"""Real CMS publishing adapters used by Kriti's gated publish workflow.

Supported transports:
* WordPress REST API using an Application Password or bearer token.
* A custom HTTPS endpoint for Git-backed/Next.js sites such as SelfStorage.help.
* GitHub (for Git-backed CMSs like TinaCMS): commits a Markdown file to a new
  branch and opens a pull request. Nothing is ever committed straight to the
  base branch — going live requires a human to merge the pull request.

This module never treats a local JSON record as a successful publication. A
publish call succeeds only after the remote CMS (or GitHub) returns a 2xx
response for every step.
"""

from __future__ import annotations

import base64
import html
import re
from datetime import datetime, timezone
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


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-") or "post"


def draft_to_tina_markdown(
    *,
    title: str,
    content: str,
    slug: str,
    meta_description: str,
    featured_image_url: str = "",
    published: bool = True,
) -> Dict[str, str]:
    """Build a Tina `post`-collection Markdown file: frontmatter + plain-markdown
    body. Field names match the real schema in the target site's tina/config.ts
    (title, date, excerpt, coverImage, published, body) — confirmed against
    devmaai/self-v1, not guessed.
    """
    title = (title or "").strip()
    if not title:
        raise CMSPublishError("A title is required to build a Tina post.")
    body = (content or "").strip()
    if not body:
        raise CMSPublishError("Post content is required to build a Tina post.")

    filename_slug = _slugify(slug or title)
    excerpt = (meta_description or "").strip().replace("'", "\\'")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00.000Z")

    frontmatter = [
        "---",
        f"title: {title}",
        f"date: {date_str}",
        f"excerpt: '{excerpt}'",
    ]
    cover = (featured_image_url or "").strip()
    if cover:
        frontmatter.append(f"coverImage: {cover}")
    frontmatter.append(f"published: {'true' if published else 'false'}")
    frontmatter.append("---")
    frontmatter.append("")

    return {
        "filename": f"{filename_slug}.md",
        "markdown": "\n".join(frontmatter) + body + "\n",
        "slug": filename_slug,
    }


class CMSPublisher:
    def __init__(self, config: Dict[str, Any], session: Any = requests) -> None:
        self.config = config or {}
        self.session = session
        self.cms_type = str(self.config.get("cms_type") or "custom").strip().lower()
        if self.cms_type == "custom_api":
            self.cms_type = "custom"
        if self.cms_type not in ("wordpress", "custom", "github"):
            raise CMSPublishError(
                f"CMS type '{self.cms_type}' is not implemented. Use wordpress, custom or github."
            )
        if self.cms_type == "github":
            self.owner = str(self.config.get("owner") or "").strip()
            self.repo = str(self.config.get("repo") or "").strip()
            self.base_branch = str(self.config.get("base_branch") or "main").strip()
            self.content_path = str(self.config.get("content_path") or "content/posts").strip().strip("/")
            self.token = str(self.config.get("api_key") or "").strip()
            if not (self.owner and self.repo and self.token):
                raise CMSPublishError("GitHub publishing requires owner, repo and a token (api_key).")
        else:
            self.api_url = _clean_url(str(self.config.get("api_url") or ""))

    def _headers(self) -> Dict[str, str]:
        if self.cms_type == "github":
            return {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        api_key = str(self.config.get("api_key") or "").strip()
        username = str(self.config.get("username") or "").strip()
        if username and api_key:
            token = base64.b64encode(f"{username}:{api_key}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        elif api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _github_api(self, path: str) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repo}{path}"

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
        if self.cms_type == "github":
            response = self.session.get(self._github_api(""), headers=self._headers(), timeout=30)
            self._raise_for_response(response, "connection test")
            data = self._response_json(response)
            permissions = data.get("permissions") or {}
            if not permissions.get("push"):
                raise CMSPublishError(
                    f"Token has no write access to {self.owner}/{self.repo} "
                    "(need Contents: read/write and Pull requests: read/write)."
                )
            return {
                "connected": True,
                "cms_type": "github",
                "repo": data.get("full_name") or f"{self.owner}/{self.repo}",
                "base_branch": self.base_branch,
            }

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
        if self.cms_type == "github":
            tina = draft_to_tina_markdown(
                title=title,
                content=content,
                slug=slug,
                meta_description=meta_description,
                featured_image_url=featured_image_url,
                published=publish_now,
            )
            branch_name = f"maai/blog/{tina['slug']}"
            file_path = f"{self.content_path}/{tina['filename']}"

            ref_response = self.session.get(
                self._github_api(f"/git/ref/heads/{self.base_branch}"),
                headers=self._headers(),
                timeout=30,
            )
            self._raise_for_response(ref_response, "base branch lookup")
            base_sha = self._response_json(ref_response)["object"]["sha"]

            branch_response = self.session.post(
                self._github_api("/git/refs"),
                json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
                headers=self._headers(),
                timeout=30,
            )
            self._raise_for_response(branch_response, "branch creation")

            encoded_content = base64.b64encode(tina["markdown"].encode("utf-8")).decode("ascii")
            commit_response = self.session.put(
                self._github_api(f"/contents/{file_path}"),
                json={
                    "message": f"content: add blog post '{title}'",
                    "content": encoded_content,
                    "branch": branch_name,
                },
                headers=self._headers(),
                timeout=30,
            )
            self._raise_for_response(commit_response, "file commit")

            pr_response = self.session.post(
                self._github_api("/pulls"),
                json={
                    "title": f"Blog: {title}",
                    "head": branch_name,
                    "base": self.base_branch,
                    "draft": not publish_now,
                    "body": (
                        f"Automated blog draft for keyword **{keyword}**.\n\n"
                        "Generated by MAAI blog automation. Review the deploy preview "
                        "before merging — merging this pull request publishes the post.\n\n"
                        f"- File: `{file_path}`\n"
                        f"- Client: {client}\n"
                    ),
                },
                headers=self._headers(),
                timeout=30,
            )
            self._raise_for_response(pr_response, "pull request creation")
            pr_data = self._response_json(pr_response)
            return {
                "cms_type": "github",
                "cms_post_id": pr_data.get("number"),
                "status": "cms_draft",
                "url": pr_data.get("html_url") or "",
                "edit_url": pr_data.get("html_url") or "",
                "remote_response": {
                    "id": pr_data.get("number"),
                    "status": "open",
                    "slug": tina["slug"],
                    "branch": branch_name,
                    "file_path": file_path,
                },
            }

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
    if cms_type == "github":
        return bool(config.get("owner") and config.get("repo") and config.get("api_key"))
    if not config.get("api_url"):
        return False
    if cms_type == "wordpress":
        return bool(config.get("api_key"))
    return bool(config.get("api_key"))
