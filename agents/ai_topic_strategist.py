"""
ai_topic_strategist.py -- Optional AI reasoning layer over funnel topics.

The deterministic engine (agents/funnel_topics.build_topics) does the heavy,
repeatable work: parse, clean, dedupe, cluster, compute Volume / KD / CPC and a
tentative funnel stage + score. THIS module adds the strategist judgement on top
-- the part that genuinely needs reasoning:

  * confirm / correct the funnel stage (buyer journey, not just intent keyword)
  * Blog vs Landing Page
  * a compelling, specific suggested title
  * a one-line reason
  * the target persona who searches this
  * a suggested CTA / content hook
  * a priority call

WHY a thin layer (not "send everything to the LLM")
----------------------------------------------------
A SEMrush file can hold thousands of keywords -> thousands of topics. Sending
all of them to an LLM is slow and expensive (see docs/.../COST_DISCIPLINE.md).
So Python clusters and ranks first, and the LLM enriches only the TOP topics --
the ones a human would actually act on. Everything else keeps its deterministic
values. The result is affordable and still feels like an SEO strategist.

GRACEFUL DEGRADATION
--------------------
If OPENROUTER_API_KEY is missing, the model errors, or the JSON can't be parsed,
enrichment is skipped and the deterministic topics are returned unchanged. The
feature never breaks the upload flow -- it only ever makes it richer.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

try:  # reuse the existing OpenRouter client (same one the content writer uses)
    from integrations.hermes_llm import hermes_generate
except Exception:  # pragma: no cover - import guard
    hermes_generate = None

VALID_FUNNELS = {"TOFU", "MOFU", "BOFU"}
VALID_CONTENT = {"Blog", "Landing Page"}
VALID_PRIORITY = {"High", "Medium", "Low"}


def _build_prompt(batch: List[Dict[str, Any]]) -> str:
    lines = []
    for item in batch:
        related = ", ".join(k.get("keyword", "") for k in item.get("keywords", [])[:6])
        lines.append(
            f'- id {item["_id"]}: primary keyword "{item.get("topic", "")}" '
            f'| related: {related or "n/a"} '
            f'| monthly volume {item.get("volume_total", 0)} '
            f'| difficulty(KD) {item.get("avg_keyword_difficulty", 0)} '
            f'| avg CPC ${item.get("avg_cpc", 0)} '
            f'| tentative funnel {item.get("funnel", "TOFU")}'
        )
    topics_block = "\n".join(lines)
    return (
        "You are an expert SEO content strategist. Turn each keyword topic below "
        "into an actionable content recommendation. Think about the buyer journey, "
        "search intent and commercial value.\n\n"
        "Funnel stages: TOFU = awareness / informational (learning); "
        "MOFU = consideration / commercial (comparing, 'best', reviews, software); "
        "BOFU = decision / transactional (buy, for sale, pricing, near me).\n"
        "Content type: Blog for informational or comparison topics; "
        "Landing Page for transactional / buyer topics.\n\n"
        f"Topics:\n{topics_block}\n\n"
        "Return ONLY a JSON object of this exact shape:\n"
        '{"topics":[{"id":<int>,"funnel":"TOFU|MOFU|BOFU",'
        '"content_type":"Blog|Landing Page","title":"<compelling specific title, '
        'use the year 2026 only when natural>","reason":"<one sentence why>",'
        '"persona":"<who searches this, 2-4 words>",'
        '"cta":"<button label for a landing page, or content hook for a blog>",'
        '"priority":"High|Medium|Low"}]}\n'
        "Include every id exactly once. No commentary outside the JSON."
    )


def _parse_response(text: str) -> Dict[int, Dict[str, Any]]:
    """Extract {id: enrichment} from a model response, tolerating stray text."""
    if not text or text.lstrip().startswith("["):  # "[OpenRouter error ...]" markers
        if not text.strip().startswith("[{") and not text.strip().startswith("["):
            return {}
    payload = None
    try:
        payload = json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group(0))
            except Exception:
                payload = None
    if payload is None:
        return {}
    items = payload.get("topics") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return {}

    out: Dict[int, Dict[str, Any]] = {}
    for entry in items:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        try:
            out[int(entry["id"])] = entry
        except (TypeError, ValueError):
            continue
    return out


def _apply(topic: Dict[str, Any], enr: Dict[str, Any]) -> None:
    """Merge one enrichment onto a topic, validating enumerated fields."""
    funnel = str(enr.get("funnel", "")).upper().strip()
    if funnel in VALID_FUNNELS:
        topic["funnel"] = funnel
    content = str(enr.get("content_type", "")).strip().title().replace("Landing page", "Landing Page")
    if content in VALID_CONTENT:
        topic["content_type"] = content
    priority = str(enr.get("priority", "")).strip().title()
    if priority in VALID_PRIORITY:
        topic["priority"] = priority
    for src, dst in (("title", "title"), ("reason", "reason"),
                     ("persona", "persona"), ("cta", "cta")):
        val = str(enr.get(src, "")).strip()
        if val:
            topic[dst] = val
    topic["strategist"] = "ai"


def enrich_topics(topics: List[Dict[str, Any]],
                  max_topics: int = 45,
                  batch_size: int = 6,
                  model: str = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Enrich the top `max_topics` topics with the LLM; leave the rest as-is.

    Returns (topics, meta). `topics` is the same list (enriched in place where
    possible). `meta` reports whether the AI layer ran and how many it covered.
    """
    meta = {"available": False, "enriched": 0, "requested": 0, "note": ""}
    for t in topics:  # default provenance so the frontend can label every card
        t.setdefault("strategist", "rule-based")

    if hermes_generate is None:
        meta["note"] = "AI client unavailable; showing rule-based recommendations."
        return topics, meta

    # Enrich the top topics of EACH funnel stage (not just the global top-N,
    # which would skew to whichever stage has the most topics). This guarantees
    # the first cards a user sees in every stage are strategist-grade.
    per_stage = max(1, max_topics // 3)
    subset = []
    seen = set()
    for stage in ("TOFU", "MOFU", "BOFU"):
        stage_topics = sorted(
            (t for t in topics if t.get("funnel") == stage),
            key=lambda t: (-t.get("score", 0), -t.get("volume_total", 0)),
        )
        for topic in stage_topics[:per_stage]:
            if id(topic) not in seen:
                seen.add(id(topic))
                subset.append(topic)
    meta["requested"] = len(subset)
    if not subset:
        return topics, meta

    by_id = {}
    for index, topic in enumerate(subset):
        topic["_id"] = index
        by_id[index] = topic

    batches = [subset[i:i + batch_size] for i in range(0, len(subset), batch_size)]

    def run_batch(batch):
        # The free model occasionally returns an empty body or a transient
        # error; retry a couple of times before giving up on the batch.
        last_err = ""
        for _attempt in range(3):
            try:
                response = hermes_generate(_build_prompt(batch), model=model, max_tokens=1600)
            except Exception as exc:  # pragma: no cover
                last_err = f"AI enrichment error: {exc}"
                continue
            if response.strip().startswith("[OpenRouter"):
                last_err = response.strip()
                continue
            parsed = _parse_response(response)
            if parsed:
                return parsed, ""
            last_err = "AI returned no usable JSON for a batch."
        return None, last_err

    # Batches are independent network calls -> run them concurrently so the
    # endpoint waits roughly one call's latency, not the sum of all of them.
    enriched_count = 0
    saw_error = False
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(6, len(batches))) as pool:
        for batch, (parsed, err) in zip(batches, pool.map(run_batch, batches)):
            if parsed is None:
                saw_error = True
                if err and not meta["note"]:
                    meta["note"] = err
                continue
            for topic in batch:
                enr = parsed.get(topic["_id"])
                if enr:
                    _apply(topic, enr)
                    enriched_count += 1

    for topic in subset:  # clean up the temporary id
        topic.pop("_id", None)

    meta["available"] = enriched_count > 0
    meta["enriched"] = enriched_count
    if enriched_count and not saw_error:
        meta["note"] = f"AI strategist enriched the top {enriched_count} topics."
    elif not enriched_count and not meta["note"]:
        meta["note"] = "AI returned no usable output; showing rule-based recommendations."
    return topics, meta
