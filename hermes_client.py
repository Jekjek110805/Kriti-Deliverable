#!/usr/bin/env python3
"""
hermes_client.py -- Stage 1A + Stage 1B analysis engine.
Deterministic rule-based scoring (no LLM calls).
Returns results in the exact same format the frontend expects.

Stage 1B additions:
  - "No Change" recommendation for well-performing pages
  - Content type classification (Existing/New Blog or Landing Page)
  - AI confidence score per opportunity
  - Gap keyword analysis (position 21-50 with significant impressions)
"""
import json
import os
from typing import Any, Dict, List

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

BLOG_URL_SIGNALS = [
    "/blog", "/article", "/post", "/guide", "/how-to", "/news",
    "/resource", "/learn", "/insights", "/tips",
]

INFORMATIONAL_SIGNALS = [
    "how to", "guide", "tips", "tutorial", "what is", "why", "strategies",
    "checklist", "mistakes", "benefits", "examples", "learn", "understand",
    "introduction", "overview",
]


def classify_intent(keyword: str) -> str:
    kw_lower = keyword.lower()
    for b in BOFU_KEYWORDS:
        if b in kw_lower:
            return "BOFU"
    for t in TOFU_KEYWORDS:
        if t in kw_lower:
            return "TOFU"
    for m in MOFU_KEYWORDS:
        if m in kw_lower:
            return "MOFU"
    return "MOFU"


# ── Stage 1B: Content type & confidence ─────────────────────────────────────

def classify_content_type(keyword: str, page: str, recommendation: str, intent: str) -> str:
    """Determine whether this keyword belongs in a Blog or Landing Page."""
    if recommendation in ("No Change", "Improve Existing", "Expand Existing"):
        page_lower = (page or "").lower()
        if any(sig in page_lower for sig in BLOG_URL_SIGNALS):
            return "Existing Blog"
        return "Existing Landing Page"
    # Creating new content
    kw_lower = keyword.lower()
    if intent == "TOFU":
        return "New Blog"
    if intent == "BOFU":
        return "New Landing Page"
    # MOFU — check informational signals to distinguish blog from landing page
    for sig in INFORMATIONAL_SIGNALS:
        if sig in kw_lower:
            return "New Blog"
    return "New Landing Page"


def compute_confidence(score: int, has_page: bool, impressions: int,
                       recommendation: str, is_gap: bool) -> int:
    """Confidence percentage (45–97) for the recommendation."""
    if score >= 80:
        base = 88
    elif score >= 65:
        base = 78
    elif score >= 50:
        base = 68
    else:
        base = 55

    if recommendation == "No Change":
        base += 7
    elif is_gap:
        base -= 8

    if has_page and impressions >= 1000:
        base += 5
    elif has_page and impressions >= 500:
        base += 3
    elif not has_page and impressions < 100:
        base -= 5

    return min(max(base, 45), 97)


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_existing_page(page: str) -> int:
    return 25 if page and page.strip() else 0


def score_position(position: int) -> int:
    if 1 <= position <= 5:
        return 20
    elif 6 <= position <= 10:
        return 18
    elif 11 <= position <= 20:
        return 12
    elif 21 <= position <= 50:
        return 4  # gap — low score but still included
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
    if intent == "BOFU":
        return "High"
    elif intent == "MOFU":
        return "Medium"
    return "Low"


def score_commercial(potential: str) -> int:
    return {"High": 10, "Medium": 6, "Low": 2}.get(potential, 6)


def score_kd() -> int:
    return 5  # no SEMrush data available


def compute_priority(score: int) -> str:
    if score >= 80:
        return "Critical"
    elif score >= 65:
        return "High"
    elif score >= 50:
        return "Medium"
    return "Low"


def compute_recommendation(page: str, position: int, intent: str,
                           ctr_val: float = 0.0) -> str:
    """
    Stage 1B recommendation logic.
    No Change     → page already performs well (pos 1-5, CTR ≥ 3%, BOFU/MOFU)
    Improve       → existing page, pos 1-10, below No Change threshold
    Expand        → existing page, pos 11-20
    Create New    → no page found OR gap keyword (pos 21-50)
    """
    has_page = bool(page and page.strip())
    if not has_page or position > 20:
        return "Create New Content"
    # Top 2 positions always "No Change" — already winning
    if position <= 2:
        return "No Change"
    if position <= 5 and intent in ("BOFU", "MOFU") and ctr_val >= 3.0:
        return "No Change"
    if position <= 10 and intent in ("BOFU", "MOFU"):
        return "Improve Existing"
    if 11 <= position <= 20:
        return "Expand Existing"
    return "Improve Existing"


