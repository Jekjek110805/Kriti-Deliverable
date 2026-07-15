import os
import requests


class SemrushError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class SemrushClient:
    def __init__(self, api_key=None, database=None):
        # Explicit args (from the saved UI config) win; env vars are the fallback.
        self.api_key = api_key or os.getenv("SEMRUSH_API_KEY")
        self.database = database or os.getenv("SEMRUSH_DATABASE", "us")
        self.base_url = "https://api.semrush.com/"

    def has_credentials(self):
        return bool(self.api_key)

    def get_keyword_metrics(self, keyword):
        """Raw semicolon-delimited CSV response from the Keyword Overview report."""
        if not self.has_credentials():
            raise SemrushError("Missing SEMrush API key.")

        params = {
            "type": "phrase_this",
            "key": self.api_key,
            "phrase": keyword,
            "database": self.database,
            "export_columns": "Ph,Nq,Cp,Co,Kd",
        }
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
        except requests.RequestException as exc:
            raise SemrushError(f"Could not reach the SEMrush API: {exc}") from exc
        response.raise_for_status()
        text = response.text.strip()
        if text.startswith("ERROR"):
            raise SemrushError(text)
        return text

    def get_keyword_metrics_parsed(self, keyword):
        """Structured keyword metrics: volume, CPC, competition, difficulty."""
        raw = self.get_keyword_metrics(keyword)
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        if len(lines) < 2:
            raise SemrushError("SEMrush returned no data for that keyword.")
        header = lines[0].split(";")
        values = lines[1].split(";")
        row = dict(zip(header, values))

        def _num(key, cast=float, default=0):
            try:
                return cast(row.get(key, default))
            except (TypeError, ValueError):
                return default

        return {
            "keyword": row.get("Keyword", keyword),
            "volume": _num("Search Volume", int, 0),
            "cpc": _num("CPC", float, 0.0),
            "competition": _num("Competition", float, 0.0),
            "keyword_difficulty": _num("Keyword Difficulty Index", float, 0.0),
        }
