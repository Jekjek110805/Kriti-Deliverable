import json
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
DEFAULT_CREDENTIALS_PATH = "config/gsc_credentials.json"

# Dimensions the Search Analytics API understands. Anything outside this set is
# rejected before it ever reaches Google so callers get a clear error.
VALID_DIMENSIONS = ("query", "page", "country", "device", "date", "searchAppearance")


class GSCError(Exception):
    """Search Console API error with a machine-readable ``code``.

    ``code`` is one of:
      not_configured        — no site URL or credentials file present
      invalid_credentials   — service-account JSON is malformed / not authorized
      property_not_verified — the site URL is not a verified GSC property
      insufficient_permissions — service account lacks access to the property
      api_disabled          — Search Console API is not enabled for the project
      quota_exceeded        — API rate / quota limit hit
      empty_data            — request succeeded but returned no rows
      bad_request           — invalid date range / dimensions / payload
      api_error             — any other API/transport failure
    """

    def __init__(self, code, message, status_code=None, raw=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.raw = raw

    def to_dict(self):
        return {
            "error_code": self.code,
            "error": self.message,
            "http_status": self.status_code,
        }


def _load_keys():
    """Load GSC settings from local config files; environment wins later."""
    keys = {}
    for keys_file in (DATA_DIR / "gsc_config.json", CONFIG_DIR / "api_keys.json"):
        if not keys_file.exists():
            continue
        with open(keys_file, encoding="utf-8") as f:
            file_keys = json.load(f)
        keys.update({
            "GSC_API_KEY": file_keys.get("GSC_API_KEY", file_keys.get("api_key", keys.get("GSC_API_KEY", ""))),
            "GSC_SITE_URL": file_keys.get("GSC_SITE_URL", file_keys.get("site_url", keys.get("GSC_SITE_URL", ""))),
            "GSC_CREDENTIALS_PATH": file_keys.get(
                "GSC_CREDENTIALS_PATH",
                file_keys.get("credentials_path", keys.get("GSC_CREDENTIALS_PATH", "")),
            ),
        })
    return keys


def _resolve_path(path_value):
    if not path_value:
        return ""
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path)


def _is_local_site_url(value):
    value = (value or "").lower()
    return value.startswith("http://localhost") or value.startswith("https://localhost") or value.startswith("http://127.0.0.1")


def _env_or_config(name, fallback):
    value = os.getenv(name)
    return value if value else fallback


