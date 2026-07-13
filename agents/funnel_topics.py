"""
funnel_topics.py -- Deterministic SEMrush keyword -> funnel topic engine.

Turns a SEMrush keyword-research export (Keyword, Intent, Volume, Keyword
Difficulty, CPC, SERP Features) into blog / landing-page TOPIC suggestions
grouped by marketing funnel stage (TOFU / MOFU / BOFU).

WHY this exists
---------------
The Discover upload flow is built for Google Search Console data (site
performance: query + page + clicks + impressions + position). A SEMrush
keyword-research export is a different kind of data -- it is about the *market*,
not the site -- so it has no landing pages to score. The old flow dead-ended
with a "landing pages not available" warning. The client's actual need is:

    "Give it my keyword file and it should suggest blogs & topics by funnel."

This module answers exactly that, from the file alone.

DESIGN
------
PURE PYTHON. No LLM, no network, no randomness. The same file produces the same
topics, scores and recommendations every run -- consistent with the Stage 1A
deterministic engine (see docs/Stage 1A - Problem Diagnosis (Hermes).md) and
important because a human approves these suggestions.

Funnel mapping (SEMrush Intent -> stage), the industry standard:
    Informational -> TOFU (awareness)
    Commercial    -> MOFU (consideration)
    Transactional -> BOFU (decision)
    Navigational  -> BOFU (brand / ready to act)
Multi-intent keywords ("Informational, Transactional") take the DEEPEST stage.

Existing-page awareness is optional. The SEMrush file carries no information
about the client's own site, so by default every topic is "New Blog" / "New
Landing Page". If a plain list of existing page URLs is supplied, topics whose
keywords clearly map to an existing page are upgraded to "Existing Blog" /
"Existing Landing Page" (improve it) or "No Action Required" (already covered).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ── Funnel model ──────────────────────────────────────────────────────────────
INTENT_STAGE = {
    "informational": "TOFU",
    "commercial": "MOFU",
    "transactional": "BOFU",
    "navigational": "BOFU",
}
STAGE_RANK = {"TOFU": 1, "MOFU": 2, "BOFU": 3}  # deeper in the funnel = higher

STAGE_META = {
    "TOFU": {
        "stage": "TOFU",
        "label": "Top of Funnel - Awareness",
        "intent": "Informational",
        "description": (
            "People learning about the topic. Educational blog content that "
            "builds trust and captures early demand."
        ),
    },
    "MOFU": {
        "stage": "MOFU",
        "label": "Middle of Funnel - Consideration",
        "intent": "Commercial",
        "description": (
            "People comparing options. Comparison, 'best' and review content "
            "that helps them shortlist a solution."
        ),
    },
    "BOFU": {
        "stage": "BOFU",
        "label": "Bottom of Funnel - Decision",
        "intent": "Transactional / Navigational",
        "description": (
            "People ready to act. Landing pages built to convert buyers who "
            "know what they want."
        ),
    },
}
STAGE_ORDER = ["TOFU", "MOFU", "BOFU"]


# ── Tokenisation helpers (deterministic) ──────────────────────────────────────
# Words dropped when deciding whether two keywords describe the SAME topic.
# These are locators / superlatives / glue words that create variants of one
# topic ("... near me", "best ...", "cheap ...") rather than new topics.
_CLUSTER_STOPWORDS = {
    "a", "an", "the", "of", "to", "in", "on", "for", "and", "or", "&",
    "my", "your", "with", "at", "by", "is", "are", "near", "me", "best",
    "top", "cheap", "cheapest", "affordable", "good", "great", "vs", "versus",
    "list", "local",
}

# Signals that push a MOFU/ambiguous topic toward a BLOG article.
_BLOG_SIGNALS = {
    "how", "what", "why", "when", "where", "guide", "tips", "ideas",
    "examples", "checklist", "benefits", "review", "reviews", "vs", "versus",
    "comparison", "compare", "start", "starting", "plan", "planning",
    "profitable", "profit", "steps", "tutorial", "explained",
}

# Signals that push a topic toward a LANDING page (buyer / transactional).
_LANDING_SIGNALS = {
    "sale", "buy", "price", "pricing", "cost", "quote", "quotes", "software",
    "services", "service", "company", "companies", "rental", "rent", "hire",
    "solutions", "solution", "provider", "providers", "near", "supplier",
    "suppliers", "insurance", "loan", "loans", "financing",
}

# Very light singulariser -- deterministic suffix rules, no external data.
def _singularise(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("ses"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t]


def _topic_key(keyword: str) -> str:
    """Order-independent signature of a keyword's *significant* tokens.

    Two keywords sharing the same key describe the same topic:
      "self storage business for sale"        -> business sale self storage
      "self storage businesses for sale"       -> business sale self storage
      "self storage business for sale near me" -> business sale self storage
    while "self storage business plan" (has 'plan') stays a distinct topic.
    """
    sig = {
        _singularise(t)
        for t in _tokens(keyword)
        if t not in _CLUSTER_STOPWORDS and not t.isdigit()
    }
    if not sig:  # keyword was entirely stopwords -- fall back to raw tokens
        sig = {_singularise(t) for t in _tokens(keyword)}
    return " ".join(sorted(sig))


# ── Numeric parsing ───────────────────────────────────────────────────────────
def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    text = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(text) if text not in ("", "-", ".") else 0.0
    except ValueError:
        return 0.0


def _to_int(value: Any) -> int:
    return int(round(_to_float(value)))


# ── Intent -> funnel stage ────────────────────────────────────────────────────
# SEMrush leaves the Intent column blank for most keywords (only a fraction are
# classified). Rather than dumping every blank into one stage, we INFER the stage
# from the keyword's own wording + SERP features when SEMrush gives us nothing.
# Deterministic, precedence BOFU > MOFU > TOFU.
_BOFU_PHRASES = ("for sale", "for rent", "for lease", "near me", "to buy")
_BOFU_TOKENS = {
    "buy", "sale", "price", "pricing", "quote", "quotes", "cost", "costs",
    "rent", "rental", "hire", "lease", "cheapest", "deal", "deals",
}
_MOFU_TOKENS = {
    "best", "top", "review", "reviews", "vs", "versus", "comparison", "compare",
    "software", "companies", "company", "providers", "provider", "services",
    "service", "solutions", "solution", "alternatives", "alternative",
}
_TOFU_TOKENS = {
    "how", "what", "why", "when", "where", "guide", "ideas", "tips", "plan",
    "planning", "start", "starting", "requirements", "profitable", "profit",
    "examples", "meaning", "definition", "tutorial", "steps", "checklist",
    "benefits", "explained", "process",
}
# SERP features that hint at commercial/transactional demand.
_BOFU_SERP = {"local pack", "ads bottom", "ads top", "popular products", "shopping"}
_MOFU_SERP = {"reviews", "things to know", "discussions and forums"}


def classify_stage(intent: str, keyword: str = "", serp_features: str = ""):
    """Return (stage, source).

    source is 'semrush' when SEMrush supplied the intent, 'inferred' when we
    derived it from the keyword/SERP wording, or 'default' when nothing matched.
    Multi-value SEMrush intent takes the DEEPEST stage.
    """
    parts = [p.strip().lower() for p in re.split(r"[,/;|]", intent or "") if p.strip()]
    stages = [INTENT_STAGE[p] for p in parts if p in INTENT_STAGE]
    if stages:
        return max(stages, key=lambda s: STAGE_RANK[s]), "semrush"

    low = (keyword or "").lower()
    tokens = set(_tokens(keyword))
    serp = {f.strip().lower() for f in re.split(r",\s*", serp_features or "") if f.strip()}
    if any(p in low for p in _BOFU_PHRASES) or (tokens & _BOFU_TOKENS) or (serp & _BOFU_SERP):
        return "BOFU", "inferred"
    if (tokens & _MOFU_TOKENS) or (serp & _MOFU_SERP):
        return "MOFU", "inferred"
    if tokens & _TOFU_TOKENS:
        return "TOFU", "inferred"
    return "TOFU", "default"  # ambiguous long-tail -> awareness/blog catch-all


# ── Content type + title (deterministic templates) ────────────────────────────
def _content_type(stage: str, topic_tokens: set) -> str:
    if topic_tokens & _BLOG_SIGNALS:
        return "Blog"
    if stage == "TOFU":
        return "Blog"
    if stage == "BOFU":
        return "Landing Page"
    # MOFU with no explicit blog signal but buyer signals -> Landing Page
    if topic_tokens & _LANDING_SIGNALS:
        return "Landing Page"
    return "Blog"


def _title(head_keyword: str, stage: str, content_type: str) -> str:
    kw = re.sub(r"\s+", " ", (head_keyword or "").strip())
    low = kw.lower()
    tc = kw.title()
    if low.startswith(("how to", "how ", "what ", "why ", "when ", "where ")):
        return tc  # already a natural headline / question
    if content_type == "Blog":
        if stage == "TOFU":
            return f"{tc}: A Complete Guide"
        return f"{tc}: What to Know Before You Choose"  # MOFU consideration
    # Landing page headline
    if stage == "BOFU":
        return tc
    return tc


# ── Existing-page matching (optional) ─────────────────────────────────────────
def _match_existing(topic_key_tokens: set,
                    existing: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the best existing page whose URL/title covers the topic, if any."""
    best = None
    best_overlap = 0.0
    for page in existing or []:
        blob = f"{page.get('url', '')} {page.get('title', '')}"
        page_tokens = {_singularise(t) for t in _tokens(blob)}
        if not page_tokens or not topic_key_tokens:
            continue
        overlap = len(topic_key_tokens & page_tokens) / len(topic_key_tokens)
        if overlap > best_overlap:
            best_overlap, best = overlap, page
    if best and best_overlap >= 0.6:  # topic is largely covered by this page
        return {"page": best, "coverage": round(best_overlap, 2)}
    return None


