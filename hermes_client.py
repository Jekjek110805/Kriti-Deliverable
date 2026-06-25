#!/usr/bin/env python3
"""
hermes_client.py -- Pure Python Stage 1A + Stage 1B analysis engine.
Deterministic rule-based scoring (no LLM calls).
Returns results in the exact same format the frontend expects.

Stage 1A: Opportunity detection (position, intent, scoring)
Stage 1B: Implementation recommendation (where should this keyword live?)

Hermes (LLM) is NOT used here.
Hermes is reserved for: executive narratives, audience questions, content explanations.
"""
import json
import os
import re
import math
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


# ── Stage 1B: Implementation Recommendation ─────────────────────────────────

# Content type signals — keyword patterns that indicate page type
BLOG_SIGNALS = [
    "what is", "how to", "why", "guide", "tutorial", "tips", "examples",
    "overview", "history of", "definition", "meaning", "introduction",
    "benefits of", "mistakes", "strategies", "checklist", "comparison",
    "versus", "vs", "review", "explained", "understanding",
]

LANDING_SIGNALS = [
    "pricing", "cost", "buy", "purchase", "demo", "trial", "sign up",
    "signup", "quote", "best", "top", "software", "service", "provider",
    "near me", "for clinics", "for accountants", "for small business",
    "alternative", "compare", "solution", "platform", "tool",
]

# Signals that a page already satisfies the keyword (no change needed)
NO_CHANGE_SIGNALS = [
    "removal", "delete", "unsubscribe", "cancel", "refund",
    "complaint", "feedback", "support", "help", "contact",
    "about us", "terms", "privacy", "login", "sitemap",
]


def classify_content_type(keyword: str, intent: str) -> str:
    """Determine whether a keyword belongs on a Blog or Landing Page.

    Returns 'Blog' or 'Landing Page'.
    """
    kw_lower = keyword.lower()

    blog_score = sum(1 for s in BLOG_SIGNALS if s in kw_lower)
    landing_score = sum(1 for s in LANDING_SIGNALS if s in kw_lower)

    # BOFU with buyer words → Landing Page
    if intent == "BOFU" and landing_score > 0:
        return "Landing Page"
    # TOFU with informational words → Blog
    if intent == "TOFU" and blog_score > 0:
        return "Blog"
    # MOFU: lean toward blog unless strong commercial signal
    if intent == "MOFU" and landing_score >= 2:
        return "Landing Page"
    if blog_score > landing_score:
        return "Blog"
    if landing_score > blog_score:
        return "Landing Page"
    # Default: MOFU → Blog, BOFU → Landing, TOFU → Blog
    if intent == "BOFU":
        return "Landing Page"
    return "Blog"


def compute_confidence(score: int, position: int, impressions: int, intent: str) -> str:
    """Compute confidence level for a recommendation.

    Returns 'high' / 'medium' / 'low' as a percentage string.
    """
    confidence = 50.0

    # Score contribution (0-30 points)
    if score >= 80:
        confidence += 30
    elif score >= 65:
        confidence += 22
    elif score >= 50:
        confidence += 14
    else:
        confidence += 5

    # Position certainty (0-25 points)
    if 3 <= position <= 5:
        confidence += 25  # very certain — close to top
    elif 6 <= position <= 10:
        confidence += 20
    elif 11 <= position <= 15:
        confidence += 12
    else:
        confidence += 5

    # Impressions volume (0-15 points)
    if impressions >= 1000:
        confidence += 15
    elif impressions >= 500:
        confidence += 10
    elif impressions >= 200:
        confidence += 5
    else:
        confidence += 2

    # Intent clarity (0-10 points)
    if intent == "BOFU":
        confidence += 10
    elif intent == "MOFU":
        confidence += 6
    else:
        confidence += 3

    # Cap at 98% (never 100% — always room for human judgment)
    confidence = min(confidence, 98.0)
    # Floor at 30%
    confidence = max(confidence, 30.0)

    pct = round(confidence)
    if pct >= 75:
        return f"{pct}% (high)"
    elif pct >= 50:
        return f"{pct}% (medium)"
    return f"{pct}% (low)"


