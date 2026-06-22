class MonthlyReportAgent:
    def run(self, topics):
        report = []

        for topic in topics:
            has_existing_page = topic.get("existing_page") is not None

            if has_existing_page:
                recommendation = "Improve Existing Page"
                reason = "An existing page is already ranking and can be optimized."
            else:
                recommendation = "Create New Page"
                reason = "No existing page currently matches this keyword."

            report.append({
                "keyword": topic.get("keyword"),
                "topic": topic.get("topic"),
                "volume": topic.get("volume"),
                "keyword_difficulty": topic.get("keyword_difficulty"),
                "intent": topic.get("intent"),
                "commercial_potential": topic.get("commercial_potential"),
                "existing_page": topic.get("existing_page"),
                "existing_page_title": topic.get("existing_page_title"),
                "existing_page_evaluation": topic.get("existing_page_evaluation"),
                "gsc_position": topic.get("gsc_position"),
                "gsc_impressions": topic.get("gsc_impressions"),
                "opportunity_type": topic.get("opportunity_type"),
                "opportunity_score": topic.get("opportunity_score"),
                "priority": topic.get("priority"),
                "recommendation": recommendation,
                "reason": reason,
                "audience_questions": topic.get("audience_questions", []),
                "suggested_h2s": topic.get("suggested_h2s", []),
                "ai_audience_questions": topic.get("ai_audience_questions", []),
                "ai_h2s": topic.get("ai_h2s", []),
                "ai_reasoning": topic.get("ai_reasoning", ""),
                "approval_status": "Pending Human Approval"
            })

        return report
