# MAAI — Stage 1A SEO Opportunity Analysis: Roadmap & Status

> **MAAI is the system. Kriti is the client.** MAAI is an **AI SEO Decision
> Platform** that reads Google Search Console data and recommends which existing
> pages to improve first, why, and what to do next. Scope is opportunity
> *analysis* only — no blog writing, CMS, or publishing.

## ✅ Completed (built & verified locally)

**Analysis engine** ([integrations/hermes_client.py](../integrations/hermes_client.py))
- Reads every GSC row (CSV/XLSX upload or live GSC API — same analysis)
- Per keyword: landing page, clicks, impressions, CTR, position, intent
  (BOFU/MOFU/TOFU), commercial potential, score, confidence, priority, reason
- Four recommendations: No Change · Improve Existing · Expand Existing · Create New Content
- Landing page resolution + clickable absolute URLs (existing match or suggested new)
- Never recommends without a reason
- Deterministic (reproducible, auditable, no LLM)

**Live Google Search Console** ([integrations/gsc_client.py](../integrations/gsc_client.py))
- Service-account auth; `get_search_analytics()`; typed error handling
- Live-first with automatic CSV/XLSX fallback (CSV always works)

**Dashboard** ([static/index.html](../static/index.html))
- Summary cards: Total, Critical, High, Improve Existing, Expand Existing, Create New, No Change
- Results table: #, Priority, Keyword, Landing Page (clickable), Pos, Imp,
  Clicks, CTR, Intent, Commercial, Score, Recommendation, Content Type,
  Confidence, Reason
- Filter bar: Recommendation, Intent, Priority, Landing Page, Position, Score
- Detail panel: metrics, why, suggested action, next step, clickable landing page
- Inline approval: status badge + Approve / Reject / Block (nothing automatic)

**Workflow wiring** ([jobs.py](../jobs.py))
- Analysis job writes both the CSV and the approval-queue YAML, so the
  Approval Queue populates after every upload

## 🔜 Remaining / future

| Item | Notes |
|---|---|
| **Production deploy of live GSC** | Deployed Cloud Run app needs the credential via Secret Manager + 2 env vars (`deploy/` scripts ready). Local is connected. |
| Stage 1B depth | Most already present (No Change, content type, confidence). Future: keyword-gap analysis, richer "blog vs landing" reasoning. |
| Polish | Light-theme pass on new controls, mobile responsiveness of the wide table. |

## Implementation order (delivered)
1. ✅ Backend wiring — approval-queue YAML + spec recommendation labels
2. ✅ Dashboard parity — summary cards + Commercial Potential & Reason columns
3. ✅ Filter bar
4. ✅ Detail panel enrichment
5. ✅ Inline approval status + actions
6. ✅ End-to-end verification + CTR percent-parsing fix

## The question MAAI answers
> "Looking at this Google Search Console data, what should we improve first,
> which landing page is affected, why, and what should we do next?"
