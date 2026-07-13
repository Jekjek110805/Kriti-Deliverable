# CLI/monthly-report pipeline only (invoked from app/main.py), separate from
# the live FastAPI web app's Stage 1A pipeline (jobs.py -> app/api.py, using
# agents/funnel_topics.py for classification). Do not wire this into the web API.
import json

from agents.topic_discovery import TopicDiscoveryAgent
from agents.gsc_opportunity import GSCOpportunityAgent
from agents.keyword_research import KeywordResearchAgent
from agents.audience_research import AudienceResearchAgent
from agents.opportunity_scoring import OpportunityScoringAgent
from agents.existing_page_evaluation import ExistingPageEvaluationAgent
from agents.monthly_report import MonthlyReportAgent
from agents.executive_summary import ExecutiveSummaryAgent
from agents.content_calendar_export import ContentCalendarExportAgent
from agents.approval_workflow import ApprovalWorkflowAgent
from agents.structured_report import StructuredReportAgent


class Stage1WorkflowAgent:

    def run(
        self,
        seed_keywords,
        existing_pages,
        keyword_metrics,
        use_ai_enrichment=True
    ):

        topic_agent = TopicDiscoveryAgent()
        gsc_agent = GSCOpportunityAgent()
        keyword_agent = KeywordResearchAgent()
        audience_agent = AudienceResearchAgent()
        scoring_agent = OpportunityScoringAgent()
        evaluation_agent = ExistingPageEvaluationAgent()

        report_agent = MonthlyReportAgent()
        summary_agent = ExecutiveSummaryAgent()
        calendar_agent = ContentCalendarExportAgent()
        approval_agent = ApprovalWorkflowAgent()
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

        # Add metadata
        structured_report["_meta"] = {
            "ai_enrichment_used": use_ai_enrichment,
            "pipeline_version": "2.0"
        }

        return structured_report
