class OpportunityScoringAgent:

    def run(self, topics):
        scored_topics = []

        for topic in topics:

            score = 0

            # Existing Page Opportunity (20)
            if topic.get("existing_page"):
                score += 20

            # GSC Opportunity (15)
            position = topic.get("gsc_position")

            if position:
                if 3 <= position <= 10:
                    score += 15
                elif 11 <= position <= 20:
                    score += 12
                elif 21 <= position <= 30:
                    score += 8

            # Intent (15)
            intent = topic.get("intent")

            if intent == "BOFU":
                score += 15
            elif intent == "MOFU":
                score += 10
            elif intent == "TOFU":
                score += 5

            # Business Value (15)
            potential = topic.get("commercial_potential")

            if potential == "High":
                score += 15
            elif potential == "Medium":
                score += 8

            # Audience Demand (10)
            if len(topic.get("audience_questions", [])) >= 3:
                score += 10

            # Search Volume (10)
            volume = topic.get("volume", 0)

            if volume >= 1000:
                score += 10
            elif volume >= 500:
                score += 8
            elif volume >= 100:
                score += 6

            # KD (5)
            kd = topic.get("keyword_difficulty", 100)

            if kd <= 20:
                score += 5
            elif kd <= 35:
                score += 4
            elif kd <= 50:
                score += 3

            topic["opportunity_score"] = score

            if score >= 80:
                topic["priority"] = "Critical"
            elif score >= 65:
                topic["priority"] = "High"
            elif score >= 50:
                topic["priority"] = "Medium"
            else:
                topic["priority"] = "Low"

            scored_topics.append(topic)

        return scored_topics
