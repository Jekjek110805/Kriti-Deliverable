"""Real CMS publishing adapters used by Kriti's gated publish workflow.

Supported transports:
* WordPress REST API using an Application Password or bearer token.
* A custom HTTPS endpoint for Git-backed/Next.js sites such as SelfStorage.help.

This module never treats a local JSON record as a successful publication. A
publish call succeeds only after the remote CMS returns a 2xx response.
"""

from __future__ import annotations

import base64
import html
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests


class CMSPublishError(RuntimeError):
    """Safe, user-facing CMS error (credentials are never included)."""


def _clean_url(value: str) -> str:
    url = (value or "").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise CMSPublishError("CMS API URL must be a complete http(s) URL.")
    return url


def _wordpress_posts_url(api_url: str) -> str:
    url = _clean_url(api_url)
    lower = url.lower()
    if lower.endswith("/wp-json"):
        return url + "/wp/v2/posts"
    if lower.endswith("/wp-json/wp/v2"):
        return url + "/posts"
    if "/wp-json/wp/v2/posts" in lower:
        return url
    return url + "/wp-json/wp/v2/posts"


def markdown_to_html(markdown: str) -> str:
    """Convert the limited MAAI draft Markdown shape to WordPress-safe HTML."""
    source = html.escape(markdown or "", quote=False)

    def inline(value: str) -> str:
        value = re.sub(
            r"!\[([^\]]*)\]\((https?://[^)]+)\)",
            r'<img src="\2" alt="\1">',
            value,
        )
        value = re.sub(
            r"(?<!!)\[([^\]]+)\]\((https?://[^)]+)\)",
            r'<a href="\2">\1</a>',
            value,
        )
        return value

    blocks = []
    for block in re.split(r"\n\s*\n", source.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if len(lines) == 1 and lines[0].startswith("### "):
            blocks.append(f"<h3>{inline(lines[0][4:])}</h3>")
        elif len(lines) == 1 and lines[0].startswith("## "):
            blocks.append(f"<h2>{inline(lines[0][3:])}</h2>")
        elif all(line.startswith("- ") for line in lines):
            items = "".join(f"<li>{inline(line[2:])}</li>" for line in lines)
            blocks.append(f"<ul>{items}</ul>")
        elif len(lines) == 1 and lines[0].upper() == "TLDR":
            blocks.append("<p><strong>TLDR</strong></p>")
        elif len(lines) == 1 and lines[0].startswith("<img "):
            blocks.append(inline(lines[0]))
        else:
            blocks.append(f"<p>{inline('<br>'.join(lines))}</p>")
    return "\n".join(blocks)


class CMSPublisher:
    def __init__(self, config: Dict[str, Any], session: Any = requests) -> None:
        self.config = config or {}
        self.session = session
        self.cms_type = str(self.config.get("cms_type") or "custom").strip().lower()
        if self.cms_type == "custom_api":
            self.cms_type = "custom"
        if self.cms_type not in ("wordpress", "custom"):
            raise CMSPublishError(
                f"CMS type '{self.cms_type}' is not implemented. Use wordpress or custom."
            )
        self.api_url = _clean_url(str(self.config.get("api_url") or ""))

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        api_key = str(self.config.get("api_key") or "").strip()
        username = str(self.config.get("username") or "").strip()
        if username and api_key:
            token = base64.b64encode(f"{username}:{api_key}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        elif api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @staticmethod
    def _response_json(response: Any) -> Dict[str, Any]:
        try:
            data = response.json()
        except Exception as exc:
            raise CMSPublishError("The CMS returned a non-JSON response.") from exc
        if not isinstance(data, dict):
            raise CMSPublishError("The CMS returned an unexpected response shape.")
        return data

    @staticmethod
    def _raise_for_response(response: Any, action: str) -> None:
        if 200 <= int(response.status_code) < 300:
            return
        detail = ""
        try:
            data = response.json()
            detail = str(data.get("message") or data.get("error") or "")
        except Exception:
            detail = str(getattr(response, "text", "") or "")
        detail = " ".join(detail.split())[:300]
        suffix = f" {detail}" if detail else ""
        raise CMSPublishError(f"CMS {action} failed with HTTP {response.status_code}.{suffix}")

    def test_connection(self) -> Dict[str, Any]:
        if self.cms_type == "wordpress":
            posts_url = _wordpress_posts_url(self.api_url)
            users_url = posts_url.rsplit("/posts", 1)[0] + "/users/me?context=edit"
            response = self.session.get(users_url, headers=self._headers(), timeout=30)
            self._raise_for_response(response, "connection test")
            data = self._response_json(response)
            return {
                "connected": True,
                "cms_type": "wordpress",
                "account": data.get("name") or data.get("slug") or "authenticated user",
            }

        response = self.session.get(self.api_url, headers=self._headers(), timeout=30)
        self._raise_for_response(response, "connection test")
        return {"connected": True, "cms_type": "custom", "endpoint": self.api_url}

    def publish(
        self,
        *,
        keyword: str,
        title: str,
        content: str,
        slug: str,
        meta_description: str,
        publish_now: bool,
        client: str = "default",
        featured_image_url: str = "",
    ) -> Dict[str, Any]:
        status = "publish" if publish_now else "draft"
        if self.cms_type == "wordpress":
            endpoint = _wordpress_posts_url(self.api_url)
            payload: Dict[str, Any] = {
                "title": title,
                "content": markdown_to_html(content),
                "slug": slug.strip("/"),
                "status": status,
                "excerpt": meta_description,
            }
            author_id = str(self.config.get("author_id") or "").strip()
            if author_id.isdigit():
                payload["author"] = int(author_id)
            response = self.session.post(
                endpoint,
                json=payload,
                headers=self._headers(),
                timeout=60,
            )
            self._raise_for_response(response, "publish")
            data = self._response_json(response)
            return {
                "cms_type": "wordpress",
                "cms_post_id": data.get("id"),
                "status": data.get("status") or status,
                "url": data.get("link") or "",
                "edit_url": data.get("_links", {}).get("self", [{}])[0].get("href", "")
                if isinstance(data.get("_links"), dict)
                else "",
                "remote_response": {
                    "id": data.get("id"),
                    "status": data.get("status"),
                    "slug": data.get("slug"),
                },
            }

        payload = {
            "keyword": keyword,
            "title": title,
            "content": content,
            "content_format": "markdown",
            "slug": slug.strip("/"),
            "meta_description": meta_description,
            "status": status,
            "client": client,
            "featured_image_url": featured_image_url,
            "source": "kriti-blog-automation",
        }
        response = self.session.post(
            self.api_url,
            json=payload,
            headers=self._headers(),
            timeout=60,
        )
        self._raise_for_response(response, "publish")
        data = self._response_json(response)
        return {
            "cms_type": "custom",
            "cms_post_id": data.get("id") or data.get("post_id") or data.get("cms_post_id"),
            "status": data.get("status") or status,
            "url": data.get("url") or data.get("link") or "",
            "edit_url": data.get("edit_url") or "",
            "remote_response": {
                "id": data.get("id") or data.get("post_id") or data.get("cms_post_id"),
                "status": data.get("status") or status,
                "slug": data.get("slug") or slug.strip("/"),
            },
        }


def configured_for_publish(config: Optional[Dict[str, Any]]) -> bool:
    config = config or {}
    cms_type = str(config.get("cms_type") or "custom").lower()
    if not config.get("api_url"):
        return False
    if cms_type == "wordpress":
        return bool(config.get("api_key"))
    return bool(config.get("api_key"))
