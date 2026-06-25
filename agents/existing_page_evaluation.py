class ExistingPageEvaluationAgent:
    def run(self, topics):
        from integrations.litellm_client import client

        evaluated_topics = []

        for topic in topics:
            has_existing_page = topic.get("existing_page") is not None
            position = topic.get("gsc_position")
            intent = topic.get("intent")

            intent_match_score = 0
            expansion_potential_score = 0
            performance_score = 0
            cannibalization_score = 0
            business_value_score = 0

            if has_existing_page:
                if intent in ["BOFU", "MOFU"]:
                    intent_match_score = 30
                    expansion_potential_score = 25
                else:
                    intent_match_score = 15
                    expansion_potential_score = 10
                cannibalization_score = 15

            if position:
                if 3 <= position <= 10:
                    performance_score = 20
                elif 11 <= position <= 20:
                    performance_score = 15
                elif 21 <= position <= 30:
                    performance_score = 10
                else:
                    performance_score = 5

            if topic.get("commercial_potential") == "High":
                business_value_score = 10
            elif topic.get("commercial_potential") == "Medium":
                business_value_score = 5
            else:
                business_value_score = 2

            total_score = (
                intent_match_score + expansion_potential_score +
                performance_score + cannibalization_score + business_value_score
            )

            if has_existing_page and intent_match_score >= 25 and expansion_potential_score >= 20:
                recommendation = "Optimize Existing Page"
                reasoning = "Existing page has strong intent match and can be expanded."
            elif not has_existing_page or intent_match_score < 15 or expansion_potential_score < 10:
                recommendation = "Create New Content"
                reasoning = "No suitable existing page was found or scores are too low."
            else:
                recommendation = "Expand Existing Page"
                reasoning = "Existing page exists but may need more substantial updates."

            topic["existing_page_evaluation"] = {
                "intent_match_score": intent_match_score,
                "expansion_potential_score": expansion_potential_score,
                "performance_score": performance_score,
                "cannibalization_score": cannibalization_score,
                "business_value_score": business_value_score,
                "total_score": total_score,
                "recommendation": recommendation,
                "reasoning": reasoning
            }

            # Stage 1B: Implementation recommendation (pure Python)
            from hermes_client import compute_stage1b_recommendation, classify_content_type
            stage1b = compute_stage1b_recommendation(
                keyword=topic.get("keyword", ""),
                page=topic.get("existing_page", ""),
                position=topic.get("gsc_position", 0) or 0,
                intent=topic.get("intent", "MOFU"),
                commercial=topic.get("commercial_potential", "Low"),
                clicks=topic.get("gsc_clicks", 0) or 0,
                impressions=topic.get("gsc_impressions", 0) or 0,
            )
            topic["implementation_recommendation"] = stage1b["recommendation"]
            topic["content_type"] = stage1b["content_type"]
            topic["confidence"] = stage1b["confidence"]
            topic["next_action"] = stage1b["next_action"]

            # AI enrichment (optional — Hermes for language explanation)
            try:
                explanation = client.generate_explanation(keyword=topic["keyword"], scores_dict=topic["existing_page_evaluation"])
                if explanation and not explanation.startswith("[LiteLLM"):
                    topic["ai_reasoning"] = explanation
            except Exception:
                pass

            topic["recommendation"] = recommendation
            topic["reason"] = reasoning
            evaluated_topics.append(topic)

        return evaluated_topics
