class StructuredReportAgent:
    def run(self, executive_summary, report, approval_queue, calendar_export):
        existing_page_opportunities = []
        new_content_opportunities = []
        audience_insights = []

        for item in report:
            if item.get("opportunity_type") == "Existing Page Optimization":
                existing_page_opportunities.append(item)

            if item.get("opportunity_type") == "New Content Opportunity":
                new_content_opportunities.append(item)

            audience_insights.append({
                "topic": item.get("topic"),
                "keyword": item.get("keyword"),
                "audience_questions": item.get("audience_questions", []),
                "suggested_h2s": item.get("suggested_h2s", [])
            })

        return {
            "executive_summary": executive_summary,
            "existing_page_opportunities": existing_page_opportunities,
            "new_content_opportunities": new_content_opportunities,
            "audience_insights": audience_insights,
            "approval_queue": approval_queue,
            "content_calendar_export": calendar_export
        }
