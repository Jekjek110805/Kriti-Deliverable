# Blog Automation Workflow and Sales Replication

## Outcome

Kriti now has a controlled automation path for:

1. checking the existing website before proposing or writing content;
2. creating a blog draft from the MAAI Blog Production SOP;
3. running SEO, fact-risk and brand/style validation;
4. keeping human approval before a live release;
5. creating a real remote CMS draft or publishing through an authenticated API;
6. monitoring the published URL through the existing GSC workflow; and
7. producing actionable suggestions for existing blog posts.

The same orchestration pattern can be reused for sales automation by changing
the research source, generated artifact, validation rules and destination.

## Current live-site status

Updated 13 July 2026:

- `selfstorage.help` is a Next.js website hosted on Vercel, source at
  `github.com/devmaai/self-v1`, using a self-hosted TinaCMS (Git-backed —
  content is Markdown files in `content/posts`, not a REST API TinaCMS itself
  exposes for writes; Tina Cloud's own content token is read-only).
- Confirmed real schema (from that repo's `tina/config.ts`): collection
  `post`, path `content/posts`, format `.md`, fields `title` (string),
  `date` (datetime), `excerpt` (string), `coverImage` (image, optional),
  `published` (boolean), `body` (rich-text/markdown).
- `integrations/cms_client.py`'s `CMSPublisher` now supports `cms_type=github`:
  it commits a Markdown file (built by `draft_to_tina_markdown()`, matching
  the schema above) to a new branch and opens a pull request — it never
  commits directly to the base branch. Going live still requires a human to
  merge the PR; the adapter always reports `status: cms_draft`, never
  `published`, regardless of the `publish_now` flag, since opening a PR is
  never itself "live."
- This was manually validated end-to-end against the real repo (branch → file
  → PR → merge → Vercel deploy → live URL, then reverted) before this adapter
  was written, so the schema and workflow are confirmed, not assumed.
- Not yet done: no `CMS_TYPE=github` / `CMS_GITHUB_OWNER` / `CMS_GITHUB_REPO` /
  `CMS_API_KEY` values are set in this Kriti checkout's running environment —
  set those (see `.env.example`) to make `/api/publish` actually usable for
  this site. Use a fine-grained GitHub PAT scoped to only that repo
  (Contents: read/write, Pull requests: read/write, Metadata: read).
- WordPress is not applicable here — the site does not expose a WordPress
  REST API.

The UI and API report missing configuration as a blocker; they never return a
fake post ID or claim that a local JSON file (or an open, unmerged PR) is live.

## End-to-end blog workflow

```text
SEMrush keyword file or approved keyword
        |
        v
Read selfstorage.help sitemap
        |
        +--> match an existing page? --> recommend improvement/no action
        |
        +--> real content gap? -------> recommend a new blog/landing page
        |
        v
Human approves the topic
        |
        v
Generate to MAAI blog template
  - keyword-led title, meta and slug
  - TLDR at the top
  - introduction and at least five H2 sections
  - short, direct paragraphs
  - FAQ and conversion CTA
  - verified internal links only
  - image brief and alt text
        |
        v
Automated quality gates
  - SEO gate
  - fact-risk check
  - brand/house-style review
  - media readiness
        |
        +--> failed/review --> human fixes and reruns checks
        |
        v
Human final approval
        |
        v
Authenticated remote CMS/API call
  - status=draft: create a remote review draft
  - status=publish: release the approved post
        |
        v
Verify URL + sitemap, then monitor in GSC
```

## MAAI template contract

The machine-enforced template is implemented in
`agents/blog_automation.py` as `maai-blog-sop-v1`. It operationalises the
source checklist in `docs/stage1_seo_business_logic/Kriti_Process_1.md`.

Every generated artifact contains:

- primary keyword, title, URL slug and meta description;
- two-to-three sentence TLDR at the top;
- introduction;
- at least five substantive H2 sections;
- FAQ questions and answers;
- next-step CTA;
- internal links selected only from the live sitemap inventory;
- image brief, alt text and media-readiness status;
- rendered Markdown content;
- template version, word count, timestamps and audit flags; and
- a checklist showing which structural requirements are ready.

The model is not allowed to invent internal URLs. Python filters every returned
link against sitemap-backed allowed URLs. Missing media remains visibly blocked
instead of creating a broken image URL.

## Existing-blog suggestion section

The Blog Automation page includes **Suggestions from Existing Blogs**. It reads
the public sitemap, fetches each `/blog/` article and reports evidence-backed
improvements such as:

- remove or replace public test content;
- expand thin articles;
- improve title/meta structure;
- add TLDR, H2 sections or FAQ coverage;
- add a relevant conversion CTA;
- add two or three contextual internal links; and
- add useful media and complete alt text.

Source: `integrations/site_inventory.py`.

This inventory also feeds the SEMrush recommendation engine. In Discover, the
keyword-upload mode now accepts an existing website URL. A recommendation can
only say `Existing Blog` or `Existing Landing Page` when a real sitemap page
matches the cluster; otherwise it stays `New ...`.

## APIs

### Create and validate a blog

`POST /api/automation/blogs/run`

```json
{
  "keyword": "self storage SEO",
  "title": "",
  "audience": "Independent self-storage operators in the USA",
  "word_count": 1500,
  "site_url": "https://www.selfstorage.help",
  "featured_image_url": "",
  "stage_to_cms": false,
  "publish_now": false
}
```

`stage_to_cms=false` creates and validates a local review draft.
`stage_to_cms=true` creates a remote CMS draft after checks pass.
`publish_now=true` also requires Approval Queue approval and a passing
validation record before it can make the authenticated live call.

### Audit existing blogs

`GET /api/automation/blogs/existing-suggestions?site_url=https://www.selfstorage.help`

### Check readiness

`GET /api/automation/blogs/status`

### Configure and test publishing

- `POST /api/integrations/cms/configure`
- `POST /api/integrations/cms/test`
- `GET /api/integrations/cms/status`

### Publish an approved artifact

`POST /api/publish`

Unlike the previous placeholder, this route calls the remote adapter and only
saves a publish record after a 2xx response.

## SelfStorage.help publishing endpoint contract

**Superseded for selfstorage.help specifically** — the section below describes
a hypothetical custom REST endpoint the site would need to build. That's no
longer necessary: selfstorage.help runs Git-backed TinaCMS, so
`CMS_TYPE=github` (see "Current live-site status" above and
`integrations/cms_client.py`) publishes by opening a pull request directly
against `github.com/devmaai/self-v1`, no new site endpoint required. This
section is kept as the fallback contract for a future site that isn't
Git-backed and does need a real custom API.

Because SelfStorage.help is a custom Next.js/Vercel site, add a protected
server-side route in that site's repository, for example:

`POST https://www.selfstorage.help/api/content/publish`

Request header:

```text
Authorization: Bearer <CMS_API_KEY>
Content-Type: application/json
```

Request body from Kriti:

```json
{
  "keyword": "self storage SEO",
  "title": "Self Storage SEO: A Practical Guide for Independent Operators",
  "content": "TLDR\n\n...",
  "content_format": "markdown",
  "slug": "self-storage-seo",
  "meta_description": "...",
  "status": "draft",
  "client": "selfstorage.help",
  "featured_image_url": "https://...",
  "source": "kriti-blog-automation"
}
```

Required 2xx response:

```json
{
  "id": "post_123",
  "status": "draft",
  "slug": "self-storage-seo",
  "url": "https://www.selfstorage.help/blog/self-storage-seo",
  "edit_url": "https://.../admin/posts/post_123"
}
```

The site endpoint must:

1. authenticate the bearer token using a server-side secret;
2. validate title, slug, content, status and metadata;
3. reject duplicate slugs unless explicitly updating the same post;
4. store draft/live state in the site's real content source;
5. trigger the required Vercel revalidation/deployment;
6. return a stable ID and canonical URL; and
7. log actor, timestamp and content version without logging the token.

Once deployed, configure Kriti with:

```text
CMS_TYPE=custom
CMS_API_URL=https://www.selfstorage.help/api/content/publish
CMS_API_KEY=<secret token>
```

Use Secret Manager/environment variables in Cloud Run. The local integration
form writes `data/cms_config.json`, which is ignored by Git and is intended only
for local development.

## Tech stack

| Layer | Technology | Responsibility |
|---|---|---|
| UI | Single-file HTML/CSS/JavaScript | Automation form, draft review, validation status, existing-blog suggestions, CMS setup |
| API | FastAPI + Pydantic | Request contracts, orchestration, validation gates and integration endpoints |
| Deterministic strategy | Python | Parsing, clustering, scoring, sitemap evidence, link allow-listing and output normalisation |
| AI generation/reasoning | OpenRouter-compatible chat API | Strategy judgement and reader-facing draft copy |
| HTTP integrations | `requests` | Sitemap/page reads and authenticated CMS publishing |
| Content discovery | XML sitemap + public HTML | Existing-page inventory and refresh evidence |
| Runtime artifacts | JSON under `outputs/` | Draft, validation and confirmed remote-publish audit records |
| Search performance | Google Search Console API/upload | Opportunity discovery and post-publication monitoring |
| Deployment | Docker + Google Cloud Run | Kriti runtime; secrets supplied through environment/Secret Manager |
| Website | Next.js + Vercel | Current SelfStorage.help frontend and future protected publish endpoint |

## Replicating the pattern for sales automation

The reusable pattern is **discover -> decide -> generate -> validate -> approve
-> execute -> monitor**. Keep the orchestrator and governance; replace the
domain-specific components.

| Blog automation | Sales automation equivalent |
|---|---|
| SEMrush/GSC opportunity | CRM lead, intent signal or target account |
| Existing-page sitemap check | Existing contact, account, opportunity and recent-touch check |
| New vs existing content decision | New lead vs nurture existing account vs no action |
| Blog brief/template | Account research brief and outreach sequence template |
| Blog draft | Personalised email, LinkedIn task or call brief |
| SEO/fact/brand gates | Data quality, consent, claim, tone and deliverability gates |
| Human publish approval | Sales-owner send/task approval |
| CMS API | CRM/sequence provider API |
| GSC monitoring | Reply, meeting, pipeline and revenue monitoring |

### Sales workflow

```text
CRM + approved intent sources
        -> dedupe/contact-history check
        -> ICP and opportunity scoring
        -> new outreach / nurture / no-action decision
        -> account brief + personalised sequence
        -> consent, accuracy, tone and deliverability validation
        -> sales-owner approval
        -> CRM/sequence API execution
        -> replies, meetings, opportunities and revenue attribution
```

### Components to reuse unchanged

- FastAPI endpoint/orchestrator pattern;
- Pydantic request and response contracts;
- human approval gates and audit records;
- configuration/status/test/publish integration pattern;
- deterministic pre-processing before AI reasoning;
- allow-listed evidence passed to the model; and
- monitoring separated from generation.

### Components to replace

- sitemap inventory -> CRM/account/contact inventory;
- keyword clustering -> lead/account deduplication and buying-signal grouping;
- blog prompt/template -> outreach/call/sequence templates;
- SEO gate -> consent, data quality, brand, deliverability and claim gates;
- CMS publisher -> HubSpot/Salesforce/sequence-provider adapter; and
- GSC metrics -> reply, meeting, SQL, pipeline and revenue metrics.

### Sales safety rules

- Do not scrape or contact people without a lawful source and permitted use.
- Do not let the model invent company facts, personal details or previous
  interactions.
- Treat unsubscribe/suppression lists as hard blocks.
- Require approval for first contact and high-value/high-risk accounts.
- Rate-limit by mailbox/domain and monitor bounces and complaints.
- Store credentials only in a secret manager.
- Keep every send/action idempotent so retries cannot duplicate outreach.

## Operator checklist

1. Open **Content -> Blog Automation**.
2. Run **Analyze Existing Blogs** and resolve the highest-priority gaps.
3. Upload SEMrush keywords in Discover with the existing-site URL populated.
4. Approve a `New Blog` recommendation.
5. Create and validate the draft in Blog Automation.
6. Add approved media and verify facts/links.
7. Approve the keyword/final review.
8. Connect and test the custom website publishing endpoint.
9. Create a remote draft, review it on the site, then publish live.
10. Verify the canonical URL and sitemap, then monitor it in GSC.
