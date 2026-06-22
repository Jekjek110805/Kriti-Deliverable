import json

from agents.structured_report import StructuredReportAgent
from agents.executive_summary import ExecutiveSummaryAgent
from agents.approval_workflow import ApprovalWorkflowAgent
from agents.content_calendar_export import ContentCalendarExportAgent
from agents.topic_discovery import TopicDiscoveryAgent
from agents.gsc_opportunity import GSCOpportunityAgent
from agents.keyword_research import KeywordResearchAgent
from agents.audience_research import AudienceResearchAgent
from agents.opportunity_scoring import OpportunityScoringAgent
from agents.monthly_report import MonthlyReportAgent
from agents.existing_page_evaluation import ExistingPageEvaluationAgent

def main():
    seed_keywords = [
        "CRM for clinics",
        "clinic management software",
        "patient management system"
    ]

    existing_pages = [
        {
            "title": "Best clinic management software",
            "url": "/best-clinic-management-software",
            "ranking_keywords": ["clinic management software"],
            "position": 8,
            "impressions": 1200
        },
        {
            "title": "How clinics manage patient records",
            "url": "/manage-patient-records",
            "ranking_keywords": ["patient management system"],
            "position": 14,
            "impressions": 700
        }
    ]

    keyword_metrics = {
        "CRM for clinics": {
            "volume": 400,
            "keyword_difficulty": 22,
            "intent": "BOFU",
            "commercial_potential": "High"
        },
        "clinic management software": {
            "volume": 900,
            "keyword_difficulty": 30,
            "intent": "MOFU",
            "commercial_potential": "High"
        },
        "patient management system": {
            "volume": 700,
            "keyword_difficulty": 27,
            "intent": "MOFU",
            "commercial_potential": "Medium"
        }
    }

    topic_agent = TopicDiscoveryAgent()
    gsc_agent = GSCOpportunityAgent()
    keyword_agent = KeywordResearchAgent()
    audience_agent = AudienceResearchAgent()
    scoring_agent = OpportunityScoringAgent()
    evaluation_agent = ExistingPageEvaluationAgent()
    report_agent = MonthlyReportAgent()
    calendar_agent = ContentCalendarExportAgent()
    approval_agent = ApprovalWorkflowAgent()
    summary_agent = ExecutiveSummaryAgent()
    structured_report_agent = StructuredReportAgent()

    topics = topic_agent.run(seed_keywords)
    topics = gsc_agent.run(topics, existing_pages)
    topics = keyword_agent.run(topics, keyword_metrics)
    topics = audience_agent.run(topics)
    topics = scoring_agent.run(topics)
    topics = evaluation_agent.run(topics)

    report = report_agent.run(topics)
    executive_summary = summary_agent.run(report)
    calendar_export = calendar_agent.run(report)
    approval_queue = approval_agent.run(report)
    structured_report = structured_report_agent.run(
        executive_summary,
        report,
        approval_queue,
        calendar_export
    )

    with open("reports/monthly_topic_report.json", "w") as file:
        json.dump(report, file, indent=2)

    with open("reports/executive_summary.json", "w") as file:
        json.dump(executive_summary, file, indent=2)

    with open("reports/content_calendar_export.json", "w") as file:
        json.dump(calendar_export, file, indent=2)

    with open("reports/approval_queue.json", "w") as file:
        json.dump(approval_queue, file, indent=2)

    with open("reports/stage1_monthly_opportunity_report.json", "w") as file:
        json.dump(structured_report, file, indent=2)

    print(json.dumps(report, indent=2))
    print("Report saved to reports/monthly_topic_report.json")
    print("Executive summary saved to reports/executive_summary.json")
    print("Calendar export saved to reports/content_calendar_export.json")
    print("Approval queue saved to reports/approval_queue.json")
    print("Structured Stage 1 report saved to reports/stage1_monthly_opportunity_report.json")

if __name__ == "__main__":
    main()
