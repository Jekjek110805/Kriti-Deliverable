# MAAI — Tech Stack & Automation Workflow

> A shareable reference describing how the blog-automation system is built and
> how work flows through it end to end — written so the same pattern can be
> replicated for other domains (e.g. a sales pipeline).

---

## 1. What this system does (in one paragraph)

MAAI turns search data into published, optimized content with a human approving
every important step. You feed it either your site's own performance data
(Google Search Console) or market keyword research (SEMrush/Ahrefs). It scores
and clusters that data into ranked opportunities or funnel-grouped topics, lets
a human approve what to act on, then automatically generates a brief, writes a
full draft, runs quality checks, and opens a publish-ready pull request to the
website. Nothing goes live without a person's sign-off.

The core design principle: **deterministic Python does the heavy, repeatable
work; the LLM only does the reasoning that genuinely needs judgement; and a
human holds the gates.**

---

## 2. Tech stack

| Layer | Choice | Notes |
|-------|--------|-------|
| **Backend** | Python + **FastAPI** (single app, `app/api.py`) | REST endpoints; runs under `uvicorn`. |
| **Frontend** | **Single static `static/index.html`** — vanilla HTML/CSS/JS | **No framework, no build step.** Served directly by FastAPI. Easy to host anywhere. |
| **Storage** | **Flat files** under `outputs/` and `data/` (JSON / CSV / YAML) | No database. Each artifact (draft, validation, queue state, audit log) is a file. Simple to inspect, back up, and reason about. |
| **LLM** | **OpenRouter** HTTP API (`integrations/hermes_llm.py`) | Model set via `OPENROUTER_MODEL` (currently a free Nemotron model). Swappable for Claude/OpenAI by changing the client + env. |
| **Deterministic engine** | Pure Python (`agents/funnel_topics.py`) | Keyword clustering + TOFU/MOFU/BOFU classification. No network, no randomness — same input → same output. |
| **Publishing** | **GitHub REST API** → Git-backed CMS (TinaCMS) (`integrations/cms_client.py`) | Also supports WordPress and a generic custom HTTP endpoint. |
| **Animations** | Self-hosted **lottie-web** (`static/lottie.min.js`) | No CDN/WASM dependency. |
| **Hosting** | Container-friendly (Google Cloud Run) | `PORT` injected by the platform. |

**Why these choices matter for replication:** the stack is intentionally
lightweight. A monolithic FastAPI app + one static HTML file + flat-file storage
means the whole thing can be copied, re-pointed at a new domain, and run with
almost no infrastructure. There is no database migration, no build pipeline, and
no framework lock-in to reproduce.

---

## 3. The automation workflow (end to end)

```
  ┌─────────────────────────────────────────────────────────────────┐
  │ 1. INGEST                                                         │
  │    GSC CSV/live  → site performance (query, page, clicks, pos.)  │
  │    SEMrush CSV   → market keywords (volume, intent, KD, CPC)      │
  │    Pure-Python parse + normalize + dedupe                        │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 2. SCORE & CLASSIFY  (deterministic)                             │
  │    GSC    → ranked page opportunities (Improve/Expand/Create)    │
  │    SEMrush→ keyword clusters grouped by funnel (TOFU/MOFU/BOFU)  │
  │    + optional LLM enrichment on the TOP items only (cost control)│
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 3. HUMAN GATE #1 — Approval Queue                                │
  │    A person Approves / Rejects / Blocks each opportunity.        │
  │    Persisted to outputs/approval_queue_state.json                │
  └─────────────────────────────────────────────────────────────────┘
                              │ approved item
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 4. BRIEF  → 5. DRAFT  → 6. VALIDATE   (one automated chain)      │
  │    Brief:    intent-aware outline, FAQs, SEO requirements        │
  │    Draft:    SOP-template article (LLM), verified internal links │
  │    Validate: SEO gate + fact check + brand review (deterministic)│
  └─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
     passes all gates                    fails a gate
              │                               │
              ▼                               ▼
  ┌────────────────────┐        ┌──────────────────────────────────┐
  │ ready to publish   │        │ 7. DRAFT BLOGS library           │
  │                    │        │    Draft is kept safely, with     │
  │                    │        │    plain-language "what to fix".  │
  │                    │        │    Human edits → re-validate →    │
  │                    │        │    becomes ready. Nothing is lost.│
  └────────────────────┘        └──────────────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 8. HUMAN GATE #2 — Publish approval                              │
  │    A person approves the specific item for publishing.          │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 9. PUBLISH  (GitHub / TinaCMS)                                   │
  │    Create branch → commit Markdown → open Pull Request.          │
  │    NEVER commits to main directly.                              │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 10. HUMAN GATE #3 — Merge the PR  (the "go live" decision)       │
  │     Site rebuilds & deploys → post is live.                     │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 11. MONITOR — track performance, feed back into scoring         │
  └─────────────────────────────────────────────────────────────────┘
```

**Three human gates** keep a person in control: (1) which opportunities to
pursue, (2) approval to publish, (3) merging the PR. Everything between the
gates is automated.

---

## 4. Key components (where each piece lives)

