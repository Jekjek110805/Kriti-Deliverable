import os
import requests


class SemrushClient:
    def __init__(self):
        self.api_key = os.getenv("SEMRUSH_API_KEY")
        self.database = os.getenv("SEMRUSH_DATABASE", "us")
        self.base_url = "https://api.semrush.com/"

    def has_credentials(self):
        return bool(self.api_key)

    def get_keyword_metrics(self, keyword):
        if not self.has_credentials():
            raise ValueError("Missing SEMRUSH_API_KEY in .env")

        params = {
            "type": "phrase_this",
            "key": self.api_key,
            "phrase": keyword,
            "database": self.database,
            "export_columns": "Ph,Nq,Kd"
        }

        response = requests.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()

        return response.text

