# Kriti Project — Quick Start Guide

## What Are We Building?

**One-liner:** A tool that reads Google Search Controller data and tells Kriti which existing pages should be improved before creating new content.

**Not building:** A blog website, CMS, or AI writer.

## The Only Business Rule That Matters

> Optimize existing pages before creating new content.

If a page already ranks at position 8 for "CRM for clinics", don't write a new blog — improve that page.

## Stage 1A — The Only Thing We're Building Right Now

### Input
A CSV export from Google Search Console with columns:
- query, page, clicks, impressions, ctr, position

### What The System Does

**1. Detect opportunities**
- Position 3-20 (not too high, not too low)
- Impressions > 50 (people actually search for it)
- Has both keyword and page

**2. Classify intent**
- **BOFU** = buying/comparing ("best", "top", "review")
- **MOFU** = researching ("how to choose", "features")
- **TOFU** = learning ("what is", "definition")

**3. Score each opportunity (0-100)**
- Existing page: up to 25 points
- Position upside: up to 20 points
- Impressions: up to 15 points
- Intent: up to 20 points
- Commercial potential: up to 10 points
- Keyword difficulty fit: up to 10 points

**4. Recommend action**
- **Improve Existing** — page ranks ≤10 with BOFU/MOFU
- **Expand Existing** — page ranks 11-20, needs more depth
- **Create New Content** — no existing page found

### Output

**3 files generated:**

1. **Markdown Report** — `stage_1a_existing_page_opportunities.md`
   - Executive summary
   - Ranked opportunities table
   - Top 10 detail notes with reasoning
   - Approval queue

2. **CSV Export** — `stage_1a_existing_page_opportunities.csv`
   - Sortable/filterable table of all opportunities

3. **YAML Approval Queue** — `stage_1a_approval_queue.yaml`
   - One entry per opportunity
   - Status: needs_review / approved / rejected / blocked

## Example Run

**Before (manual):**
Someone manually looks at GSC data for hours, tries to figure out which pages to improve.

**After (automated):**
```
Upload GSC CSV
    ↓
System processes 20 rows
    ↓
Found 16 opportunities
    ↓
"Improve /clinic-crm-guide for 'crm for clinics' (score: 93)"
    ↓
Kriti reviews → approves
```

## What Each Person Does

### Reil (Backend / SEO Logic)
- Read and parse GSC CSV
- Apply position 3-20 + impressions filter
- Classify intent (BOFU/MOFU/TOFU)
- Score opportunities (0-100)
- Generate CSV and YAML output

### Angel (Workflow / Reports)
- Hermes skill definition
- Orchestrate the workflow
- Generate markdown report
- Documentation

## The Full Roadmap (Future Stages)

```
Stage 1A: Find opportunities (NOW)
    ↓
Stage 2: Create content briefs
    ↓
Stage 3: Write drafts
    ↓
Stage 4: Validate quality
    ↓
Stage 5: Prepare publishing
    ↓
Stage 6: Monitor performance
```

## Cost Discipline

**Important:** Don't use expensive LLMs for everything.

| Task | Model Tier |
|------|-----------|
| Brainstorming, architecture, advice | Free/cheap |
| Testing workflows, drafts | Standard |
| Final reports, client data, publishing | Premium |

**Before running expensive operations, ask:**
1. Am I just asking for general advice? → Use free
2. Am I testing the workflow? → Use standard on one sample first
3. Is this final output for the client? → Use premium

## Current Status

**Platform running at:** `http://<server-ip>:8000`

**API endpoints:**
- `POST /api/stage1a/analyze` — upload GSC CSV, get opportunities
- `GET /api/stage1a/report` — view markdown report
- `GET /api/stage1a/csv` — download CSV
- `GET /api/stage1a/yaml` — download approval queue
- `POST /api/queue/{keyword}/approve` — approve an opportunity
- `GET /api/queue/stats` — queue statistics

**Stage 1A deliverables:** ✅ Complete
- Markdown report: ✅
- CSV export: ✅
- YAML approval queue: ✅
- Human approval workflow: ✅
