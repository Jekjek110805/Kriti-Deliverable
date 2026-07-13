import json
import unittest

from agents.blog_automation import generate_blog_draft
from integrations.cms_client import CMSPublisher, CMSPublishError, draft_to_tina_markdown, markdown_to_html
from integrations.site_inventory import analyze_existing_blogs, inventory_existing_pages


class FakeResponse:
    def __init__(self, body="", status_code=200, json_body=None):
        self.content = body.encode("utf-8")
        self.text = body
        self.status_code = status_code
        self._json_body = json_body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self._json_body is None:
            raise ValueError("not json")
        return self._json_body


class FakeSiteSession:
    sitemap = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/</loc></url>
      <url><loc>https://example.com/blog/testing</loc></url>
    </urlset>"""
    blog = """<html><head><title>Testing post</title>
    <meta name="description" content="Short description"></head>
    <body><h1>Testing</h1><p>Short placeholder copy.</p></body></html>"""

    def get(self, url, **kwargs):
        if url.endswith("sitemap.xml"):
            return FakeResponse(self.sitemap)
        if url.endswith("sitemap_index.xml"):
            return FakeResponse("", 404)
        return FakeResponse(self.blog)


class FakeCMSSession:
    def __init__(self):
        self.last_post = None

    def post(self, url, json=None, **kwargs):
        self.last_post = {"url": url, "json": json, "headers": kwargs.get("headers", {})}
        return FakeResponse(json_body={
            "id": "post_123",
            "status": json["status"],
            "url": "https://example.com/blog/test-post",
            "slug": json["slug"],
        })


class FakeGitHubSession:
    """Simulates the three GitHub calls a github-type publish makes, in order:
    GET ref sha -> POST create branch -> PUT commit file -> POST open PR.
    Also handles the plain repo GET used by test_connection()'s permission check.
    """

    def __init__(self, push_allowed=True):
        self.push_allowed = push_allowed
        self.calls = []

    def get(self, url, headers=None, **kwargs):
        self.calls.append(("GET", url, None))
        if url.endswith("/git/ref/heads/main"):
            return FakeResponse(json_body={"object": {"sha": "base-sha-123"}})
        # repo permission check (test_connection)
        return FakeResponse(json_body={
            "full_name": "devmaai/self-v1",
            "permissions": {"push": self.push_allowed},
        })

    def post(self, url, json=None, headers=None, **kwargs):
        self.calls.append(("POST", url, json))
        if url.endswith("/git/refs"):
            return FakeResponse(status_code=201, json_body={"ref": json["ref"]})
        if url.endswith("/pulls"):
            return FakeResponse(status_code=201, json_body={
                "number": 7,
                "html_url": "https://github.com/devmaai/self-v1/pull/7",
            })
        raise AssertionError(f"Unexpected POST {url}")

    def put(self, url, json=None, headers=None, **kwargs):
        self.calls.append(("PUT", url, json))
        return FakeResponse(status_code=201, json_body={"commit": {"sha": "file-commit-sha"}})


class BlogAutomationTests(unittest.TestCase):
    def test_sitemap_inventory_and_existing_blog_suggestions(self):
        session = FakeSiteSession()
        pages = inventory_existing_pages("https://example.com", session=session)
        self.assertEqual(len(pages), 2)
        result = analyze_existing_blogs("https://example.com", session=session)
        self.assertEqual(result["blog_count"], 1)
        self.assertEqual(result["blogs"][0]["priority"], "High")
        actions = [item["action"] for item in result["blogs"][0]["suggestions"]]
        self.assertIn("Replace or remove the test article", actions)

    def test_draft_uses_template_and_filters_invented_links(self):
        paragraph = (
            "You can review local demand, facility operations, customer needs and "
            "specific actions before deciding what belongs in the plan. " * 18
        )
        model_output = {
            "title": "Self Storage Business Plan: A Practical Guide",
            "meta_description": "A practical self storage business plan guide for independent facility owners preparing market, operations and financial sections.",
            "url_slug": "self-storage-business-plan",
            "tldr": "A focused plan turns your assumptions into decisions. Use evidence and review it as the facility changes.",
            "introduction": paragraph,
            "sections": [
                {"heading": f"Self Storage Business Plan Section {number}", "content": paragraph}
                for number in range(1, 6)
            ],
            "faq": [
                {"question": f"Planning question {number}?", "answer": paragraph}
                for number in range(1, 4)
            ],
            "cta": {"heading": "Next Steps", "content": paragraph, "label": "Get an audit", "target_url": "https://example.com/audit"},
            "internal_links": [
                {"url": "https://example.com/audit", "anchor": "request an audit"},
                {"url": "https://invented.example/page", "anchor": "invented"},
            ],
            "image": {"brief": "An operator reviewing a plan", "alt_text": "self storage business plan review"},
        }

        def generator(prompt, max_tokens=0):
            return json.dumps(model_output)

        draft = generate_blog_draft(
            keyword="self storage business plan",
            site_url="https://example.com",
            existing_pages=[
                {"url": "https://example.com/audit", "title": "Audit"},
                {"url": "https://example.com/services", "title": "Services"},
            ],
            featured_image_url="https://cdn.example.com/plan.jpg",
            generator=generator,
        )
        self.assertEqual(draft["template_version"], "maai-blog-sop-v1")
        self.assertGreaterEqual(draft["word_count_actual"], 1000)
        self.assertEqual(len(draft["faq"]), 3)
        self.assertTrue(all("invented.example" not in item["url"] for item in draft["internal_links"]))
        self.assertTrue(draft["full_content"].startswith("TLDR"))

    def test_custom_cms_publishes_only_after_remote_success(self):
        session = FakeCMSSession()
        publisher = CMSPublisher({
            "cms_type": "custom",
            "api_url": "https://example.com/api/content/publish",
            "api_key": "secret",
        }, session=session)
        result = publisher.publish(
            keyword="test post",
            title="Test Post",
            content="TLDR\n\nCopy",
            slug="test-post",
            meta_description="Description",
            publish_now=False,
        )
        self.assertEqual(result["cms_post_id"], "post_123")
        self.assertEqual(session.last_post["json"]["status"], "draft")
        self.assertEqual(session.last_post["headers"]["Authorization"], "Bearer secret")

    def test_wordpress_markdown_is_rendered_as_html(self):
        rendered = markdown_to_html(
            "TLDR\n\nSummary.\n\n## Main Section\n\nRead [the audit](https://example.com/audit)."
        )
        self.assertIn("<h2>Main Section</h2>", rendered)
        self.assertIn('<a href="https://example.com/audit">the audit</a>', rendered)

    def test_draft_to_tina_markdown_matches_real_schema(self):
        tina = draft_to_tina_markdown(
            title="Best Medicine for Fever",
            content="## Understand Fever\n\nBody copy.",
            slug="Best Medicine for fever",
            meta_description="A guide to fever medicine.",
            featured_image_url="/uploads/fever.jpg",
            published=True,
        )
        self.assertEqual(tina["filename"], "best-medicine-for-fever.md")
        self.assertTrue(tina["markdown"].startswith("---\ntitle: Best Medicine for Fever\n"))
        self.assertIn("excerpt: 'A guide to fever medicine.'", tina["markdown"])
        self.assertIn("coverImage: /uploads/fever.jpg", tina["markdown"])
        self.assertIn("published: true", tina["markdown"])
        self.assertIn("## Understand Fever", tina["markdown"])

    def test_draft_to_tina_markdown_requires_title_and_content(self):
        with self.assertRaises(CMSPublishError):
            draft_to_tina_markdown(title="", content="body", slug="x", meta_description="")
        with self.assertRaises(CMSPublishError):
            draft_to_tina_markdown(title="Title", content="", slug="x", meta_description="")

    def test_github_publish_opens_pr_never_direct_to_main(self):
        session = FakeGitHubSession()
        publisher = CMSPublisher({
            "cms_type": "github",
            "owner": "devmaai",
            "repo": "self-v1",
            "base_branch": "main",
            "content_path": "content/posts",
            "api_key": "fake-token",
        }, session=session)

        result = publisher.publish(
            keyword="fever medicine",
            title="Best Medicine for Fever",
            content="## Section\n\nBody copy.",
            slug="best-medicine-for-fever",
            meta_description="A guide.",
            publish_now=True,
            featured_image_url="",
        )

        # Even with publish_now=True, a github publish only opens a PR —
        # it must never report as actually "published" (live).
        self.assertEqual(result["status"], "cms_draft")
        self.assertEqual(result["cms_post_id"], 7)
        self.assertEqual(result["url"], "https://github.com/devmaai/self-v1/pull/7")

        methods = [call[0] for call in session.calls]
        self.assertEqual(methods, ["GET", "POST", "PUT", "POST"])
        branch_call = session.calls[1]
        self.assertEqual(branch_call[2]["sha"], "base-sha-123")
        self.assertTrue(branch_call[2]["ref"].startswith("refs/heads/maai/blog/"))
        commit_call = session.calls[2]
        self.assertIn("content/posts/best-medicine-for-fever.md", commit_call[1])
        pr_call = session.calls[3]
        self.assertEqual(pr_call[2]["base"], "main")
        self.assertFalse(pr_call[2]["draft"])  # publish_now=True -> ready for review, not a draft PR

    def test_github_test_connection_requires_push_permission(self):
        session = FakeGitHubSession(push_allowed=False)
        publisher = CMSPublisher({
            "cms_type": "github",
            "owner": "devmaai",
            "repo": "self-v1",
            "api_key": "fake-token",
        }, session=session)
        with self.assertRaises(CMSPublishError):
            publisher.test_connection()

    def test_github_requires_owner_repo_and_token(self):
        with self.assertRaises(CMSPublishError):
            CMSPublisher({"cms_type": "github"}, session=FakeGitHubSession())


if __name__ == "__main__":
    unittest.main()