def compute_stage1b_recommendation(keyword: str, page: str, position: int,
                                   intent: str, commercial: str,
                                   clicks: int, impressions: int) -> Dict[str, Any]:
    """Stage 1B: Determine implementation recommendation for a keyword.

    Returns dict with: recommendation, content_type, confidence, reason, next_action.
    """
    has_page = bool(page and page.strip())
    kw_lower = keyword.lower()

    # Check if page already satisfies keyword (no change needed)
    no_change_signal = any(s in kw_lower for s in NO_CHANGE_SIGNALS)
    page_likely_satisfies = has_page and position <= 5 and intent in ("BOFU", "MOFU") and clicks >= 50

    if no_change_signal and has_page:
        recommendation = "No Change"
        reason = f"Existing page at position {position} already satisfies this keyword intent. No optimization needed."
    elif page_likely_satisfies and impressions >= 500:
        recommendation = "No Change"
        reason = f"Page ranks well at position {position} with {impressions} impressions and {clicks} clicks. Already satisfies intent."
    elif has_page and position <= 10 and intent in ("BOFU", "MOFU"):
        recommendation = "Improve Existing Page"
        reason = f"Existing page at position {position} can be optimized to better match {intent} intent and capture more clicks."
    elif has_page and 11 <= position <= 20:
        recommendation = "Improve Existing Page"
        reason = f"Page at position {position} needs content depth improvements to climb into top 10."
    elif has_page and position > 20:
        recommendation = "Create New Content"
        reason = f"Existing page ranks too low (position {position}). A dedicated new page would perform better."
    else:
        recommendation = "Create New Content"
        reason = f"No existing page targets this keyword. New content needed to capture {impressions} monthly impressions."

    content_type = classify_content_type(keyword, intent)
    confidence = compute_confidence(
        score=0,  # We compute confidence from raw signals here
        position=position,
        impressions=impressions,
        intent=intent,
    )

    # Build next action
    if recommendation == "No Change":
        next_action = "No action required. Monitor periodically."
    elif recommendation == "Improve Existing Page":
        next_action = f"Optimize {page or 'existing page'} — strengthen content, add CTAs, improve internal links."
    else:
        ct = content_type
        next_action = f"Create a new {ct} targeting '{keyword}'. Assign to content team."

    return {
        "recommendation": recommendation,
        "content_type": content_type,
        "confidence": confidence,
        "reason": reason,
        "next_action": next_action,
    }


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

        # Stage 1B: Implementation recommendation
        stage1b = compute_stage1b_recommendation(
            keyword=keyword, page=page, position=position,
            intent=intent, commercial=commercial,
            clicks=clicks, impressions=impressions,
        )

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
            "recommendation": stage1b["recommendation"],
            "content_type": stage1b["content_type"],
            "confidence": stage1b["confidence"],
            "reason": stage1b["reason"],
            "next_action": stage1b["next_action"],
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


# ── Keyword Gap Analysis (Stage 1B feedback #4) ──────────────────────────────

def analyze_keyword_gaps(keywords: List[str], existing_pages: List[Dict]) -> Dict[str, Any]:
    """Identify keyword gaps — topics not covered by existing pages.

    Args:
        keywords: List of all keywords from GSC data
        existing_pages: List of dicts with 'url' and 'ranking_keywords' keys

    Returns:
        Dict with gap analysis results.
    """
    # Extract all keywords that have existing page coverage
    covered_keywords = set()
    for page in existing_pages:
        for kw in page.get("ranking_keywords", []):
            covered_keywords.add(kw.lower())

    # Find uncovered keywords from the GSC data
    uncovered = []
    for kw in keywords:
        if kw.lower() not in covered_keywords:
            uncovered.append(kw)

    # Group uncovered keywords by intent for pattern detection
    gap_by_intent = {"BOFU": [], "MOFU": [], "TOFU": []}
    for kw in uncovered:
        intent = classify_intent(kw)
        gap_by_intent[intent].append(kw)

    # Identify topical clusters (simple: group by shared words)
    topical_clusters = {}
    for kw in uncovered:
        words = kw.lower().split()
        # Use the most meaningful word (skip common words)
        skip_words = {"the", "a", "an", "for", "in", "on", "to", "of", "and", "or"}
        meaningful = [w for w in words if w not in skip_words and len(w) > 3]
        if meaningful:
            key = sorted(meaningful)[0]  # First alphabetically as cluster key
            if key not in topical_clusters:
                topical_clusters[key] = []
            topical_clusters[key].append(kw)

    return {
        "total_keywords_analyzed": len(keywords),
        "covered_count": len(covered_keywords),
        "uncovered_count": len(uncovered),
        "coverage_pct": round(len(covered_keywords) / max(len(keywords), 1) * 100, 1),
        "uncovered_keywords": uncovered,
        "gaps_by_intent": gap_by_intent,
        "topical_clusters": topical_clusters,
        "recommendation": _gap_recommendation(len(uncovered), len(keywords)),
    }


def _gap_recommendation(uncovered_count: int, total: int) -> str:
    """Generate a recommendation based on gap analysis."""
    if total == 0:
        return "No keywords to analyze."
    pct = uncovered_count / total * 100
    if pct >= 60:
        return f"Large content gap ({pct:.0f}% uncovered). Prioritize new content creation for top uncovered keywords."
    elif pct >= 30:
        return f"Moderate content gap ({pct:.0f}% uncovered). Consider creating new pages for high-value uncovered keywords."
    elif pct > 0:
        return f"Small content gap ({pct:.0f}% uncovered). Focus on optimizing existing pages for remaining gaps."
    return "Full coverage. All keywords have matching existing pages."


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
