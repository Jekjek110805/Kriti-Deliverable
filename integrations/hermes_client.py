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
import re
from typing import Any, Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
EXISTING_PAGES_FILE = os.path.join(DATA_DIR, "existing_pages.json")


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
                       recommendation: str, is_gap: bool, clicks: int = 0) -> int:
    """Confidence percentage (45–97) for the recommendation."""
    if score >= 85:
        base = 88
    elif score >= 70:
        base = 78
    elif score >= 55:
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
    elif impressions >= 100:
        return 5
    elif impressions >= 50:
        return 3
    elif impressions >= 10:
        return 1
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


def score_clicks(clicks: int) -> int:
    """Score click-through signal (0-10). Rewards keywords that already
    prove users want them; penalises zero-click high-impression rows."""
    if clicks >= 100:
        return 10
    elif clicks >= 50:
        return 8
    elif clicks >= 20:
        return 6
    elif clicks >= 10:
        return 4
    elif clicks >= 1:
        return 2
    return 0  # zero clicks — no real demand signal


def compute_priority(score: int) -> str:
    if score >= 85:
        return "Critical"
    elif score >= 70:
        return "High"
    elif score >= 55:
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


# ── Landing page suggestion & matching (deterministic) ──────────────────────

# Common URL stop-words stripped from generated slugs so paths stay clean.
_SLUG_STOPWORDS = {"a", "an", "the", "for", "to", "of", "and", "in", "on", "is"}


def slugify(text: str) -> str:
    """Deterministic kebab-case slug for a keyword (no AI, fully predictable)."""
    words = re.sub(r"[^a-z0-9\s-]", "", (text or "").lower()).split()
    words = [w for w in words if w not in _SLUG_STOPWORDS] or words
    slug = "-".join(words)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "page"


def _site_base_url() -> str:
    """Best-effort absolute site origin for resolving relative landing pages.

    Reads the configured GSC property and normalises it to an https origin:
      https://example.com/      -> https://example.com
      sc-domain:example.com     -> https://example.com
    Returns "" when no property is configured (relative paths stay relative).
    """
    try:
        from integrations.gsc_client import GSCClient
        raw = (GSCClient().site_url or "").strip()
    except Exception:
        raw = ""
    if not raw:
        return ""
    if raw.startswith("sc-domain:"):
        return "https://" + raw[len("sc-domain:"):].strip().strip("/")
    return raw.rstrip("/")


def absolutize(path_or_url: str, base: str) -> str:
    """Turn a page path into a clickable absolute URL when possible."""
    if not path_or_url:
        return ""
    if re.match(r"^https?://", path_or_url, re.IGNORECASE):
        return path_or_url
    if not base:
        return ""  # cannot build an absolute URL without a site domain
    return base.rstrip("/") + "/" + path_or_url.lstrip("/")


