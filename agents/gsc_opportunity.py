import os
import json
from pathlib import Path

from integrations.gsc_client import GSCClient

EXISTING_PAGES_PATH = Path(__file__).parent.parent / "data" / "existing_pages.json"


class GSCOpportunityAgent:
    def __init__(self):
        self.client = GSCClient()
        self.use_api = self.client.has_credentials()

    def run(self, topics, existing_pages=None):
        """
        Enrich topics with GSC data.
        If GSC_API_KEY + GSC_SITE_URL are set, fetches live data from API.
        Otherwise falls back to matching against existing_pages JSON.
        """
        if self.use_api:
            return self._run_from_api(topics)
        return self._run_from_data(topics, existing_pages or [])

    def _run_from_api(self, topics):
        """Fetch live GSC data and match against topics."""
        performance_rows = self.client.get_performance_data(days=30)
        if not performance_rows:
            return self._run_from_data(topics, [])

        enriched_topics = []
        for topic in topics:
            keyword = topic["keyword"].lower()
            matched_row = None

            for row in performance_rows:
                if keyword in row["query"].lower() or row["query"].lower() in keyword:
                    matched_row = row
                    break

            if matched_row:
                topic["existing_page"] = matched_row["page"]
                topic["existing_page_title"] = None
                topic["gsc_position"] = round(matched_row["position"], 1)
                topic["gsc_impressions"] = matched_row["impressions"]
                topic["gsc_clicks"] = matched_row["clicks"]
                topic["gsc_ctr"] = matched_row["ctr"]
                topic["opportunity_type"] = "Existing Page Optimization"
            else:
                topic["existing_page"] = None
                topic["existing_page_title"] = None
                topic["gsc_position"] = None
                topic["gsc_impressions"] = None
                topic["gsc_clicks"] = None
                topic["gsc_ctr"] = None
                topic["opportunity_type"] = "New Content Opportunity"

            enriched_topics.append(topic)

        return enriched_topics

    def _run_from_data(self, topics, existing_pages):
        """Original matching logic using existing_pages JSON."""
        enriched_topics = []

        for topic in topics:
            keyword = topic["keyword"]
            matched_page = None

            for page in existing_pages:
                if keyword in page.get("ranking_keywords", []):
                    matched_page = page
                    break

            topic["existing_page"] = matched_page["url"] if matched_page else None
            topic["existing_page_title"] = matched_page["title"] if matched_page else None
            topic["gsc_position"] = matched_page["position"] if matched_page else None
            topic["gsc_impressions"] = matched_page["impressions"] if matched_page else None
            topic["gsc_clicks"] = matched_page.get("clicks", None) if matched_page else None
            topic["gsc_ctr"] = matched_page.get("ctr", None) if matched_page else None

            if matched_page:
                topic["opportunity_type"] = "Existing Page Optimization"
            else:
                topic["opportunity_type"] = "New Content Opportunity"

            enriched_topics.append(topic)

        return enriched_topics
