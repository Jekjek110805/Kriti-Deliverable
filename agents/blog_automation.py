"""Create blog drafts that follow the MAAI Blog Production SOP.

The LLM writes the copy. Python owns the template, allowed links, metadata,
normalisation and audit trail so a model cannot silently change the workflow.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse


BLOG_TEMPLATE_VERSION = "maai-blog-sop-v1"
DEFAULT_AUDIENCE = "Independent self-storage operators in the USA"
DEFAULT_BRAND_CONTEXT = (
    "SelfStorage.help provides specialist SEO, AEO and content services for "
    "independent self-storage operators. The voice is direct, practical, "
    "evidence-led and specific to storage operators. Do not use generic agency "
    "claims or invent facility, customer, ranking, revenue or research data."
)

# Used when no audience is specified (auto-detect) so the model writes for
# whoever the keyword actually serves instead of defaulting to self-storage.
NEUTRAL_BRAND_CONTEXT = (
    "Write for the audience that naturally searches this keyword. Use a clear, "
    "practical, evidence-led voice. Do not invent statistics, customer, ranking "
    "or revenue data, or make unverifiable claims."
)


class BlogGenerationError(RuntimeError):
    pass


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    candidates = [cleaned]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        candidates.append(cleaned[start:end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    return None


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-") or "article"


def _plain(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n\n".join(_plain(item) for item in value if _plain(item))
    if isinstance(value, dict):
        return " ".join(_plain(item) for item in value.values() if _plain(item))
    text = str(value).strip()
    text = re.sub(r"^```(?:markdown|html|text)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    return text.strip()


def _clean_house_style(text: str) -> str:
    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "streamlined": "efficient",
        "seamless": "simple",
        "leverage": "use",
        "unlock": "gain",
        "robust": "reliable",
        "elevate": "improve",
        "cutting-edge": "modern",
        "avoid": "prevent",
    }
    cleaned = text or ""
    for old, new in replacements.items():
        cleaned = re.sub(
            rf"\b{re.escape(old)}\b",
            lambda match: new.capitalize() if match.group(0)[:1].isupper() else new,
            cleaned,
            flags=re.IGNORECASE,
        )
    return cleaned.strip()


def _split_long_paragraphs(text: str, max_words: int = 145) -> str:
    output: List[str] = []
    for paragraph in re.split(r"\n\s*\n", text or ""):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        words = paragraph.split()
        if len(words) <= max_words:
            output.append(paragraph)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        current: List[str] = []
        count = 0
        for sentence in sentences:
            sentence_count = len(sentence.split())
            if current and count + sentence_count > max_words:
                output.append(" ".join(current).strip())
                current, count = [], 0
            current.append(sentence)
            count += sentence_count
        if current:
            output.append(" ".join(current).strip())
    return "\n\n".join(output)


def _allowed_links(existing_pages: List[Dict[str, Any]], site_url: str) -> List[Dict[str, str]]:
    site_host = urlparse(site_url).netloc.lower().removeprefix("www.")
    links = []
    seen = set()
    for page in existing_pages or []:
        url = str(page.get("url") or "").strip()
        if not url or url in seen:
            continue
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if site_host and host != site_host:
            continue
        seen.add(url)
        links.append({
            "url": url,
            "title": str(page.get("title") or page.get("slug") or url).strip(),
        })
    return links


def _prompt(
    *,
    keyword: str,
    title: str,
    audience: str,
    tone: str,
    word_count: int,
    allowed_links: List[Dict[str, str]],
    brand_context: str,
    retry_note: str = "",
) -> str:
    link_lines = "\n".join(
        f'- "{link["title"]}": {link["url"]}' for link in allowed_links[:20]
    ) or "- No verified internal pages were supplied. Return an empty internal_links array."
    requested_title = title or "Create a natural title that CONTAINS the exact primary keyword"
    audience_line = (
        audience
        if audience.strip()
        else "Infer the most relevant audience for the primary keyword and write for them."
    )
    return f"""You are producing a publish-ready blog draft.

