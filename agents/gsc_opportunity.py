class GSCOpportunityAgent:
    def run(self, topics, existing_pages):
        enriched_topics = []

        for topic in topics:
            keyword = topic["keyword"]
            matched_page = None

            for page in existing_pages:
                if keyword in page["ranking_keywords"]:
                    matched_page = page
                    break

            topic["existing_page"] = matched_page["url"] if matched_page else None
            topic["existing_page_title"] = matched_page["title"] if matched_page else None
            topic["gsc_position"] = matched_page["position"] if matched_page else None
            topic["gsc_impressions"] = matched_page["impressions"] if matched_page else None

            if matched_page:
                topic["opportunity_type"] = "Existing Page Optimization"
            else:
                topic["opportunity_type"] = "New Content Opportunity"

            enriched_topics.append(topic)

        return enriched_topics