def build_reason(keyword: str, page: str, position: int, impressions: int,
                 intent: str, score: int, recommendation: str,
                 commercial: str, content_type: str = "",
                 is_gap: bool = False) -> str:
    parts = []
    if recommendation == "No Change":
        parts.append(f"Existing page ranks at position {position} and is already performing well")
        parts.append(f"{impressions:,} monthly impressions with strong CTR")
        parts.append("No optimization required at this time")
    elif recommendation == "Improve Existing":
        parts.append(f"Existing page ranks at position {position}")
        parts.append(f"with {impressions:,} monthly impressions")
        parts.append(f"Optimize on-page elements and content depth to push into top 5")
    elif recommendation == "Expand Existing":
        parts.append(f"Page ranks at position {position} (11–20 range)")
        parts.append(f"{impressions:,} impressions available — deeper content can push it to page 1")
    elif is_gap:
        parts.append(f"Gap keyword: site appears at position {position} but ranks poorly")
        parts.append(f"{impressions:,} impressions going uncaptured")
        parts.append(f"A dedicated {content_type} would fully satisfy this demand")
    else:
        parts.append(f"No existing page targets this keyword")
        parts.append(f"{impressions:,} monthly impressions going uncaptured")
        parts.append(f"Create a {content_type} to capture this demand")

    parts.append(f"{intent} intent with {commercial.lower()} commercial potential")
    parts.append(f"Score: {score}/100")
    return ". ".join(parts) + "."


# ── Main analysis ────────────────────────────────────────────────────────────

def analyze_stage1a(rows: List[Dict]) -> Dict[str, Any]:
    """
    Stage 1A + Stage 1B analysis on GSC CSV rows.
    Pure Python, no LLM calls. Expands to position 50 to surface gap keywords.
    """
    total_rows = len(rows)
    opportunities = []
    excluded = []

    for row in rows:
        keyword = (row.get("query") or row.get("Query") or row.get("keyword") or "").strip()
        page = (row.get("page") or row.get("Page") or "").strip()
        clicks_str = str(row.get("clicks") or row.get("Clicks") or 0)
        impressions_str = str(row.get("impressions") or row.get("Impressions") or 0)
        position_str = str(row.get("position") or row.get("Position") or 0)
        ctr_str = str(row.get("ctr") or row.get("CTR") or "0")

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
        try:
            ctr_raw = float(ctr_str)
            ctr_val = ctr_raw * 100 if ctr_raw < 1 else ctr_raw
        except (ValueError, TypeError):
            ctr_val = 0.0

        if not keyword:
            excluded.append({"keyword": "(empty)", "reason": "empty keyword"})
            continue

        is_gap = position > 20

        if position < 1 or position > 50:
            excluded.append({"keyword": keyword, "reason": f"position {position} outside 1-50"})
            continue

        # Gap keywords need stronger signal to be worth surfacing
        min_impressions = 300 if is_gap else 50
        if impressions < min_impressions:
            excluded.append({"keyword": keyword, "reason": f"impressions {impressions} below {min_impressions}"})
            continue

        intent = classify_intent(keyword)
        commercial = classify_commercial_potential(keyword, intent, clicks)

        s_existing = score_existing_page(page)
        s_position = score_position(position)
        s_impressions = score_impressions(impressions)
        s_intent = score_intent(intent)
        s_commercial = score_commercial(commercial)
        s_kd = score_kd()
        total_score = (s_existing + s_position + s_impressions +
                       s_intent + s_commercial + s_kd)

        priority = compute_priority(total_score)
        recommendation = compute_recommendation(page, position, intent, ctr_val)
        content_type = classify_content_type(keyword, page, recommendation, intent)
        confidence = compute_confidence(total_score, bool(page), impressions,
                                        recommendation, is_gap)
        reason = build_reason(keyword, page, position, impressions, intent,
                              total_score, recommendation, commercial,
                              content_type, is_gap)

        ctr_display = f"{ctr_val:.1f}%"

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
            "content_type": content_type,
            "confidence": confidence,
            "reason": reason,
            "is_gap": is_gap,
            "approval_status": "needs_review",
        })

    # Deduplicate by keyword (case-insensitive), keep highest score
    seen: Dict[str, Any] = {}
    for opp in opportunities:
        key = opp["keyword"].lower()
        if key not in seen or opp["score"] > seen[key]["score"]:
            seen[key] = opp
    opportunities = list(seen.values())
    opportunities.sort(key=lambda o: o["score"], reverse=True)

    no_change = sum(1 for o in opportunities if o["recommendation"] == "No Change")
    improve = sum(1 for o in opportunities if o["recommendation"] in ("Improve Existing", "Expand Existing"))
    create_new = sum(1 for o in opportunities if o["recommendation"] == "Create New Content")
    gap_count = sum(1 for o in opportunities if o.get("is_gap"))
    critical = sum(1 for o in opportunities if o["priority"] == "Critical")
    high = sum(1 for o in opportunities if o["priority"] == "High")

    return {
        "status": "success",
        "summary": {
            "rows_processed": total_rows,
            "opportunities_found": len(opportunities),
            "top_opportunities": critical + high,
            "no_change": no_change,
            "improve_existing": improve,
            "create_new": create_new,
            "gap_keywords": gap_count,
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
        {"query": "what is ehr", "page": "", "clicks": "5", "impressions": "800", "ctr": "0.6", "position": "34"},
        {"query": "removal reviews", "page": "/removal-reviews", "clicks": "220", "impressions": "3100", "ctr": "7.1", "position": "2"},
    ]
    result = analyze_stage1a(test_rows)
    print(json.dumps(result, indent=2))
