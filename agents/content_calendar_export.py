class ContentCalendarExportAgent:
    def run(self, report):
        calendar_items = []

        for item in report:
            calendar_items.append({
                "topic": item.get("topic"),
                "keyword": item.get("keyword"),
                "opportunity_type": item.get("opportunity_type"),
                "volume": item.get("volume"),
                "keyword_difficulty": item.get("keyword_difficulty"),
                "intent": item.get("intent"),
                "existing_page_url": item.get("existing_page"),
                "current_position": item.get("gsc_position"),
                "priority": item.get("priority"),
                "recommendation": item.get("recommendation"),
                "approval_status": item.get("approval_status")
            })

        return calendar_items
