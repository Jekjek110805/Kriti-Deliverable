class TopicDiscoveryAgent:
    def run(self, seed_keywords):
        topics = []

        for keyword in seed_keywords:
            topics.append({
                "topic": keyword.title(),
                "keyword": keyword,
                "status": "discovered"
            })

        return topics
