import csv


class ContentCalendarCSVExportAgent:
    def run(self, calendar_items, output_path):
        fieldnames = [
            "topic",
            "keyword",
            "opportunity_type",
            "volume",
            "keyword_difficulty",
            "intent",
            "existing_page_url",
            "current_position",
            "priority",
            "recommendation",
            "approval_status"
        ]

        with open(output_path, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()

            for item in calendar_items:
                writer.writerow({
                    "topic": item.get("topic"),
                    "keyword": item.get("keyword"),
                    "opportunity_type": item.get("opportunity_type"),
                    "volume": item.get("volume"),
                    "keyword_difficulty": item.get("keyword_difficulty"),
                    "intent": item.get("intent"),
                    "existing_page_url": item.get("existing_page_url"),
                    "current_position": item.get("current_position"),
                    "priority": item.get("priority"),
                    "recommendation": item.get("recommendation"),
                    "approval_status": item.get("approval_status")
                })

        return output_path
