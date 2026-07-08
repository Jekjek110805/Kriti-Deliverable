# What Is Kriti? — Stage 1A Explainer

> **One sentence:** Kriti is an AI SEO decision platform that analyzes website
> data and recommends what actions to take — starting with identifying which
> existing pages should be optimized first.

Kriti is **not** another Google Search Console. It is an **AI decision-making
layer on top of** Google Search Console.

```text
Google Search Console
        │   raw SEO data (clicks, impressions, position, page, query)
        ▼
      Kriti
        │   AI analysis (score, intent, recommendation, priority)
        ▼
Actionable decisions  →  Human approves  →  Next stage
```

---

## Google Search Console vs Kriti

**Google Search Console is a reporting tool.** It tells you *what happened*:
clicks, impressions, ranking keywords, average position, which pages appear in
Google. It does **not** tell you what to do.

It shows you this:

| Keyword | Position | Impressions |
|---|---|---|
| clinic management software | 8 | 1,200 |

…and leaves you asking: *Is position 8 good? Should I improve this page or write
a new one? Is this my highest priority?* GSC doesn't answer those.

**Kriti answers them.** It reasons about that same row:

```
Keyword:          clinic management software
Current position: 8        → already on page 1 of Google
Impressions:      1,200    → strong, consistent demand
Commercial intent: High    → "software" = buyer keyword (BOFU)
Existing page:    Yes       → /best-clinic-management-software

→ Recommendation: Improve Existing
→ Reason: Already ranking page 1 for a commercial keyword with strong
  impressions. Optimizing this page beats writing new content.
→ Score: 93/100  →  Priority: Critical
```

### The doctor analogy
- **Google Search Console** is the lab report: blood pressure 150/95, sugar 210,
  cholesterol 260. Facts, no action.
- **Kriti** is the doctor: "High priority — lower the blood pressure; start
  treatment for the diabetes; fix diet before considering surgery." It turns raw
  measurements into a prioritized action plan.

---

## What Stage 1A actually does (the business value)

```text
Export GSC CSV  →  Upload to Kriti  →  Stage 1A analyzes every row
→ scores each opportunity  →  recommends an action  →  ranks by priority
→ explains why  →  Human approves which pages to improve
```

The upload is **input data**, not storage. Kriti reads real website performance
and answers the valuable question GSC can't:

> **"Given the Google Search Console data, which existing pages should we improve
> first, and why?"**

Stage 1A **finds and prioritizes opportunities. It does not write content yet.**

### What the agent reasons about, per row
1. **Is there an existing page?** (something to improve vs. a gap to fill)
2. **Is it already ranking?** (position — room to climb)
3. **Does Google show it often?** (impressions — real demand)
4. **Is the keyword commercial?** (BOFU / MOFU / TOFU intent)
5. **What's the right action?** (the recommendation below)

### The four recommendations
| Recommendation | When |
|---|---|
| **No Change** | Already winning (top positions) — don't touch it |
| **Improve Existing** | On page 1 (pos ~3–10), commercial intent — optimize it |
| **Expand Existing** | Page 2 (pos 11–20) — add depth to reach page 1 |
| **Create New Content** | No page ranks, or the page can't serve the intent |

Low-value rows are filtered out entirely (e.g. ranking past position 50, or very
low impressions), so the list stays focused on real opportunities.

### What each opportunity carries
Priority, Keyword, **Landing Page** (clickable), Position, Impressions, **Clicks**,
**CTR**, Intent, Score (0–100), Recommendation, **Content Type** (Blog vs Landing
Page), **Confidence %**, and a plain-language reason.

### After approval
Kriti ranks the opportunities; the human approves which to act on:

```
✓ Improve  clinic management software   (Score 93)
✓ Improve  patient management system    (Score 72)
✗ Ignore   ehr software                 (Score 35)
```

Approved pages move to the next stage, where later agents analyze the content in
detail and draft the specific improvements.

---

## Kriti is bigger than GSC — GSC is just one input

Stage 1A is the beginning. Over time Kriti chains more inputs and agents:

```text
Google Search Console → find pages to improve
SEMrush               → add search volume & keyword difficulty
Audience Research     → understand real search intent (Reddit/Quora/PAA)
Content Evaluation    → identify missing sections
Content Brief         → create the SEO brief
AI Writer             → draft the improvements
Reviewer              → quality-gate before publishing
```

GSC is **one data source**. Kriti's value is the **intelligence and the workflow**
layered on top — turning data into prioritized, explained, human-approved action.

---

*Stage 1A status: deterministic engine, live GSC integration + CSV fallback,
clickable landing pages, Clicks/CTR, content-type & confidence — built and
verified. See `docs/GSC_LIVE_API.md` for the integration details.*
