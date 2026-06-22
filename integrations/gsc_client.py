import os
import json
import requests
from pathlib import Path


def _load_keys():
    """Load API keys from config/api_keys.json or environment."""
    keys_file = Path(__file__).parent.parent / "config" / "api_keys.json"
    if keys_file.exists():
        with open(keys_file) as f:
            return json.load(f)
    return {}


class GSCClient:
    """Google Search Console API client for fetching performance data."""

    def __init__(self):
        keys = _load_keys()
        self.api_key = os.getenv("GSC_API_KEY", keys.get("GSC_API_KEY", ""))
        self.site_url = os.getenv("GSC_SITE_URL", keys.get("GSC_SITE_URL", ""))
        self.base_url = "https://searchconsole.googleapis.com/webmasters/v3"
        self._has_credentials = bool(self.api_key and self.site_url)

    def has_credentials(self):
        return self._has_credentials

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

    def get_performance_data(self, days=30, row_limit=250):
        """
        Fetch search performance data from GSC.
        Returns rows with: query, page, clicks, impressions, ctr, position
        """
        if not self._has_credentials:
            return None

        end_date = "2026-06-22"
        start_date = "2026-05-23"

        try:
            from datetime import datetime, timedelta
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        except Exception:
            pass

        url = f"{self.base_url}/sites/{self.site_url}/searchAnalytics/query"

        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query", "page"],
            "rowLimit": row_limit,
            "startRow": 0,
            "dataState": "final"
        }

        try:
            response = requests.post(
                url,
                headers=self._headers(),
                json=payload,
                params={"key": self.api_key},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            rows = []
            for row in data.get("rows", []):
                rows.append({
                    "query": row["keys"][0],
                    "page": row["keys"][1],
                    "clicks": row["clicks"],
                    "impressions": row["impressions"],
                    "ctr": row["ctr"],
                    "position": row["position"]
                })
            return rows

        except requests.exceptions.RequestException as e:
            print(f"GSC API error: {e}")
            return None

    def get_sitemaps(self):
        """Fetch sitemap status."""
        if not self._has_credentials:
            return None

        url = f"{self.base_url}/sites/{self.site_url}/sitemaps"

        try:
            response = requests.get(
                url,
                headers=self._headers(),
                params={"key": self.api_key},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return None

    def submit_url(self, url_to_submit):
        """Submit a URL for indexing."""
        if not self._has_credentials:
            return False

        url = f"{self.base_url}/sites/{self.site_url}/index:submit"
        payload = {"url": url_to_submit, "type": "URL_UPDATED"}

        try:
            response = requests.post(
                url,
                headers=self._headers(),
                json=payload,
                params={"key": self.api_key},
                timeout=30
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False
