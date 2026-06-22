import datetime


class MonthlyReportAgent:
    def run(self, topics):
        report = {
            "executive_summary": self._build_executive_summary(topics),
            "existing_page_opportunities": [],
            "new_content_opportunities": [],
            "audience_insights": [],
            "approval_queue": [],
            "content_calendar_export": [],
        }

        for topic in topics:
            has_existing_page = topic.get("existing_page") is not None

            if has_existing_page:
                entry = self._build_existing_page_entry(topic)
                report["existing_page_opportunities"].append(entry)
            else:
                entry = self._build_new_content_entry(topic)
                report["new_content_opportunities"].append(entry)

            # Collect audience insights with source attribution
            for question in topic.get("audience_questions", []):
                report["audience_insights"].append({
                    "question": question,
                    "keyword": topic.get("keyword"),
                    "topic": topic.get("topic"),
                    "source_attribution": topic.get("audience_question_source", "Reddit"),
                })

            for question in topic.get("ai_audience_questions", []):
                report["audience_insights"].append({
                    "question": question,
                    "keyword": topic.get("keyword"),
                    "topic": topic.get("topic"),
                    "source_attribution": "AI-generated",
                })

            # Approval queue entry
            report["approval_queue"].append({
                "keyword": topic.get("keyword"),
                "topic": topic.get("topic"),
                "opportunity_type": topic.get("opportunity_type"),
                "opportunity_score": topic.get("opportunity_score"),
                "priority": topic.get("priority"),
                "recommendation": entry.get("recommendation"),
                "approval_status": "Pending Human Approval",
            })

            # Content calendar export entry
            report["content_calendar_export"].append({
                "keyword": topic.get("keyword"),
                "topic": topic.get("topic"),
                "due_date": None,
                "assigned_to": None,
                "status": "Proposed",
                "recommendation": entry.get("recommendation"),
                "priority": topic.get("priority"),
            })

        return report

    def _build_executive_summary(self, topics):
        total = len(topics)
        existing_count = sum(1 for t in topics if t.get("existing_page") is not None)
        new_count = total - existing_count
        high_priority = sum(1 for t in topics if t.get("priority") == "High")

        total_volume = sum(t.get("volume", 0) or 0 for t in topics)
        avg_difficulty = (
            sum(t.get("keyword_difficulty", 0) or 0 for t in topics) / total
            if total > 0
            else 0
        )

        # Aggregate expected impact across all topics
        expected_impact = {
            "total_keywords_analyzed": total,
            "existing_page_opportunities": existing_count,
            "new_content_opportunities": new_count,
            "high_priority_opportunities": high_priority,
            "total_monthly_search_volume": total_volume,
            "average_keyword_difficulty": round(avg_difficulty, 1),
            "projected_traffic_uplift": self._estimate_traffic_uplift(topics),
            "estimated_timeline_to_results": "3-6 months",
        }

        now = datetime.datetime.now()
        return {
            "month": now.strftime("%B %Y"),
            "total_opportunities": total,
            "existing_pages_count": existing_count,
            "new_content_count": new_count,
            "high_priority_count": high_priority,
            "expected_impact": expected_impact,
        }

    def _estimate_traffic_uplift(self, topics):
        """Rough estimate of potential monthly traffic uplift."""
        uplift = 0
        for t in topics:
            volume = t.get("volume", 0) or 0
            difficulty = t.get("keyword_difficulty", 0) or 50
            # Assume we can capture a fraction of volume inversely proportional to difficulty
            capture_rate = max(0.05, (100 - difficulty) / 100 * 0.3)
            uplift += int(volume * capture_rate)
        return uplift

    def _build_existing_page_entry(self, topic):
        return {
            "keyword": topic.get("keyword"),
            "topic": topic.get("topic"),
            "volume": topic.get("volume"),
            "keyword_difficulty": topic.get("keyword_difficulty"),
            "intent": topic.get("intent"),
            "commercial_potential": topic.get("commercial_potential"),
            "opportunity_type": topic.get("opportunity_type"),
            "opportunity_score": topic.get("opportunity_score"),
            "priority": topic.get("priority"),
            "recommendation": "Improve Existing Page",
            "reason": "An existing page is already ranking and can be optimized.",
            "approval_status": "Pending Human Approval",
            # Existing page details
            "existing_page": topic.get("existing_page"),
            "existing_page_title": topic.get("existing_page_title"),
            "existing_page_evaluation": topic.get("existing_page_evaluation"),
            "gsc_position": topic.get("gsc_position"),
            "gsc_impressions": topic.get("gsc_impressions"),
            # --- New supporting fields per spec ---
            "current_ranking_page": topic.get("existing_page", "N/A"),
            "intent_match": self._determine_intent_match(topic),
            "improvement_opportunity": topic.get(
                "improvement_opportunity",
                self._infer_improvement_opportunity(topic),
            ),
            "suggested_sections": topic.get(
                "suggested_sections",
                topic.get("suggested_h2s", []),
            ),
            "potential_internal_links": topic.get("potential_internal_links", []),
            "expected_impact": topic.get(
                "expected_impact",
                self._estimate_entry_impact(topic),
            ),
            # Content aids
            "audience_questions": topic.get("audience_questions", []),
            "suggested_h2s": topic.get("suggested_h2s", []),
            "ai_audience_questions": topic.get("ai_audience_questions", []),
            "ai_h2s": topic.get("ai_h2s", []),
            "ai_reasoning": topic.get("ai_reasoning", ""),
        }

    def _build_new_content_entry(self, topic):
        return {
            "keyword": topic.get("keyword"),
            "topic": topic.get("topic"),
            "volume": topic.get("volume"),
            "keyword_difficulty": topic.get("keyword_difficulty"),
            "intent": topic.get("intent"),
            "commercial_potential": topic.get("commercial_potential"),
            "opportunity_type": topic.get("opportunity_type"),
            "opportunity_score": topic.get("opportunity_score"),
            "priority": topic.get("priority"),
            "recommendation": "Create New Page",
            "reason": "No existing page currently matches this keyword.",
            "approval_status": "Pending Human Approval",
            # --- New supporting fields per spec ---
            "why_existing_cannot_win": topic.get(
                "why_existing_cannot_win",
                "No existing page targets this keyword or intent.",
            ),
            "target_audience": topic.get(
                "target_audience",
                self._infer_target_audience(topic),
            ),
            "business_value": topic.get(
                "business_value",
                self._infer_business_value(topic),
            ),
            "suggested_content_angle": topic.get(
                "suggested_content_angle",
                f"Comprehensive guide covering '{topic.get('keyword', '')}'",
            ),
            "suggested_cta": topic.get(
                "suggested_cta",
                self._infer_cta(topic),
            ),
            # Content aids
            "audience_questions": topic.get("audience_questions", []),
            "suggested_h2s": topic.get("suggested_h2s", []),
            "ai_audience_questions": topic.get("ai_audience_questions", []),
            "ai_h2s": topic.get("ai_h2s", []),
            "ai_reasoning": topic.get("ai_reasoning", ""),
        }

    # --- Helper inference methods ---

    def _determine_intent_match(self, topic):
        intent = topic.get("intent", "")
        existing_eval = topic.get("existing_page_evaluation", "")
        if existing_eval:
            return f"Existing page partially matches '{intent}' intent — optimization recommended."
        return f"Existing page aligns with '{intent}' intent."

    def _infer_improvement_opportunity(self, topic):
        gsc_position = topic.get("gsc_position", 0) or 0
        if gsc_position > 10:
            return "Page is ranking beyond page 1; optimize title, meta, and on-page content to climb."
        if gsc_position > 3:
            return "Page is on page 1 but not in top 3; improve content depth and E-E-A-T signals."
        return "Page is ranking well; focus on content freshness and internal linking to maintain position."

    def _estimate_entry_impact(self, topic):
        volume = topic.get("volume", 0) or 0
        difficulty = topic.get("keyword_difficulty", 0) or 50
        capture_rate = max(0.05, (100 - difficulty) / 100 * 0.25)
        estimated_additional_traffic = int(volume * capture_rate)
        return {
            "estimated_additional_monthly_traffic": estimated_additional_traffic,
            "confidence": "medium" if difficulty < 60 else "low",
            "effort_level": "low" if difficulty < 40 else "medium" if difficulty < 70 else "high",
        }

    def _infer_target_audience(self, topic):
        intent = topic.get("intent", "informational")
        if intent == "commercial":
            return "Buyers and decision-makers researching solutions before purchase."
        if intent == "transactional":
            return "Users ready to take action (sign up, buy, contact)."
        return "General audience seeking information on this topic."

    def _infer_business_value(self, topic):
        potential = topic.get("commercial_potential", "low")
        volume = topic.get("volume", 0) or 0
        if potential == "high" and volume > 1000:
            return "High — strong commercial intent with significant search volume."
        if potential in ("medium", "high"):
            return "Medium — moderate commercial potential worth capturing."
        return "Low — primarily informational value; supports topical authority."

    def _infer_cta(self, topic):
        intent = topic.get("intent", "informational")
        if intent == "transactional":
            return "Add a prominent 'Get Started' or 'Request a Demo' CTA."
        if intent == "commercial":
            return "Include comparison tables and a 'See Pricing' CTA."
        return "Add a newsletter signup or related content recommendation CTA."
