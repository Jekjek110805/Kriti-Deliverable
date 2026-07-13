# AI Content Strategy Engine v1

> "The next step is automating the blogs." — Kriti

Stage 1A could read a SEMrush export and display the keywords. This engine is
the next layer: after the upload, the AI analyzes the keywords like an
experienced SEO strategist and returns a complete content strategy — not just
blog titles.

It deliberately goes one step beyond "automating the blogs": not every keyword
deserves a new blog post. For every keyword cluster the engine decides between
**five** outcomes:

| Recommendation | When |
|---|---|
| **New Blog** | Informational / comparison demand, no existing page covers it |
| **New Landing Page** | Transactional / buyer demand, no existing page covers it |
| **Existing Blog** | A known page partially covers the topic — improve it |
| **Existing Landing Page** | A known page partially covers the buyer topic — improve it |
| **No Action Required** | Cluster is too weak, off-topic, or already fully served |

This makes it an SEO **decision engine**, not a blog-title generator.

---

## Workflow

```
Upload SEMrush XLSX/CSV
        ↓
Read + normalize keywords          (Python, deterministic)
        ↓
Cluster similar keywords           (Python, deterministic)
        ↓
Tentative intent + funnel + score  (Python, deterministic)
        ↓
Strategist reasoning               (LLM — the only AI step)
  • search intent behind the cluster
  • funnel: TOFU / MOFU / BOFU
  • commercial potential: High / Medium / Low
  • content decision (the 5-way call above)
  • compelling title, target audience, CTA/hook
  • one-line business reason
  • priority + confidence (0–100)
        ↓
Funnel-grouped SEO plan (JSON → frontend cards)
```

## Division of labour (deliberate)

**Python only** (never the LLM): Excel/CSV parsing, column normalization,
deduplication, keyword clustering, Volume/KD/CPC math, validation, file upload.
Same file in → same clusters out, every run. Code: [`agents/funnel_topics.py`](../agents/funnel_topics.py).

**LLM only** (never Python heuristics pretending to think): everything that is
judgement — intent, funnel confirmation, commercial value, the content
decision, titles, audience, reasoning, confidence. Code:
[`agents/ai_topic_strategist.py`](../agents/ai_topic_strategist.py).

### Which model?

The engine uses the project's **existing LLM client** —
[`integrations/hermes_llm.py`](../integrations/hermes_llm.py), which calls the
configured **OpenRouter** model (`OPENROUTER_MODEL` in `.env`). There is **no
OpenAI dependency**; because OpenRouter speaks the OpenAI-compatible chat API,
swapping models is a one-line `.env` change.

