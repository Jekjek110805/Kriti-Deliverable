# Live Google Search Console API Integration (Stage 1A)

Stage 1A can read query/page performance data in two ways:

1. **CSV / XLSX upload** — the default. Works with zero configuration.
2. **Live Search Console API** — uses a Google **service account** to query the
   Search Analytics API directly. Enabled when credentials are configured.

CSV upload is never removed. When live credentials are present the system
**prefers live data** and **falls back to CSV** if the API is missing or fails.

---

## 1. Where to put the service-account JSON

Place your downloaded service-account key here:

```
config/gsc_credentials.json
```

> You downloaded `for-kriti-500207-f576315470fa.json`. Copy/rename it to
> `config/gsc_credentials.json` in the project root.

PowerShell:

```powershell
Copy-Item "$env:USERPROFILE\Downloads\for-kriti-500207-f576315470fa.json" `
          "config\gsc_credentials.json"
```

This path is already git-ignored (`.gitignore` → `config/gsc_credentials.json`),
so the secret will **not** be committed. You can store it elsewhere and point
`GSC_CREDENTIALS_PATH` at it instead (absolute or project-relative path).

> ⚠️ The key you opened in the editor is now exposed. Because the private key is
> visible, **rotate/regenerate it** in Google Cloud before using it in any shared
> or production environment.

---

## 2. Required environment variables

Set these in `.env` (copy from `.env.example`) or `config/api_keys.json`.
Environment variables win over config files.

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `GSC_SITE_URL` | Yes (for live) | `https://example.com/` or `sc-domain:example.com` | Must **exactly** match a verified GSC property. |
| `GSC_CREDENTIALS_PATH` | Yes (for live) | `config/gsc_credentials.json` | Path to the service-account JSON. Relative paths resolve from the project root. |
| `GSC_API_KEY` | No | — | Not used for Search Analytics; kept for compatibility. |

Live mode activates only when **both** `GSC_SITE_URL` and a readable
credentials file are present (`GSCClient.has_credentials()`).

---

## 3. Configuring the GSC property

1. In **Google Cloud Console** → *APIs & Services → Library*, enable the
   **Google Search Console API** for project `for-kriti-500207`.
2. The service account email is:
   `kriti-project@for-kriti-500207.iam.gserviceaccount.com`
3. In **Search Console** → *Settings → Users and permissions*, add that email
   as a user (Full or Restricted) on the verified property.
4. Set `GSC_SITE_URL` to the **exact** property string:
   - URL-prefix property → `https://example.com/` (note the trailing slash).
   - Domain property → `sc-domain:example.com`.

The current `config/api_keys.json` has `GSC_SITE_URL` set to a localhost
placeholder. Replace it with the real verified property URL (or set
`GSC_SITE_URL` in `.env`).

---

## 4. How to test the integration

Start the server, then:

```powershell
# A. Status — confirms credentials are detected
curl http://localhost:8080/api/integrations/gsc/status

# B. Validate — does a tiny live query (last 7 days, 5 rows)
curl http://localhost:8080/api/integrations/gsc/validate

# C. Pull live data and queue Stage 1A analysis
curl -X POST http://localhost:8080/api/integrations/gsc/pull `
     -H "Content-Type: application/json" -d '{"days":30,"row_limit":250}'

# D. Stage 1A live-first: NO file => uses live GSC; with a file => CSV
curl -X POST http://localhost:8080/api/stage1a/analyze -F "days=30"
curl -X POST http://localhost:8080/api/stage1a/analyze -F "file=@export.csv"
```

A successful validate returns `{"valid": true, "test_rows": N, ...}`.
On failure you get a typed `error_code` (see below).

Quick Python smoke test (no server):

```python
from integrations.gsc_client import GSCClient
from datetime import date, timedelta

c = GSCClient()
print(c.status())
rows = c.get_search_analytics(
    start_date=date.today() - timedelta(days=30),
    end_date=date.today() - timedelta(days=2),
    dimensions=["page", "query"],
    row_limit=100,
)
print(len(rows), rows[:2])
```

---

## 5. The reusable function

```python
get_search_analytics(
    start_date,            # date or "YYYY-MM-DD"
    end_date,              # date or "YYYY-MM-DD"
    dimensions=["page", "query"],   # query, page, country, device, date, searchAppearance
    row_limit=25000,       # 1..25000
    country=None,          # ISO-3 filter, e.g. "usa"
    device=None,           # DESKTOP | MOBILE | TABLET
    search_type="web",     # web | image | video | news | discover | googleNews
)
```

Returns a list of dicts in the **internal pipeline format** — each row contains
the requested dimension values plus `clicks`, `impressions`, `ctr`, `position`
(as strings), and always includes `query`/`page` keys so the existing Stage 1A
scoring pipeline runs unchanged.

---

## 6. Error handling (`GSCError.code`)

| code | Meaning | Typical cause |
|------|---------|---------------|
| `not_configured` | No site URL / credentials file | Live mode not set up |
| `invalid_credentials` | JSON malformed or token refused | Wrong/expired key |
| `property_not_verified` | 404 from API | `GSC_SITE_URL` not a verified property |
| `insufficient_permissions` | 403 | Service account not added to the property |
| `api_disabled` | 403 / "API not enabled" | Search Console API off in the project |
| `quota_exceeded` | 429 / quota reason | Rate or quota limit hit |
| `empty_data` | 200 but no rows | New property / no traffic in range |
| `bad_request` | 400 | Bad dates or dimensions |
| `api_error` | other | Network/transport or unexpected response |

Endpoints return these as `{"error_code": "...", "error": "..."}`. The Stage 1A
endpoint additionally returns a `fallback` hint pointing to CSV upload.
