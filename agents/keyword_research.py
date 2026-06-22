class KeywordResearchAgent:
    def run(self, topics, keyword_metrics):
        enriched_topics = []

        for topic in topics:
            keyword = topic["keyword"]
            metrics = keyword_metrics.get(keyword, {})

            topic["volume"] = metrics.get("volume", 0)
            topic["keyword_difficulty"] = metrics.get("keyword_difficulty", 0)
            topic["intent"] = metrics.get("intent", "Unknown")
            topic["commercial_potential"] = metrics.get("commercial_potential", "Unknown")

            enriched_topics.append(topic)

        return enriched_topics
