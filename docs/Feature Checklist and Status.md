# MAAI Blog Automation — Feature Checklist

Status as of 13 July 2026, based on direct code inspection and live verification
this session (not assumptions) — see `Blog Automation Workflow and Sales
Replication.md` for the full workflow write-up.

## Section A — New Content Suggestions (SEMrush)

- ✅ SEMrush XLSX upload & parsing — `/api/stage1a/analyze` (source_type=keyword_research), hand-rolled XLSX parsing
- ✅ Keyword normalization & dedup — `agents/funnel_topics.py` (`_topic_key()`)
- ✅ Keyword clustering into topics — `build_topics()`
- ✅ TOFU/MOFU/BOFU funnel classification — `classify_stage()`, with inferred-intent fallback when SEMrush leaves Intent blank
- ✅ Content recommendation per cluster (New Blog / New Landing Page / No Change) — `recommendation` field
- ✅ Priority, confidence, commercial potential, reason, suggested title/CTA — all present in the topic dict
- ✅ Card/container UI with full-detail modal on click

## Section B — Existing Blog Suggestions

- ⚠️ Partial. `integrations/site_inventory.analyze_existing_blogs()` does real structural analysis (missing TLDR/H2s/FAQ/CTA, thin content, meta description length, alt text, internal links) from live sitemap + HTML crawl.
- ❌ Missing: GSC performance data (position/impressions/clicks/CTR) is not joined to these suggestions — it's pure on-page/content analysis, not "page ranks position 8 with weak CTR" reasoning.
- ❌ Missing: concrete suggested H2 titles / FAQ questions / meta-title rewrite (only flags "add an H2 outline," not what the H2s should say).
- ❌ Confidence score and target-keyword identification per page.
- This is the least-built section of the spec — top candidate for the next work phase.

## Section C — Blog Generation & Publishing

- ✅ Content brief generation — `/api/brief/generate`
- ✅ Full blog draft generation, SOP-compliant — `agents/blog_automation.generate_blog_draft()` (consolidated this session — previously a separate, buggy generator existed in parallel)
- ✅ Blog template enforcement (1 H1, TLDR, 5+ H2s, FAQ, CTA, verified-only internal links, house style, word count retries) — `template_checklist` in the draft output
- ⚠️ Quality validation — deterministic only. SEO gate / fact-check / brand-review all real and working (`/api/validate`).
- ❌ AI-assisted validation does not exist — no intent-alignment, audience-fit, completeness, or tone check by an LLM; spec asks for this explicitly (§11), only regex/rule checks exist today.
- ✅ CMS draft creation — built and live-tested: `CMSPublisher` (`cms_type=github`) opens a real branch + file + PR against `devmaai/self-v1`, confirmed via `/api/integrations/cms/test` (push access verified) and an actual end-to-end manual test (post created, rendered correctly, merged, then cleanly reverted).
- ✅ Publish requires explicit human approval — `/api/publish` gates on validation pass + queue approval; for GitHub specifically, publishing is never instant — a human must merge the PR regardless of the `publish_now` flag. Strongest gate of any CMS type built so far.

## Approval / Human-in-the-loop

- ✅ Topic-level approval queue — `/api/queue/*`
- ✅ Brief & final-review approval gates + audit log — `/api/governance/*` (confirmed this session: these are two distinct, complementary stages, not a duplicate system)
- ✅ No autonomous production publishing — verified structurally (code) and behaviorally (deliberately did not auto-merge PRs during testing)

## Documentation (spec §17)

- ⚠️ Partial. `docs/Blog Automation Workflow and Sales Replication.md` exists, is substantive, and was updated this session with the real Tina/GitHub findings.
- ❌ The spec asks for a specific file `docs/BLOG_AUTOMATION_WORKFLOW_AND_TECH_STACK.md` with 16 defined subsections — does not exist under that name/structure.

## Security & Cost Controls (spec §19)

- ✅ API keys via env vars, never hardcoded, `.env` gitignored — confirmed structurally and live (`.env` is `!!`-ignored)
- ⚠️ Process risk observed, not a code issue: during this session, GitHub tokens were pasted directly into chat twice — the app's own credential handling is correct, but worth a process reminder going forward.
- ✅ Model-cost tier config exists — `MODEL_TIERS` with `cost_per_1k_tokens`, `/api/observability/costs`, `/api/models/cost-saving-tips` endpoints all present.
- ❌ Not actually wired up: `record_model_usage()` is defined but never called anywhere in the codebase. The observability endpoints exist but `outputs/model_usage.json` never gets populated in practice. So "model usage and costs are observable" is not true today, despite the scaffolding existing.

## Summary — spec's own §22 Acceptance Criteria

| Criterion | Status |
|---|---|
| SEMrush XLSX upload | ✅ |
| Keywords normalized/validated | ✅ |
| Keywords clustered | ✅ |
| Every cluster gets funnel stage | ✅ |
| Every cluster gets content recommendation | ✅ |
| Suggests blogs/landing pages | ✅ |
| Existing pages checked before new content | ✅ |
| Existing blogs get specific improvement suggestions | ⚠️ Partial |
| Approved topics → content briefs | ✅ |
| Approved briefs → full drafts | ✅ |
| Drafts follow blog template | ✅ |
| Drafts pass quality validation | ⚠️ Deterministic only, no AI-assisted layer |
| Human approves/rejects each stage | ✅ |
| Approved blogs → CMS drafts | ✅ (built + verified this session) |
| Direct publishing requires human approval | ✅ |
| Workflow/tech-stack docs generated | ⚠️ Exists, wrong filename/structure |
| API keys remain secure | ✅ code / ⚠️ process |
| Model usage & costs observable | ❌ Scaffolded, not wired up |

**Bottom line**: 12 of 18 fully done, 5 partial, 1 not actually functional despite
existing endpoints. The two most concrete gaps worth tackling next are the
AI-assisted validation layer and wiring `record_model_usage()` into the actual
LLM call sites — both are scoped, contained pieces of work, unlike Section B
which is a bigger lift.
