import json

from agents.content_calendar_csv_export import ContentCalendarCSVExportAgent
from agents.workflow import Stage1WorkflowAgent
from config.paths import (
    SEED_KEYWORDS_PATH,
    EXISTING_PAGES_PATH,
    KEYWORD_METRICS_PATH,
    STAGE1_REPORT_PATH
)


def load_json(path):
    with open(path, "r") as file:
        return json.load(file)


def main():
    seed_keywords = load_json(SEED_KEYWORDS_PATH)
    existing_pages = load_json(EXISTING_PAGES_PATH)
    keyword_metrics = load_json(KEYWORD_METRICS_PATH)

    workflow = Stage1WorkflowAgent()

    structured_report = workflow.run(
        seed_keywords,
        existing_pages,
        keyword_metrics
    )

    with open(STAGE1_REPORT_PATH, "w") as file:
        json.dump(structured_report, file, indent=2)

    print(json.dumps(structured_report, indent=2))
    print(f"Structured Stage 1 report saved to {STAGE1_REPORT_PATH}")

@app.get("/stage1/content-calendar.csv")
def export_content_calendar_csv():
    report = load_json(STAGE1_REPORT_PATH)

    calendar_items = report.get("content_calendar_export", [])

    exporter = ContentCalendarCSVExportAgent()
    path = "reports/content_calendar_export.csv"

    exporter.run(calendar_items, path)

    return {
        "message": "Content calendar CSV exported",
        "path": path
    }

if __name__ == "__main__":
    main()