def load_existing_pages() -> List[Dict]:
    """Load the known site pages used to match keywords to real landing pages."""
    try:
        with open(EXISTING_PAGES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def suggest_landing_page(keyword: str, intent: str, content_type: str) -> str:
    """Deterministically suggest an ideal landing-page path for a keyword.

    Section is chosen from intent / content type — no LLM involved:
      • Blog content        → /blog/<slug>
      • BOFU (commercial)   → /solutions/<slug>
      • everything else     → /services/<slug>
    """
    slug = slugify(keyword)
    if "Blog" in (content_type or ""):
        return f"/blog/{slug}"
    if intent == "BOFU":
        return f"/solutions/{slug}"
    return f"/services/{slug}"


def match_existing_page(keyword: str, gsc_page: str, existing_pages: List[Dict]) -> str:
    """Return the existing landing page that best matches this keyword, or "".

    Match priority (deterministic):
      1. The page GSC already ranks for this query (the export's Page column).
      2. A known site page whose ranking_keywords contains the keyword.
      3. A known site page whose URL slug contains the keyword slug.
    """
    if gsc_page and gsc_page.strip():
        return gsc_page.strip()

    kw = (keyword or "").lower().strip()
    for page in existing_pages:
        ranking = [str(k).lower().strip() for k in page.get("ranking_keywords", [])]
        if kw in ranking:
            return page.get("url", "")

    kw_slug = slugify(keyword)
    for page in existing_pages:
        url = page.get("url", "")
        if kw_slug and kw_slug in slugify(url):
            return url
    return ""


def resolve_landing_page(keyword: str, gsc_page: str, intent: str,
                         content_type: str, existing_pages: List[Dict],
                         base_url: str = "") -> Dict[str, str]:
    """Combine suggestion + matching into the final landing-page decision.

    ``landing_page``     human-readable path/URL of the chosen page.
    ``landing_page_url`` absolute, clickable URL (resolved against base_url for
                          relative paths); "" when it cannot be made absolute.
    """
    suggested = suggest_landing_page(keyword, intent, content_type)
    matched = match_existing_page(keyword, gsc_page, existing_pages)
    if matched:
        return {
            "landing_page": matched,
            "landing_page_url": absolutize(matched, base_url),
            "landing_page_type": "existing",
            "suggested_landing_page": suggested,
            "matched_existing_page": matched,
        }
    return {
        "landing_page": suggested,
        "landing_page_url": absolutize(suggested, base_url),
        "landing_page_type": "suggested_new",
        "suggested_landing_page": suggested,
        "matched_existing_page": "",
    }


# ── Main analysis ────────────────────────────────────────────────────────────

def analyze_stage1a(rows: List[Dict]) -> Dict[str, Any]:
    """
    Stage 1A + Stage 1B analysis on GSC CSV rows.
    Pure Python, no LLM calls. Expands to position 50 to surface gap keywords.
    """
    total_rows = len(rows)
    opportunities = []
    excluded = []
    existing_pages = load_existing_pages()
    site_base = _site_base_url()

    for row in rows:
        keyword = (row.get("query") or row.get("Query") or row.get("keyword") or "").strip()
        page = (row.get("page") or row.get("Page") or "").strip()
        clicks_str = str(row.get("clicks") or row.get("Clicks") or 0)
        impressions_str = str(row.get("impressions") or row.get("Impressions") or 0)
        position_str = str(row.get("position") or row.get("Position") or 0)
        # GSC exports CTR as "2.33%" (already a percent) or "0.0233" (fraction).
        # Remember whether a % sign was present so we don't double-scale: a value
        # written with "%" is already a percentage (e.g. "0.6%" = 0.6%), while a
        # bare fraction < 1 (e.g. "0.006") must be multiplied by 100.
        ctr_raw_str = str(row.get("ctr") or row.get("CTR") or "0").strip()
        ctr_had_percent = "%" in ctr_raw_str
        ctr_str = ctr_raw_str.replace("%", "").replace(",", "")

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
            if ctr_had_percent:
                ctr_val = ctr_raw  # already a percentage
            else:
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
        min_impressions = 100 if is_gap else 10
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
        s_clicks = score_clicks(clicks)
        total_score = (s_existing + s_position + s_impressions +
                       s_intent + s_commercial + s_kd + s_clicks)

        priority = compute_priority(total_score)
        recommendation = compute_recommendation(page, position, intent, ctr_val)
        content_type = classify_content_type(keyword, page, recommendation, intent)
        confidence = compute_confidence(total_score, bool(page), impressions,
                                        recommendation, is_gap, clicks)
        reason = build_reason(keyword, page, position, impressions, intent,
                              total_score, recommendation, commercial,
                              content_type, is_gap)

        ctr_display = f"{ctr_val:.1f}%"

        landing = resolve_landing_page(keyword, page, intent, content_type,
                                       existing_pages, site_base)

        opportunities.append({
            "priority": priority,
            "keyword": keyword,
            "page": page,  # raw GSC ranking URL (kept for backward compatibility)
            "landing_page": landing["landing_page"],
            "landing_page_url": landing["landing_page_url"],
            "landing_page_type": landing["landing_page_type"],
            "suggested_landing_page": landing["suggested_landing_page"],
            "matched_existing_page": landing["matched_existing_page"],
            "position": position,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr_display,
            "intent": intent,
            "commercial_potential": commercial,
            "score": total_score,
            "opportunity_score": total_score,  # alias per Stage 1 spec
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