Nothing is hardcoded: every AI recommendation comes from the model via a
structured prompt that demands strict JSON. Every enum in the response is
validated against a whitelist before it touches the UI — if the model returns
garbage for a field, the deterministic value survives. The model is also never
allowed to claim "Existing Blog/Landing Page" unless the pipeline actually
knows an existing page for that cluster (it can't invent site knowledge).

### Cost discipline

A SEMrush file can hold thousands of keywords. Python clusters and ranks them
first, then the LLM enriches the **top topics of each funnel stage** (default
45 total, in concurrent batches of 6) — the ones a human would actually act
on. The rest keep their deterministic recommendation and are labelled
`rule-based` so the UI can tell them apart.

### Graceful degradation

If `OPENROUTER_API_KEY` is missing, the model errors, or the JSON can't be
parsed after retries, the upload never breaks: deterministic recommendations
are returned and `ai.note` explains what happened.

---

## API

### `POST /api/semrush/recommendations`

Multipart form:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `file` | XLSX/CSV upload | required | SEMrush/Ahrefs keyword export (needs a `Keyword` column plus Intent / Volume / Keyword Difficulty / CPC) |
| `use_ai` | bool | `true` | Set `false` for deterministic-only output |
| `top_per_stage` | int | `30` | Topics returned per funnel stage in `funnels` |
| `existing_site_url` | URL | optional | Public site whose sitemap is used to distinguish new content from improvements to existing pages |

```bash
curl -X POST http://localhost:8000/api/semrush/recommendations \
  -F "file=@semrush-keywords.xlsx" \
  -F "existing_site_url=https://www.selfstorage.help"
```

Errors: `400` with a plain-English `error` when no file is sent or the file
isn't a keyword export; `500` with `error` if the engine itself fails.

The main upload flow (`POST /api/stage1a/analyze` with
`source_type=keyword_research`) runs the same engine, so the Discover page
gets the AI strategy immediately after upload — no second call needed.

### Example response (real output, abridged)

Besides `clusters`, the response carries the same funnel-grouped `funnels`
payload the frontend renders, plus `summary` and `ai` status.

```json
{
  "status": "keyword_topics",
  "strategist": "ai",
  "source": "semrush",
  "summary": { "total_keywords": 3, "total_topics": 3,
               "tofu_topics": 1, "mofu_topics": 1, "bofu_topics": 1 },
  "ai": { "available": true, "enriched": 3, "requested": 3,
          "note": "AI strategist enriched the top 3 topics." },
  "clusters": [
    {
      "primary_keyword": "self storage business for sale",
      "secondary_keywords": ["self storage business for sale near me"],
      "search_intent": "find self storage businesses for sale",
      "funnel": "BOFU",
      "commercial_potential": "High",
      "recommended_content": "New Landing Page",
      "blog_title": "Self Storage Businesses for Sale in 2026: Verified Listings & Financing",
      "target_audience": "buyers seeking acquisition",
      "target_page": "",
      "reason": "Targets transactional buyers ready to act, enabling lead capture and direct sales conversion with optimized CTAs.",
      "priority": "High",
      "confidence": 95,
      "monthly_volume": 480,
      "avg_keyword_difficulty": 28.0,
      "strategist": "ai"
    },
    {
      "primary_keyword": "how to start a self storage business",
      "secondary_keywords": [],
      "search_intent": "learn how to start self storage business",
      "funnel": "TOFU",
      "commercial_potential": "Medium",
      "recommended_content": "New Blog",
      "blog_title": "How to Start a Self Storage Business in 2026: Step-by-Step Guide",
      "target_audience": "aspiring entrepreneurs",
      "reason": "Captures high-intent informational traffic to build authority and nurture early-stage leads into the sales funnel.",
      "priority": "High",
      "confidence": 90,
      "monthly_volume": 590,
      "avg_keyword_difficulty": 33.0,
      "strategist": "ai"
    }
  ],
  "funnels": [ "... same topics grouped TOFU → MOFU → BOFU for the UI ..." ]
}
```

---

## Frontend

The Discover page's **SEMrush / Keyword Research** upload mode renders the
strategy as cards grouped by funnel stage (TOFU → MOFU → BOFU). Each card
shows:

- AI-written **title** and the primary keyword/topic
- **Recommendation** (the 5-way decision) with **confidence** and opportunity score
- **Priority** badge, **commercial potential** badge, Blog/Landing Page badge
- **Search intent** and **target audience** lines
- The one-line business **reason**
- Expandable list of all keywords in the cluster (with volume/KD)
- `✦ AI strategist` badge on AI-decided cards vs. rule-based ones

A rotating loading state covers the analysis, and any AI degradation is
surfaced in the info banner above the cards instead of failing the upload.

## Prompt engineering (summary)

The prompt frames the model as *"an experienced SEO content strategist (not a
copywriter)"*, defines the funnel stages, states the recommendation rules
(including when "No Action Required" is the honest answer), feeds each cluster
with its metrics (volume, KD, CPC, tentative funnel, known existing page), and
demands a single strict-JSON object covering every cluster id exactly once.
`response_format: json_object` is requested from the model, responses are
retried up to 3 times per batch, and batches run concurrently so the user
waits roughly one model call, not dozens.

The writing, quality-gate and remote-publishing workflow that consumes these
recommendations is documented in
[`Blog Automation Workflow and Sales Replication.md`](Blog%20Automation%20Workflow%20and%20Sales%20Replication.md).