| Concern | File / module | Key entry points |
|---------|---------------|------------------|
| API + orchestration | `app/api.py` | all `/api/*` endpoints |
| Keyword clustering + funnel | `agents/funnel_topics.py` | `build_topics`, `group_by_funnel` |
| LLM topic strategy (reasoning layer) | `agents/ai_topic_strategist.py` | `enrich_topics` |
| Blog draft generation (SOP template) | `agents/blog_automation.py` | `generate_blog_draft` |
| Quality gates | `app/api.py` | `run_seo_gate`, `run_fact_check`, `run_brand_review` |
| LLM client | `integrations/hermes_llm.py` | `hermes_generate` |
| Publishing adapter | `integrations/cms_client.py` | `CMSPublisher`, `draft_to_tina_markdown` |
| Existing-page inventory | `integrations/site_inventory.py` | `inventory_existing_pages` |
| UI (all screens) | `static/index.html` | one file |

### Representative endpoints
- `POST /api/stage1a/analyze` — GSC upload → ranked opportunities
- `POST /api/integrations/semrush/recommendations` — SEMrush upload → funnel topics
- `GET/POST /api/queue…` — approval queue (approve/reject/block, status, history)
- `POST /api/brief/generate` — content brief
- `POST /api/content/write` / `POST /api/automation/blogs/run` — draft generation
- `GET/PATCH/DELETE /api/drafts…` — Draft Blogs library (CRUD)
- `POST /api/validate` — SEO/fact/brand gates
- `POST /api/publish` — gated publish (opens the PR)
- `GET /api/governance/*` — gates, audit log, roles, compliance

---

## 5. Integrations

| Integration | Purpose | Config (env) |
|-------------|---------|--------------|
| Google Search Console | Live/uploaded site performance | `GSC_SITE_URL`, `GSC_CREDENTIALS_PATH` (OAuth service-account JSON) |
| SEMrush / Ahrefs | Keyword market data (CSV upload works with no key) | `SEMRUSH_API_KEY` (optional) |
| Site Crawler | Map existing pages via sitemap | none |
| LLM (OpenRouter) | Draft writing + topic reasoning | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` |
| CMS publishing (GitHub/TinaCMS) | Open publish PRs | `CMS_TYPE=github`, `CMS_GITHUB_OWNER/REPO/BASE_BRANCH/CONTENT_PATH`, `CMS_API_KEY` (fine-grained PAT: Contents R/W, Pull requests R/W, Metadata R) |
| Notifications | Slack + email alerts | notification config |

All real secrets live only in `.env` (gitignored). `.env.example` is the
committed, blank template. **The server reads `.env` once at startup — restart
after any change.**

---

## 6. How to replicate this for a different domain (e.g. Sales)

The architecture generalizes cleanly. To adapt it to a **sales** pipeline,
keep the same skeleton and swap the domain-specific pieces:

1. **Ingest** — replace GSC/SEMrush parsers with your sales data source
   (CRM export, lead list, call transcripts). Keep the "detect file type →
   pick the right flow" pattern.
2. **Score & classify (deterministic)** — replace funnel/SEO scoring with your
   sales scoring (lead score, deal stage, ICP fit). Keep it pure-Python so it's
   repeatable and explainable — this is what makes the recommendations
   defensible to a human reviewer.
3. **LLM reasoning layer** — reuse the "enrich only the top N items" pattern
   (`ai_topic_strategist.py`) for the judgement calls (e.g. suggested outreach
   angle, objection handling, next-best-action). Everything else stays rule-based
   for cost and consistency.
4. **Human gates** — keep all three gates. For sales: (1) approve which leads to
   work, (2) approve the generated outreach/proposal, (3) approve sending.
5. **Generation** — swap `generate_blog_draft` for your artifact generator
   (email sequence, proposal, call script) using the same SOP-template +
   validation pattern.
6. **Validation gates** — replace SEO/fact/brand with sales checks
   (compliance, tone, personalization completeness, no over-promising).
7. **Delivery** — replace the GitHub/TinaCMS adapter with your delivery channel
   (email/CRM/Slack), keeping the "never send without human approval" rule.
8. **Reuse as-is:** the FastAPI + static-HTML shell, flat-file storage, approval
   queue, Draft library, governance/audit log, and the count-up/loader UI
   patterns all transfer directly.

**The transferable idea:** *deterministic scoring + thin LLM reasoning + a
human-approved pipeline with a draft-safety-net and an audit trail.* That
pattern is domain-agnostic — only the inputs, scoring rules, generated artifact,
and delivery channel change.

---

## 7. Guardrails worth keeping

- **Human-in-the-loop by default** — automation prepares work; people approve it.
- **Never auto-publish/auto-send** — the final "go live" is always a human action
  (here, merging the PR).
- **Nothing is lost** — work that fails a check is saved to the Draft library with
  clear reasons, not discarded.
- **Full audit trail** — every approve/reject/publish is logged with who, what,
  when, and the item title.
- **Secrets only in `.env`** (gitignored); never in code or git history.
- **Graceful degradation** — if the LLM or an integration is unavailable, the
  deterministic core still works and explains what was skipped.