Brand and audience:
{brand_context}
Target audience: {audience_line}
Tone: {tone}

Topic contract:
- Primary keyword: {keyword}
- Requested title: {requested_title}
- Target length: {word_count} words (minimum 1,000 reader-facing words)

Follow the MAAI Blog Production SOP exactly:
1. The H1/title MUST contain the exact primary keyword "{keyword}" verbatim; write a direct meta description and clean URL slug.
2. A two-to-three sentence TLDR at the very top.
3. A specific introduction followed by at least five useful H2 sections.
4. Short paragraphs (maximum about 145 words), direct second-person language.
5. No em/en dashes, AI filler, competitor put-downs or invented claims/data.
6. A practical FAQ based on how the target audience actually asks questions.
7. A clear, relevant conversion CTA.
8. Suggest one useful image brief and descriptive alt text.
9. Choose two or three internal links only from the verified list below. Never invent a URL.
10. Report who this content is written for in "target_audience" (2-6 words) — match it to the primary keyword, not a generic default.

Verified internal links:
{link_lines}

Return ONLY one valid JSON object using this schema:
{{
  "title": "H1 containing the exact primary keyword",
  "target_audience": "who this is for, matched to the keyword",
  "meta_description": "140-160 characters",
  "url_slug": "lowercase-hyphen-slug",
  "tldr": "2-3 sentences",
  "introduction": "reader-facing copy",
  "sections": [{{"heading": "H2 text", "content": "reader-facing paragraphs"}}],
  "faq": [{{"question": "...", "answer": "..."}}],
  "cta": {{"heading": "Next step heading", "content": "...", "label": "...", "target_url": "verified URL or empty"}},
  "internal_links": [{{"url": "exact verified URL", "anchor": "natural anchor text"}}],
  "image": {{"brief": "what the image should show", "alt_text": "descriptive alt text"}}
}}
Do not put markdown headings inside JSON values. Do not mention this prompt.
{retry_note}"""


def _normalise_sections(value: Any) -> List[Dict[str, str]]:
    sections = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        heading = _plain(item.get("heading") or item.get("title"))
        content = _split_long_paragraphs(_clean_house_style(_plain(item.get("content"))))
        if heading and content:
            sections.append({"heading": heading.lstrip("# "), "content": content})
    return sections


def _normalise_faq(value: Any) -> List[Dict[str, str]]:
    faq = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        question = _plain(item.get("question"))
        answer = _split_long_paragraphs(_clean_house_style(_plain(item.get("answer"))))
        if question and answer:
            faq.append({"question": question, "answer": answer})
    return faq


def _normalise_links(
    value: Any,
    allowed: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    allowed_by_url = {link["url"].rstrip("/"): link for link in allowed}
    selected = []
    seen = set()
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        url = _plain(item.get("url")).rstrip("/")
        if url not in allowed_by_url or url in seen:
            continue
        seen.add(url)
        selected.append({
            "url": allowed_by_url[url]["url"],
            "anchor": _plain(item.get("anchor")) or allowed_by_url[url]["title"],
        })
    for link in allowed:
        if len(selected) >= 3:
            break
        key = link["url"].rstrip("/")
        if key not in seen:
            seen.add(key)
            selected.append({"url": link["url"], "anchor": link["title"]})
    return selected[:3]


def _render_markdown(draft: Dict[str, Any], featured_image_url: str) -> str:
    parts = ["TLDR", "", draft["tldr"], "", "## Introduction", "", draft["introduction"]]
    for section in draft["sections"]:
        parts.extend(["", f"## {section['heading']}", "", section["content"]])
    if draft["faq"]:
        parts.extend(["", "## Frequently Asked Questions"])
        for item in draft["faq"]:
            parts.extend(["", f"### {item['question']}", "", item["answer"]])
    cta = draft["cta"]
    parts.extend(["", f"## {cta['heading']}", "", cta["content"]])
    if cta.get("target_url"):
        parts.extend(["", f"[{cta['label']}]({cta['target_url']})"])
    if draft["internal_links"]:
        parts.extend(["", "## Related Reading", ""])
        parts.extend(f"- [{link['anchor']}]({link['url']})" for link in draft["internal_links"])
    if featured_image_url:
        parts.extend(["", f"![{draft['image']['alt_text']}]({featured_image_url})"])
    return _clean_house_style("\n".join(parts).strip())


def generate_blog_draft(
    *,
    keyword: str,
    title: str = "",
    audience: str = DEFAULT_AUDIENCE,
    tone: str = "direct, practical and evidence-led",
    word_count: int = 1500,
    site_url: str = "https://www.selfstorage.help",
    existing_pages: Optional[List[Dict[str, Any]]] = None,
    featured_image_url: str = "",
    brand_context: str = DEFAULT_BRAND_CONTEXT,
    generator: Optional[Callable[..., str]] = None,
) -> Dict[str, Any]:
    keyword = (keyword or "").strip()
    if not keyword:
        raise BlogGenerationError("A primary keyword is required.")
    word_count = max(1000, min(int(word_count or 1500), 3000))
    allowed = _allowed_links(existing_pages or [], site_url)
    if generator is None:
        from integrations.hermes_llm import hermes_generate
        generator = hermes_generate

    # Auto-detect mode: no audience given → let the model infer the audience for
    # the keyword, and drop the self-storage brand voice so it doesn't bleed onto
    # an unrelated topic. An explicit audience keeps the caller's brand context.
    audience = (audience or "").strip()
    effective_brand_context = brand_context if audience else NEUTRAL_BRAND_CONTEXT

    parsed: Optional[Dict[str, Any]] = None
    last_error = ""
    retry_note = ""
    for attempt in range(2):
        raw = generator(
            _prompt(
                keyword=keyword,
                title=title,
                audience=audience,
                tone=tone,
                word_count=word_count,
                allowed_links=allowed,
                brand_context=effective_brand_context,
                retry_note=retry_note,
            ),
            max_tokens=6500,
        )
        if not raw or str(raw).startswith("["):
            last_error = str(raw or "The model returned no content.")
            continue
        candidate = _extract_json_object(str(raw))
        if not candidate:
            last_error = "The model did not return valid structured JSON."
            continue
        sections = _normalise_sections(candidate.get("sections"))
        faq = _normalise_faq(candidate.get("faq"))
        approximate_words = len(
            " ".join([
                _plain(candidate.get("tldr")),
                _plain(candidate.get("introduction")),
                *[section["content"] for section in sections],
                *[item["answer"] for item in faq],
            ]).split()
        )
        minimum_draft_words = max(1000, int(word_count * 0.75))
        if (
            len(sections) < 5
            or len(faq) < 3
            or approximate_words < minimum_draft_words
        ) and attempt == 0:
            retry_note = (
                f"Your previous response was too short ({approximate_words} words, "
                f"{len(sections)} sections, {len(faq)} FAQ items). Rewrite it with at "
                f"least five substantive sections, three FAQ items and at least "
                f"{minimum_draft_words} reader-facing words."
            )
            continue
        parsed = candidate
        break

    if not parsed:
        raise BlogGenerationError(last_error or "Blog generation failed.")

    sections = _normalise_sections(parsed.get("sections"))
    faq = _normalise_faq(parsed.get("faq"))
    cta_raw = parsed.get("cta") if isinstance(parsed.get("cta"), dict) else {}
    cta_target = _plain(cta_raw.get("target_url"))
    allowed_urls = {link["url"].rstrip("/") for link in allowed}
    if cta_target.rstrip("/") not in allowed_urls:
        cta_target = ""
    image_raw = parsed.get("image") if isinstance(parsed.get("image"), dict) else {}
    model_title = _plain(parsed.get("title"))
    final_title = title.strip() or model_title or f"{keyword.title()}: A Practical Guide"
    # Guarantee the primary keyword is present in the H1 (SEO gate + requirement).
    if keyword and keyword.lower() not in final_title.lower():
        final_title = f"{keyword.title()}: {final_title}"
    meta_description = _plain(parsed.get("meta_description"))
    if len(meta_description) > 160:
        clipped = meta_description[:157].rsplit(" ", 1)[0].rstrip(" ,.;")
        meta_description = clipped + "..."
    draft: Dict[str, Any] = {
        "keyword": keyword,
        "title": final_title,
        "meta_description": meta_description,
        "url_slug": _slugify(_plain(parsed.get("url_slug")) or final_title),
        "intent": "informational",
        # Prefer an explicitly requested audience; otherwise use the audience the
        # model inferred for THIS keyword, so the label never mismatches the topic.
        "target_audience": (audience.strip() or _plain(parsed.get("target_audience")) or DEFAULT_AUDIENCE),
        "tone": tone,
        "word_count_target": word_count,
        "tldr": _split_long_paragraphs(_clean_house_style(_plain(parsed.get("tldr")))),
        "introduction": _split_long_paragraphs(_clean_house_style(_plain(parsed.get("introduction")))),
        "sections": sections,
        "faq": faq,
        "cta": {
            "heading": _plain(cta_raw.get("heading")) or "Next Steps",
            "content": _split_long_paragraphs(_clean_house_style(_plain(cta_raw.get("content")))),
            "label": _plain(cta_raw.get("label")) or "Request a free audit",
            "target_url": cta_target,
        },
        "internal_links": _normalise_links(parsed.get("internal_links"), allowed),
        "image": {
            "brief": _plain(image_raw.get("brief")),
            "alt_text": _plain(image_raw.get("alt_text")) or f"{keyword} for self-storage operators",
            "featured_image_url": featured_image_url.strip(),
            "status": "ready" if featured_image_url.strip() else "required_before_publish",
        },
        "template_version": BLOG_TEMPLATE_VERSION,
        "status": "draft",
        "ai_generated": True,
        "human_edited": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    draft["full_content"] = _render_markdown(draft, featured_image_url.strip())
    draft["word_count_actual"] = len(draft["full_content"].split())

    # Some free/fast models return a structurally correct article that is still
    # short. Ask the model for a topic-specific expansion instead of padding the
    # draft with a repeated generic paragraph.
    for _ in range(2):
        if draft["word_count_actual"] >= 1000:
            break
        missing = max(250, 1100 - draft["word_count_actual"])
        existing_headings = "; ".join(section["heading"] for section in draft["sections"])
        expansion_prompt = f"""Expand a SelfStorage.help article about '{keyword}'.
