#!/usr/bin/env python3
"""
hermes_client.py -- Pure Python Stage 1A analysis engine.
Replaces LLM subprocess calls with deterministic rule-based logic.
Returns results in the exact same format the frontend expects.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")


# ── Intent classification ────────────────────────────────────────────────────

BOFU_KEYWORDS = [
    "best", "top", "software", "service", "pricing", "cost", "compare",
    "versus", "vs", "alternative", "review", "near me", "for clinics",
    "for accountants", "for small business", "buy", "purchase", "demo",
    "trial", "sign up", "signup", "quote", "provider",
]

TOFU_KEYWORDS = [
    "what is", "history of", "definition", "meaning", "basic explanation",
    "introduction", "overview", "why does",
]

MOFU_KEYWORDS = [
    "how to choose", "how much does", "features", "benefits", "examples",
    "template", "checklist", "implementation", "mistakes", "guide",
    "tutorial", "how to", "tips", "strategies", "tools",
]


def classify_intent(keyword: str) -> str:
    kw_lower = keyword.lower()
    # Check BOFU first (highest priority)
    for b in BOFU_KEYWORDS:
        if b in kw_lower:
            return "BOFU"
    # Check TOFU
    for t in TOFU_KEYWORDS:
        if t in kw_lower:
            return "TOFU"
    # Check MOFU
    for m in MOFU_KEYWORDS:
        if m in kw_lower:
            return "MOFU"
    return "MOFU"  # default


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_existing_page(page: str) -> int:
    return 25 if page and page.strip() else 0


def score_position(position: int) -> int:
    if 3 <= position <= 5:
        return 20
    elif 6 <= position <= 10:
        return 18
    elif 11 <= position <= 20:
        return 12
    return 0


def score_impressions(impressions: int) -> int:
    if impressions >= 1000:
        return 15
    elif impressions >= 500:
        return 12
    elif impressions >= 200:
        return 9
    elif impressions >= 50:
        return 5
    return 0


def score_intent(intent: str) -> int:
    return {"BOFU": 20, "MOFU": 14, "TOFU": 5}.get(intent, 14)


def classify_commercial_potential(keyword: str, intent: str, clicks: int) -> str:
    kw_lower = keyword.lower()
    buyer_words = ["buy", "pricing", "cost", "demo", "trial", "best", "top",
                   "review", "software", "service"]
    if intent == "BOFU":
        for bw in buyer_words:
            if bw in kw_lower:
                return "High"
        return "High"  # all BOFU default to High
    elif intent == "MOFU" and clicks >= 50:
        return "Medium"
    elif intent == "MOFU":
        return "Medium"
    else:
        return "Low"


def score_commercial(potential: str) -> int:
    return {"High": 10, "Medium": 6, "Low": 2}.get(potential, 6)


def score_kd() -> int:
    return 5  # no SEMrush data


def compute_priority(score: int) -> str:
    if score >= 80:
        return "Critical"
    elif score >= 65:
        return "High"
    elif score >= 50:
        return "Medium"
    return "Low"


def compute_recommendation(page: str, position: int, intent: str) -> str:
    has_page = bool(page and page.strip())
    if has_page and position <= 10 and intent in ("BOFU", "MOFU"):
        return "Improve Existing"
    elif has_page and 11 <= position <= 20:
        return "Expand Existing"
    elif not has_page:
        return "Create New Content"
    return "Improve Existing"


def build_reason(keyword: str, page: str, position: int, impressions: int,
                 intent: str, score: int, recommendation: str,
                 commercial: str) -> str:
    parts = []
    if recommendation == "Improve Existing":
        parts.append(f"Existing page ranks at position {position}")
        parts.append(f"with {impressions} monthly impressions")
    elif recommendation == "Expand Existing":
        parts.append(f"Page ranks at position {position} (positions 11-20)")
        parts.append(f"has {impressions} impressions — room to climb")
    else:
        parts.append(f"No existing page for this keyword")
        parts.append(f"{impressions} monthly impressions going uncaptured")

    parts.append(f"{intent} intent with {commercial.lower()} commercial potential")
    parts.append(f"Score: {score}/100")
    return ". ".join(parts) + "."


# ── Main analysis ────────────────────────────────────────────────────────────

def analyze_stage1a(rows: List[Dict]) -> Dict[str, Any]:
    """
    Run Stage 1A analysis on GSC CSV rows.
    Pure Python — no LLM calls. Returns the exact same JSON format.
    """
    total_rows = len(rows)
    opportunities = []
    excluded = []

    for row in rows:
        # Parse fields with flexible column names
        keyword = (row.get("query") or row.get("Query") or row.get("keyword") or "").strip()
        page = (row.get("page") or row.get("Page") or "").strip()
        clicks_str = str(row.get("clicks") or row.get("Clicks") or 0)
        impressions_str = str(row.get("impressions") or row.get("Impressions") or 0)
        position_str = str(row.get("position") or row.get("Position") or 0)
        ctr_str = str(row.get("ctr") or row.get("CTR") or "0")

        # Parse numeric values
        try:
            clicks = int(float(clicks_str))
        except (ValueError, TypeError):
            clicks = 0
        try:
            impressions = int(float(impressions_str))
        except (ValueError, TypeError):
            impressions = 0
        try:
            position = int(float(position_str))
        except (ValueError, TypeError):
            position = 0

        # Filter: position 3-20 AND impressions >= 50
        if not keyword:
            excluded.append({"keyword": keyword or "(empty)", "reason": "empty keyword"})
            continue
        if not (3 <= position <= 20):
            excluded.append({"keyword": keyword, "reason": f"position {position} outside 3-20"})
            continue
        if impressions < 50:
            excluded.append({"keyword": keyword, "reason": f"impressions {impressions} below 50"})
            continue

        # Classify
        intent = classify_intent(keyword)
        commercial = classify_commercial_potential(keyword, intent, clicks)

        # Score
        s_existing = score_existing_page(page)
        s_position = score_position(position)
        s_impressions = score_impressions(impressions)
        s_intent = score_intent(intent)
        s_commercial = score_commercial(commercial)
        s_kd = score_kd()
        total_score = s_existing + s_position + s_impressions + s_intent + s_commercial + s_kd

        priority = compute_priority(total_score)
        recommendation = compute_recommendation(page, position, intent)
        reason = build_reason(keyword, page, position, impressions, intent,
                              total_score, recommendation, commercial)

        # Format CTR
        try:
            ctr_val = float(ctr_str)
            if ctr_val < 1:
                ctr_display = f"{ctr_val * 100:.1f}%"
            else:
                ctr_display = f"{ctr_val:.1f}%"
        except (ValueError, TypeError):
            ctr_display = f"{ctr_str}%"

        opportunities.append({
            "priority": priority,
            "keyword": keyword,
            "page": page,
            "position": position,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr_display,
            "intent": intent,
            "commercial_potential": commercial,
            "score": total_score,
            "recommendation": recommendation,
            "reason": reason,
            "approval_status": "needs_review",
        })

    # Deduplicate by keyword (case-insensitive), keep highest score
    seen = {}
    for opp in opportunities:
        key = opp["keyword"].lower()
        if key not in seen or opp["score"] > seen[key]["score"]:
            seen[key] = opp
    opportunities = list(seen.values())

    # Sort by score descending
    opportunities.sort(key=lambda o: o["score"], reverse=True)

    # Summary
    critical = sum(1 for o in opportunities if o["priority"] == "Critical")
    high = sum(1 for o in opportunities if o["priority"] == "High")

    return {
        "status": "success",
        "summary": {
            "rows_processed": total_rows,
            "opportunities_found": len(opportunities),
            "top_opportunities": critical + high,
        },
        "outputs": {
            "csv_file": "outputs/stage_1a_existing_page_opportunities.csv",
            "approval_queue": "outputs/stage_1a_approval_queue.yaml",
            "report": "reports/stage_1a_existing_page_opportunities.md",
        },
        "opportunities": opportunities,
        "excluded": excluded,
    }


# ── Async wrapper for backward compatibility ────────────────────────────────

async def hermes_analyze_stage1a(rows: List[Dict]) -> Dict[str, Any]:
    """Async wrapper — runs synchronous analysis (fast, no I/O)."""
    return analyze_stage1a(rows)


# ── CLI test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_rows = [
        {"query": "clinic management software", "page": "/clinic-software", "clicks": "120", "impressions": "2450", "ctr": "4.9", "position": "8"},
        {"query": "best clinic software", "page": "/clinic-software-comparison", "clicks": "180", "impressions": "4200", "ctr": "4.3", "position": "4"},
        {"query": "ehr pricing", "page": "/ehr-pricing", "clicks": "60", "impressions": "950", "ctr": "6.3", "position": "3"},
    ]
    result = analyze_stage1a(test_rows)
    print(json.dumps(result, indent=2))
