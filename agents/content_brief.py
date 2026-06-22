class ContentBriefAgent:
    def run(self, opportunity):
        keyword = opportunity.get("keyword")
        topic = opportunity.get("topic")
        intent = opportunity.get("intent")
        audience_questions = opportunity.get("audience_questions", [])

        return {
            "topic": topic,
            "keyword": keyword,
            "intent": intent,
            "recommended_h1": f"{topic}: A Practical Guide",
            "brief_status": "Pending Human Approval",
            "target_audience": "Buyer, user, or warm lead",
            "content_goal": opportunity.get("recommendation"),
            "outline": [
                {
                    "heading": f"What is {keyword}?",
                    "purpose": "Define the topic clearly."
                },
                {
                    "heading": f"Why {keyword} matters",
                    "purpose": "Explain business value."
                },
                {
                    "heading": f"How to choose {keyword}",
                    "purpose": "Help the reader evaluate options."
                },
                {
                    "heading": "Common questions",
                    "purpose": "Answer audience questions."
                }
            ],
            "faq_questions": audience_questions,
            "cta": "Book a demo or contact the team to learn more.",
            "internal_link_notes": "Add 2 to 3 relevant internal links.",
            "media_requirements": [
                "One relevant hero image",
                "One original chart, screenshot, or infographic if available",
                "Descriptive alt text for every image"
            ],
            "human_approval_required": True
        }
