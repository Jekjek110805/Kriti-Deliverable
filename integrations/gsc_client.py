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
    """Google Search Console API client.
    
    NOTE: The Search Console API requires OAuth 2.0 (service account),
    NOT an API key. CSV upload is the primary data source.
    This client is kept for future OAuth integration.
    """

    def __init__(self):
        keys = _load_keys()
        self.api_key = os.getenv("GSC_API_KEY", keys.get("GSC_API_KEY", ""))
        self.site_url = os.getenv("GSC_SITE_URL", keys.get("GSC_SITE_URL", ""))
        self.credentials_path = os.getenv(
            "GSC_CREDENTIALS_PATH",
            keys.get("GSC_CREDENTIALS_PATH", "")
        )
        self.base_url = "https://searchconsole.googleapis.com/webmasters/v3"
        self._has_credentials = bool(self.credentials_path and os.path.exists(self.credentials_path))

    def has_credentials(self):
        """GSC needs OAuth service account credentials, not just an API key."""
        return self._has_credentials

    def get_performance_data(self, days=30, row_limit=250):
        """Fetch live GSC data via OAuth (requires service account JSON)."""
        if not self._has_credentials:
            return None

        # Future: OAuth2 flow with service account
        return None

    @staticmethod
    def setup_instructions():
        return {
            "method": "service_account",
            "steps": [
                "Go to console.google.com → APIs & Services → Library",
                "Search 'Search Console API' → Enable",
                "Go to Credentials → Create Service Account",
                "Download JSON key file",
                "Add service account email to GSC property as Owner",
                "Place JSON key in config/gsc_credentials.json",
            ],
            "note": "API keys alone do NOT work for Search Console. CSV upload works today.",
        }