# ── Scoring (deterministic 0-100) ─────────────────────────────────────────────
def _volume_norm(total_volume: int) -> float:
    # log scale: 10 -> ~0.33, 1k -> ~0.75, 10k+ -> ~1.0
    if total_volume <= 0:
        return 0.0
    import math
    return min(1.0, math.log10(total_volume + 1) / 4.0)


def _score(total_volume: int, avg_kd: float, avg_cpc: float, cluster_size: int) -> int:
    volume = _volume_norm(total_volume)
    ease = (100.0 - min(100.0, max(0.0, avg_kd))) / 100.0
    value = min(1.0, avg_cpc / 10.0)
    breadth = min(1.0, cluster_size / 10.0)
    raw = 0.45 * volume + 0.30 * ease + 0.15 * value + 0.10 * breadth
    return int(round(raw * 100))


def _priority(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


# Per-stage search-intent label used when SEMrush left the Intent column blank.
_STAGE_INTENT = {"TOFU": "Informational", "MOFU": "Commercial", "BOFU": "Transactional"}


def _commercial_potential(stage: str, avg_cpc: float, volume_total: int) -> str:
    """Deterministic High/Medium/Low commercial-potential baseline.

    Funnel depth is the strongest signal (BOFU searchers are buyers), CPC shows
    what advertisers pay for the click, and volume scales the opportunity. The
    AI strategist layer may override this with judgement.
    """
    points = {"TOFU": 0, "MOFU": 1, "BOFU": 2}.get(stage, 0)
    if avg_cpc >= 3.0:
        points += 2
    elif avg_cpc >= 1.0:
        points += 1
    if volume_total >= 1000:
        points += 1
    if points >= 3:
        return "High"
    if points >= 2:
        return "Medium"
    return "Low"


def _confidence(cluster_size: int, single_intent: bool, has_volume: bool,
                intent_source: str) -> int:
    conf = 60
    conf += min(18, cluster_size * 3)
    if single_intent:
        conf += 6
    if has_volume:
        conf += 3
    # How the funnel stage was decided matters most for trust.
    conf += {"semrush": 15, "inferred": 6, "default": -8}.get(intent_source, 0)
    return max(35, min(99, conf))


# ── Deterministic topic builder (Python layer) ────────────────────────────────
def build_topics(keyword_rows: List[Dict[str, Any]],
                 existing_pages: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Cluster SEMrush keyword rows into a flat, score-ranked list of topics.

    This is the deterministic Python layer: parse, dedupe, cluster, compute
    Volume/KD/CPC and a tentative funnel stage + score. The optional AI
    strategist layer (agents/ai_topic_strategist.py) enriches these topics
    afterwards; call group_by_funnel() to bucket the final list for display.

    keyword_rows: dicts with keys keyword, intent, volume, keyword_difficulty,
                  cpc, serp_features (all optional except keyword).
    existing_pages: optional [{"url","title"}] to enable Improve/No-Change.
    """
    clusters: Dict[str, Dict[str, Any]] = {}

    for row in keyword_rows:
        keyword = (row.get("keyword") or "").strip()
        if not keyword:
            continue
        key = _topic_key(keyword)
        serp = (row.get("serp_features") or "").strip()
        intent_raw = (row.get("intent") or "").strip()
        stage, stage_source = classify_stage(intent_raw, keyword, serp)
        volume = _to_int(row.get("volume"))
        kd = _to_float(row.get("keyword_difficulty"))
        cpc = _to_float(row.get("cpc"))

        bucket = clusters.get(key)
        if bucket is None:
            bucket = clusters[key] = {
                "key": key,
                "keywords": [],
                "volume_total": 0,
                "kd_values": [],
                "cpc_values": [],
                "serp_features": set(),
                "intents": set(),
                "head_keyword": keyword,
                "head_volume": -1,
                "head_stage": stage,
                "head_source": stage_source,
                "has_deeper_intent": False,
            }
        bucket["keywords"].append({
            "keyword": keyword,
            "intent": intent_raw,
            "volume": volume,
            "keyword_difficulty": round(kd, 1),
            "cpc": round(cpc, 2),
        })
        # The topic is named after (and classified by) its highest-volume
        # keyword. A lower-volume variant sitting deeper in the funnel is noted
        # as a buyer sub-intent rather than reclassifying the whole topic.
        if STAGE_RANK[stage] > STAGE_RANK[bucket["head_stage"]]:
            bucket["has_deeper_intent"] = True
        bucket["volume_total"] += volume
        if kd:
            bucket["kd_values"].append(kd)
        if cpc:
            bucket["cpc_values"].append(cpc)
        for feat in re.split(r",\s*", serp):
            if feat:
                bucket["serp_features"].add(feat)
        if intent_raw:
            bucket["intents"].add(intent_raw)
        if volume > bucket["head_volume"]:
            bucket["head_volume"] = volume
            bucket["head_keyword"] = keyword
            bucket["head_stage"] = stage
            bucket["head_source"] = stage_source

    topics: List[Dict[str, Any]] = []
    for bucket in clusters.values():
        cluster_size = len(bucket["keywords"])
        stage = bucket["head_stage"]
        head = bucket["head_keyword"]
        key_tokens = set(bucket["key"].split())
        content_type = _content_type(stage, key_tokens)

        avg_kd = round(sum(bucket["kd_values"]) / len(bucket["kd_values"]), 1) if bucket["kd_values"] else 0.0
        avg_cpc = round(sum(bucket["cpc_values"]) / len(bucket["cpc_values"]), 2) if bucket["cpc_values"] else 0.0
        volume_total = bucket["volume_total"]
        score = _score(volume_total, avg_kd, avg_cpc, cluster_size)

        # Recommendation enum: New Blog | Existing Blog | New Landing Page |
        # Existing Landing Page | No Action Required. Without site data every
        # topic defaults to New; existing-page matches upgrade the call.
        match = _match_existing(key_tokens, existing_pages)
        if match:
            covered_well = match["coverage"] >= 0.9
            recommendation = "No Action Required" if covered_well else f"Existing {content_type}"
            target_page = match["page"].get("url", "")
        else:
            recommendation = f"New {content_type}"
            target_page = ""

        # Provenance of the DISPLAYED stage = how the head keyword was decided.
        intent_source = bucket["head_source"]
        single_intent = len(bucket["intents"]) <= 1
        confidence = _confidence(cluster_size, single_intent, volume_total > 0, intent_source)

        # Search intent: SEMrush's own label(s) when supplied, otherwise the
        # canonical intent of the resolved funnel stage.
        search_intent = ", ".join(sorted(bucket["intents"])) or _STAGE_INTENT[stage]

        topics.append({
            "topic": head.title(),
            "primary_keyword": head,
            "title": _title(head, stage, content_type),
            "funnel": stage,
            "search_intent": search_intent,
            "commercial_potential": _commercial_potential(stage, avg_cpc, volume_total),
            "intent_source": intent_source,
            "has_deeper_intent": bucket["has_deeper_intent"],
            "content_type": content_type,
            "recommendation": recommendation,
            "target_page": target_page,
            "keyword_count": cluster_size,
            "volume_total": volume_total,
            "avg_keyword_difficulty": avg_kd,
            "avg_cpc": avg_cpc,
            "score": score,
            "priority": _priority(score),
            "confidence": confidence,
            "serp_features": sorted(bucket["serp_features"]),
            "reason": _reason(stage, content_type, cluster_size, volume_total,
                              avg_kd, recommendation),
            "keywords": sorted(bucket["keywords"], key=lambda k: -k["volume"])[:25],
        })

    # Rank by opportunity score, then volume.
    topics.sort(key=lambda t: (-t["score"], -t["volume_total"]))
    return topics


def group_by_funnel(topics: List[Dict[str, Any]],
                    top_per_stage: int = 60,
                    strategist: str = "rule-based") -> Dict[str, Any]:
    """Bucket a flat topic list into TOFU/MOFU/BOFU sections for the frontend.

    top_per_stage caps what's sent per stage (the frontend paginates client-side
    over whatever's fetched); topic_count on each stage is always the real total
    so the UI can say "+N more not fetched" if a stage exceeds this cap.
    """
    funnels = []
    for stage in STAGE_ORDER:
        stage_topics = [t for t in topics if t.get("funnel") == stage]
        stage_topics.sort(key=lambda t: (-t.get("score", 0), -t.get("volume_total", 0)))
        meta = dict(STAGE_META[stage])
        meta["topic_count"] = len(stage_topics)
        meta["keyword_count"] = sum(t.get("keyword_count", 0) for t in stage_topics)
        meta["shown"] = min(len(stage_topics), top_per_stage)
        meta["topics"] = stage_topics[:top_per_stage]
        funnels.append(meta)

    return {
        "status": "keyword_topics",
        "strategist": strategist,  # "ai" when the LLM layer enriched the topics
        "summary": {
            "total_keywords": sum(t.get("keyword_count", 0) for t in topics),
            "total_topics": len(topics),
            "tofu_topics": sum(1 for t in topics if t.get("funnel") == "TOFU"),
            "mofu_topics": sum(1 for t in topics if t.get("funnel") == "MOFU"),
            "bofu_topics": sum(1 for t in topics if t.get("funnel") == "BOFU"),
        },
        "funnels": funnels,
    }


def topics_to_clusters(topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten topics into the strict cluster schema of the recommendations API.

    One entry per cluster: primary keyword, secondary keywords, funnel,
    intent, commercial potential, the content decision and the reasoning.
    """
    clusters = []
    for t in topics:
        primary = t.get("primary_keyword") or t.get("topic", "")
        secondary = [
            k.get("keyword", "") for k in t.get("keywords", [])
            if k.get("keyword", "").lower() != primary.lower()
        ]
        clusters.append({
            "primary_keyword": primary,
            "secondary_keywords": secondary,
            "search_intent": t.get("search_intent", ""),
            "funnel": t.get("funnel", ""),
            "commercial_potential": t.get("commercial_potential", ""),
            "recommended_content": t.get("recommendation", ""),
            "blog_title": t.get("title", ""),
            "target_audience": t.get("persona", ""),
            "target_page": t.get("target_page", ""),
            "reason": t.get("reason", ""),
            "priority": t.get("priority", ""),
            "confidence": t.get("confidence", 0),
            "monthly_volume": t.get("volume_total", 0),
            "avg_keyword_difficulty": t.get("avg_keyword_difficulty", 0),
            "strategist": t.get("strategist", "rule-based"),
        })
    return clusters


def build_funnel_topics(keyword_rows: List[Dict[str, Any]],
                        existing_pages: Optional[List[Dict[str, Any]]] = None,
                        top_per_stage: int = 30) -> Dict[str, Any]:
    """Deterministic-only convenience: build topics and group them (no LLM)."""
    topics = build_topics(keyword_rows, existing_pages)
    return group_by_funnel(topics, top_per_stage)


def _reason(stage: str, content_type: str, cluster_size: int,
            volume_total: int, avg_kd: float, recommendation: str) -> str:
    kw = "keyword" if cluster_size == 1 else "keywords"
    vol = f"{volume_total:,} monthly searches" if volume_total else "no volume data"
    difficulty = (
        "low difficulty" if avg_kd and avg_kd < 30
        else "moderate difficulty" if avg_kd and avg_kd < 60
        else "high difficulty" if avg_kd
        else "unrated difficulty"
    )
    stage_phrase = {
        "TOFU": "awareness-stage searchers learning about the topic",
        "MOFU": "consideration-stage searchers comparing options",
        "BOFU": "decision-stage searchers ready to act",
    }[stage]
    fmt = "an educational blog article" if content_type == "Blog" else "a conversion-focused landing page"
    return (
        f"{cluster_size} related {kw} ({vol}, {difficulty} KD {avg_kd}) aimed at "
        f"{stage_phrase}. Best served by {fmt}. Recommendation: {recommendation}."
    )