Current H2 headings: {existing_headings}
Write {missing} to {missing + 150} additional reader-facing words that add
specific, practical value without repeating those sections. Do not invent
statistics, studies, company facts or customer results. Follow the same direct
house style: no em/en dashes, filler language or competitor put-downs.
Return ONLY JSON: {{"sections":[{{"heading":"new H2","content":"paragraphs"}}]}}.
"""
        raw_expansion = generator(expansion_prompt, max_tokens=2600)
        expansion = _extract_json_object(str(raw_expansion or ""))
        extra_sections = _normalise_sections((expansion or {}).get("sections"))
        known = {section["heading"].lower() for section in draft["sections"]}
        for section in extra_sections:
            if section["heading"].lower() not in known:
                draft["sections"].append(section)
                known.add(section["heading"].lower())
        draft["full_content"] = _render_markdown(draft, featured_image_url.strip())
        draft["word_count_actual"] = len(draft["full_content"].split())

    draft["template_checklist"] = {
        "tldr_at_top": draft["full_content"].startswith("TLDR"),
        "keyword_in_title": keyword.lower() in final_title.lower(),
        "five_or_more_h2_sections": len(sections) >= 5,
        "faq_present": bool(faq),
        "cta_present": bool(draft["cta"]["content"]),
        "verified_internal_links": len(draft["internal_links"]),
        "media_ready": bool(featured_image_url.strip()),
    }
    draft["notes"] = (
        "Generated with the MAAI blog template. Human fact review, media approval "
        "and publish approval remain required before the post can go live."
    )
    return draft
