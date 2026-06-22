class AudienceResearchAgent:
    def run(self, topics):
        from integrations.litellm_client import client

        enriched_topics = []

        for topic in topics:
            keyword = topic["keyword"]
            intent = topic.get("intent", "Unknown")

            # Keep deterministic fallback questions
            topic["audience_questions"] = [
                f"What is the best {keyword}?",
                f"How do I choose {keyword}?",
                f"Is {keyword} worth it for small clinics?"
            ]

            topic["suggested_h2s"] = [
                f"What is {keyword}?",
                f"How to choose {keyword}",
                f"Best use cases for {keyword}"
            ]

            # AI enrichment
            try:
                enrichment = client.generate_audience_questions(keyword, intent)
                if enrichment and not str(enrichment[0]).startswith("[LiteLLM"):
                    topic["ai_audience_questions"] = enrichment
            except Exception:
                pass

            try:
                h2s = client.generate_h2s(keyword, topic.get("topic", keyword), intent)
                if h2s and not str(h2s[0]).startswith("[LiteLLM"):
                    topic["ai_h2s"] = h2s
            except Exception:
                pass

            enriched_topics.append(topic)

        return enriched_topics
