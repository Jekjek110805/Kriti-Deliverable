"""Read a site's sitemap and turn existing blog pages into useful evidence.

The content strategy and refresh suggestions must not invent existing pages.
This module uses the site's own sitemap and public HTML as the source of truth.
It deliberately has no CMS or framework dependency, so it works for the current
Next.js SelfStorage.help site and for WordPress/custom sites later.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import requests


DEFAULT_SITE_URL = "https://www.selfstorage.help"
_REQUEST_TIMEOUT = 20
_USER_AGENT = "KritiBlogAutomation/1.0 (+https://selfstorage.help/)"


def normalize_site_url(site_url: str) -> str:
    value = (site_url or DEFAULT_SITE_URL).strip()
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = "https://" + value
    parsed = urlparse(value)
    if not parsed.netloc:
        raise ValueError("Enter a valid website URL, for example https://selfstorage.help")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _request(session: Any, url: str):
    response = session.get(
        url,
        headers={"User-Agent": _USER_AGENT},
        timeout=_REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response


def _xml_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _read_sitemap(
    sitemap_url: str,
    session: Any,
    seen: set,
    depth: int = 0,
) -> List[Dict[str, str]]:
    if sitemap_url in seen or depth > 2:
        return []
    seen.add(sitemap_url)

    response = _request(session, sitemap_url)
    root = ET.fromstring(response.content)
    root_name = _xml_name(root.tag)

    if root_name == "sitemapindex":
        pages: List[Dict[str, str]] = []
        for child in root:
            loc = next(
                (node.text.strip() for node in child if _xml_name(node.tag) == "loc" and node.text),
                "",
            )
            if loc:
                pages.extend(_read_sitemap(loc, session, seen, depth + 1))
        return pages

    pages = []
    for child in root:
        values = {
            _xml_name(node.tag): (node.text or "").strip()
            for node in child
        }
        if values.get("loc"):
            pages.append({"url": values["loc"], "lastmod": values.get("lastmod", "")})
    return pages


def inventory_existing_pages(
    site_url: str = DEFAULT_SITE_URL,
    session: Any = requests,
) -> List[Dict[str, Any]]:
    """Return sitemap-backed page evidence suitable for topic matching."""
    base_url = normalize_site_url(site_url)
    sitemap_candidates = [
        urljoin(base_url + "/", "sitemap.xml"),
        urljoin(base_url + "/", "sitemap_index.xml"),
    ]
    last_error: Optional[Exception] = None
    rows: List[Dict[str, str]] = []
    for sitemap_url in sitemap_candidates:
        try:
            rows = _read_sitemap(sitemap_url, session, set())
            if rows:
                break
        except Exception as exc:  # caller decides whether inventory is required
            last_error = exc

    if not rows and last_error:
        raise RuntimeError(f"Could not read the site sitemap: {last_error}") from last_error

    pages = []
    for row in rows:
        url = row.get("url", "")
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        slug = path.rsplit("/", 1)[-1] if path != "/" else "home"
        title = re.sub(r"[-_]+", " ", slug).strip().title()
        content_type = "blog" if path == "/blog" or path.startswith("/blog/") else "page"
        pages.append({
            "url": url,
            "path": path,
            "slug": slug,
            "title": title,
            "lastmod": row.get("lastmod", ""),
            "content_type": content_type,
        })
    return pages


class _PageFactsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.headings: List[Dict[str, str]] = []
        self.links: List[str] = []
        self.images: List[Dict[str, str]] = []
        self.text_parts: List[str] = []
        self._ignored_depth = 0
        self._capture_title = False
        self._heading_tag = ""
        self._heading_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: Iterable) -> None:
        tag = tag.lower()
        values = {str(k).lower(): str(v or "") for k, v in attrs}
        if tag in ("script", "style", "noscript", "svg"):
            self._ignored_depth += 1
            return
        if tag == "title":
            self._capture_title = True
        elif tag in ("h1", "h2", "h3"):
            self._heading_tag = tag
            self._heading_parts = []
        elif tag == "meta" and values.get("name", "").lower() == "description":
            self.description = values.get("content", "").strip()
        elif tag == "a" and values.get("href"):
            self.links.append(values["href"].strip())
        elif tag == "img":
            self.images.append({
                "src": values.get("src", "").strip(),
                "alt": values.get("alt", "").strip(),
            })

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("script", "style", "noscript", "svg") and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if tag == "title":
            self._capture_title = False
        if tag == self._heading_tag:
            text = " ".join(self._heading_parts).strip()
            if text:
                self.headings.append({"level": tag, "text": text})
            self._heading_tag = ""
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self._capture_title:
            self.title = f"{self.title} {text}".strip()
        if self._heading_tag:
            self._heading_parts.append(text)
        self.text_parts.append(text)


def extract_page_facts(html: str, url: str) -> Dict[str, Any]:
    parser = _PageFactsParser()
    parser.feed(html or "")
    base_host = urlparse(url).netloc.lower().removeprefix("www.")
    internal_links = []
    for href in parser.links:
        absolute = urljoin(url, href)
        host = urlparse(absolute).netloc.lower().removeprefix("www.")
        if host == base_host and absolute.rstrip("/") != url.rstrip("/"):
            internal_links.append(absolute)

    visible_text = " ".join(parser.text_parts)
    article_markers = visible_text.lower()
    return {
        "title": parser.title.strip(),
        "meta_description": parser.description,
        "word_count": len(re.findall(r"\b[\w'-]+\b", visible_text)),
        "h1_count": sum(1 for h in parser.headings if h["level"] == "h1"),
        "h2_count": sum(1 for h in parser.headings if h["level"] == "h2"),
        "headings": parser.headings,
        "internal_link_count": len(set(internal_links)),
        "image_count": len(parser.images),
        "images_missing_alt": sum(1 for image in parser.images if not image["alt"]),
        "has_tldr": "tldr" in article_markers or "tl;dr" in article_markers,
        "has_faq": "frequently asked" in article_markers or "common questions" in article_markers,
        "has_cta": any(
            phrase in article_markers
            for phrase in ("get a free", "request an", "book a", "contact us", "next step")
        ),
    }


def _suggestions_for_blog(page: Dict[str, Any]) -> List[Dict[str, str]]:
    suggestions: List[Dict[str, str]] = []

    def add(priority: str, action: str, reason: str) -> None:
        suggestions.append({"priority": priority, "action": action, "reason": reason})

    title = page.get("title", "")
    slug = page.get("slug", "")
    if "test" in slug.lower() or title.lower().startswith("testing"):
        add("High", "Replace or remove the test article", "A public placeholder weakens topical quality and user trust.")
    if page.get("word_count", 0) < 800:
        priority = "High" if page.get("word_count", 0) < 400 else "Medium"
        add(priority, "Expand the article with specific, useful sections", f"The rendered page has about {page.get('word_count', 0)} visible words.")
    meta_len = len(page.get("meta_description", ""))
    if meta_len < 120 or meta_len > 165:
        add("Medium", "Rewrite the meta description", f"The current description is {meta_len} characters; target roughly 140-160.")
    if page.get("h1_count", 0) != 1:
        add("High", "Use one clear keyword-focused H1", f"Found {page.get('h1_count', 0)} H1 headings.")
    if page.get("h2_count", 0) < 3:
        add("Medium", "Add a structured H2 outline", f"Found only {page.get('h2_count', 0)} H2 sections.")
    if not page.get("has_tldr"):
        add("Medium", "Add a two-to-three sentence TLDR at the top", "The MAAI blog template requires a liftable summary before the body.")
    if not page.get("has_faq"):
        add("Medium", "Add questions real storage operators ask", "A focused FAQ improves reader utility and AI-search coverage.")
    if not page.get("has_cta"):
        add("High", "Add a relevant conversion CTA", "The article should guide the reader to a clear next action.")
    if page.get("internal_link_count", 0) < 2:
        add("Medium", "Add two or three contextual internal links", f"Found {page.get('internal_link_count', 0)} unique internal links.")
    if page.get("image_count", 0) == 0:
        add("Low", "Add one useful original or licensed image with descriptive alt text", "The blog SOP requires media that supports the article.")
    elif page.get("images_missing_alt", 0):
        add("Medium", "Write descriptive alt text for every image", f"{page.get('images_missing_alt', 0)} images are missing alt text.")
    if not suggestions:
        add("Low", "Keep monitoring this article in GSC", "No structural template gaps were detected in the public page.")
    return suggestions


def analyze_existing_blogs(
    site_url: str = DEFAULT_SITE_URL,
    session: Any = requests,
    max_blogs: int = 50,
) -> Dict[str, Any]:
    """Audit sitemap-backed blog posts and return actionable refresh ideas."""
    base_url = normalize_site_url(site_url)
    inventory = inventory_existing_pages(base_url, session=session)
    blog_pages = [
        page for page in inventory
        if page.get("path", "").startswith("/blog/")
    ][:max_blogs]

    results = []
    errors = []
    for page in blog_pages:
        try:
            response = _request(session, page["url"])
            facts = extract_page_facts(response.text, page["url"])
            enriched = {**page, **facts}
            enriched["suggestions"] = _suggestions_for_blog(enriched)
            priorities = [s["priority"] for s in enriched["suggestions"]]
            enriched["priority"] = (
                "High" if "High" in priorities else "Medium" if "Medium" in priorities else "Low"
            )
            results.append(enriched)
        except Exception as exc:
            errors.append({"url": page["url"], "error": str(exc)})

    results.sort(key=lambda row: ({"High": 0, "Medium": 1, "Low": 2}.get(row["priority"], 3), row["title"]))
    return {
        "site_url": base_url,
        "source": "public sitemap and page HTML",
        "blog_count": len(blog_pages),
        "analyzed_count": len(results),
        "inventory_count": len(inventory),
        "blogs": results,
        "errors": errors,
        "message": (
            f"Analyzed {len(results)} existing blog post(s) from the site's sitemap."
            if blog_pages
            else "No /blog/ article URLs were found in the site's sitemap."
        ),
    }