def _coerce_date(value):
    """Accept a ``datetime.date`` or an ISO ``YYYY-MM-DD`` string."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


class GSCClient:
    """Google Search Console Search Analytics API client."""

    def __init__(self):
        keys = _load_keys()
        self.api_key = _env_or_config("GSC_API_KEY", keys.get("GSC_API_KEY", ""))
        self.site_url = _env_or_config("GSC_SITE_URL", keys.get("GSC_SITE_URL", ""))
        config_site_url = keys.get("GSC_SITE_URL", "")
        if _is_local_site_url(self.site_url) and config_site_url and not _is_local_site_url(config_site_url):
            self.site_url = config_site_url
        # Resolution order: env var → config file → built-in default path.
        # The default means simply dropping the JSON at config/gsc_credentials.json
        # is enough — no extra env var required.
        self.credentials_path = _resolve_path(_env_or_config(
            "GSC_CREDENTIALS_PATH",
            keys.get("GSC_CREDENTIALS_PATH", "") or DEFAULT_CREDENTIALS_PATH,
        ))
        self.base_url = "https://searchconsole.googleapis.com/webmasters/v3"
        self._has_credentials_file = bool(self.credentials_path and os.path.exists(self.credentials_path))
        self._credentials = None

    def has_credentials(self):
        """GSC needs OAuth service account credentials, not just an API key."""
        return bool(self.site_url and self._has_credentials_file)

    def service_account_email(self):
        if not self._has_credentials_file:
            return ""
        try:
            with open(self.credentials_path, encoding="utf-8") as f:
                credentials_data = json.load(f)
            return credentials_data.get("client_email", "")
        except (OSError, json.JSONDecodeError):
            return ""

    def status(self):
        return {
            "configured": self.has_credentials(),
            "site_url": self.site_url,
            "credentials_path": self.credentials_path,
            "credentials_file_exists": self._has_credentials_file,
            "service_account_email": self.service_account_email(),
        }

    def _get_credentials(self):
        if not self.has_credentials():
            raise GSCError(
                "not_configured",
                "GSC requires GSC_SITE_URL and a valid GSC_CREDENTIALS_PATH service account JSON file.",
            )
        if self._credentials is None:
            try:
                self._credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=[GSC_SCOPE],
                )
            except (ValueError, KeyError) as exc:
                raise GSCError(
                    "invalid_credentials",
                    f"Service account JSON is invalid or unreadable: {exc}",
                ) from exc
        if not self._credentials.valid:
            try:
                self._credentials.refresh(GoogleAuthRequest())
            except Exception as exc:  # google.auth.exceptions.RefreshError and friends
                raise GSCError(
                    "invalid_credentials",
                    f"Could not obtain an access token from the service account: {exc}",
                ) from exc
        return self._credentials

    @staticmethod
    def _raise_for_api_error(response):
        """Translate a non-2xx Search Console response into a typed GSCError."""
        status = response.status_code
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = err.get("message", response.text or "Search Console API error")
        reason = ""
        details = err.get("errors") or []
        if details and isinstance(details, list):
            reason = details[0].get("reason", "")
        lowered = f"{message} {reason}".lower()

        if status == 401:
            code = "invalid_credentials"
        elif status == 403:
            if "has not been used" in lowered or "is disabled" in lowered or "accessnotconfigured" in lowered:
                code = "api_disabled"
            elif "quota" in lowered or "rate" in lowered or reason in ("rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"):
                code = "quota_exceeded"
            else:
                code = "insufficient_permissions"
        elif status == 404:
            code = "property_not_verified"
        elif status == 429:
            code = "quota_exceeded"
        elif status == 400:
            code = "bad_request"
        else:
            code = "api_error"
        raise GSCError(code, message, status_code=status, raw=payload)

    def _post_search_analytics(self, payload):
        credentials = self._get_credentials()
        encoded_site_url = quote(self.site_url, safe="")
        url = f"{self.base_url}/sites/{encoded_site_url}/searchAnalytics/query"
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {credentials.token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise GSCError("api_error", f"Could not reach the Search Console API: {exc}") from exc

        if not response.ok:
            self._raise_for_api_error(response)
        return response.json()

    def get_search_analytics(
        self,
        start_date,
        end_date,
        dimensions=("page", "query"),
        row_limit=25000,
        country=None,
        device=None,
        search_type="web",
    ):
        """Query the Search Analytics API and return normalised internal rows.

        Args:
            start_date / end_date: ``datetime.date`` or ``YYYY-MM-DD`` strings.
            dimensions: any of query, page, country, device, date, searchAppearance.
            row_limit: 1..25000 (the API maximum per request).
            country: optional ISO-3166-1-alpha-3 filter (e.g. "usa").
            device: optional filter (DESKTOP / MOBILE / TABLET).
            search_type: web (default), image, video, news, discover, googleNews.

        Returns:
            list[dict] — each row carries the requested dimension values plus
            clicks, impressions, ctr and position as strings, matching the
            internal format the Stage 1A pipeline already consumes.

        Raises:
            GSCError with a typed ``code`` on any failure.
        """
        dimensions = list(dimensions) if dimensions else ["page", "query"]
        invalid = [d for d in dimensions if d not in VALID_DIMENSIONS]
        if invalid:
            raise GSCError(
                "bad_request",
                f"Unsupported GSC dimension(s): {', '.join(invalid)}. "
                f"Valid options: {', '.join(VALID_DIMENSIONS)}.",
            )

        start = _coerce_date(start_date)
        end = _coerce_date(end_date)
        if start > end:
            raise GSCError("bad_request", f"start_date {start} is after end_date {end}.")

        row_limit = max(1, min(int(row_limit), 25000))

        payload = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": dimensions,
            "rowLimit": row_limit,
            "startRow": 0,
            "type": search_type,
        }

        filters = []
        if country:
            filters.append({"dimension": "country", "operator": "equals", "expression": str(country).lower()})
        if device:
            filters.append({"dimension": "device", "operator": "equals", "expression": str(device).upper()})
        if filters:
            payload["dimensionFilterGroups"] = [{"filters": filters}]

        result = self._post_search_analytics(payload)
        api_rows = result.get("rows", [])
        if not api_rows:
            raise GSCError(
                "empty_data",
                "Search Console returned no rows for the requested range/filters. "
                "The property may be too new, or the date window may have no traffic.",
            )

        rows = []
        for item in api_rows:
            row_keys = item.get("keys", [])
            row = {}
            for index, dimension in enumerate(dimensions):
                value = row_keys[index] if index < len(row_keys) else ""
                row[dimension] = value
            row.update({
                "clicks": str(int(item.get("clicks", 0))),
                "impressions": str(int(item.get("impressions", 0))),
                "ctr": str(float(item.get("ctr", 0))),
                "position": str(float(item.get("position", 0))),
            })
            # Pipeline expects query/page keys to always exist.
            row.setdefault("query", "")
            row.setdefault("page", "")
            rows.append(row)
        return rows

    def get_performance_data(self, days=30, row_limit=250):
        """Fetch live query/page rows from GSC Search Analytics.

        Thin wrapper over :meth:`get_search_analytics` kept for backwards
        compatibility with existing callers. Returns ``None`` when GSC is not
        configured; returns an empty list when the range simply has no data.
        """
        if not self.has_credentials():
            return None

        today = date.today()
        end_date = today - timedelta(days=2)  # GSC data lags ~2 days
        start_date = end_date - timedelta(days=max(int(days), 1) - 1)
        try:
            return self.get_search_analytics(
                start_date=start_date,
                end_date=end_date,
                dimensions=["query", "page"],
                row_limit=row_limit,
            )
        except GSCError as exc:
            if exc.code == "empty_data":
                return []
            raise

    @staticmethod
    def setup_instructions():
        return {
            "method": "service_account",
            "steps": [
                "Enable the Google Search Console API in Google Cloud.",
                "Create a service account and download its JSON key.",
                "Add the service account email to the verified GSC property.",
                "Place the JSON key at config/gsc_credentials.json.",
                "Set GSC_SITE_URL to the exact verified property URL.",
                "Set GSC_CREDENTIALS_PATH=config/gsc_credentials.json.",
            ],
            "note": "Search Console does not return performance data with API keys alone.",
        }
