class ExecutiveSummaryAgent:
    def run(self, report):
        from integrations.litellm_client import client

        total = len(report)

        existing_page_count = sum(
            1 for item in report
            if item.get("opportunity_type") == "Existing Page Optimization"
        )

        new_content_count = sum(
            1 for item in report
            if item.get("opportunity_type") == "New Content Opportunity"
        )

        priority_counts = {
            "Critical": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0
        }

        for item in report:
            priority = item.get("priority", "Low")
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        top_opportunity = None

        if report:
            top_opportunity = max(
                report,
                key=lambda item: item.get("opportunity_score", 0)
            )

        summary = {
            "total_opportunities": total,
            "existing_page_opportunities": existing_page_count,
            "new_content_opportunities": new_content_count,
            "priority_counts": priority_counts,
            "top_opportunity": {
                "keyword": top_opportunity.get("keyword") if top_opportunity else None,
                "recommendation": top_opportunity.get("recommendation") if top_opportunity else None,
                "score": top_opportunity.get("opportunity_score") if top_opportunity else None,
                "priority": top_opportunity.get("priority") if top_opportunity else None
            }
        }

        # Add AI narrative
        try:
            narrative = client.generate_executive_narrative(summary)
            if narrative and not narrative.startswith("[LiteLLM"):
                summary["ai_narrative"] = narrative
        except Exception:
            pass

        return summary
