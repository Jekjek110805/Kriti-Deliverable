# MAAI — Documentation

MAAI is an AI decision layer for SEO. It turns your search data into ranked,
action-ready recommendations, then walks a topic through briefing, drafting,
quality validation, and publishing — with a human approving every stage.

---

## GSC upload vs SEMrush upload — why they behave differently

A common question: *"Why doesn't a GSC CSV upload look the same as a SEMrush
upload?"*

They're two different kinds of data answering two different questions, so the
app deliberately handles them differently. It auto-detects which kind of file
you uploaded from its columns and picks the right flow — you don't choose
manually.

### GSC CSV — *your own site's performance*

A Google Search Console export is about **how your site is already doing**.

| | |
|---|---|
| **Typical columns** | `query`, `page`, `clicks`, `impressions`, `position` |
| **Data is about** | Your website |
| **Has real pages & traffic?** | Yes |
| **Question it answers** | "Which of my existing pages should I optimize, and is it worth it?" |
| **Output view** | **Ranked Opportunities** — each row is a page/keyword you already rank for, scored, with a recommendation (*Improve Existing*, *Expand Existing*, or *Create New*) |
| **"Pull live GSC" button** | Shown |

This is the *"improve what I already have"* view.

### SEMrush / Ahrefs CSV — *the search market*

A keyword-research export is about **the market**, not your site. It contains
no pages and no clicks — it doesn't know anything about your website.

| | |
|---|---|
| **Typical columns** | `keyword`, `intent`, `volume`, `keyword difficulty`, `CPC` |
| **Data is about** | The whole search market |
| **Has real pages & traffic?** | No |
| **Question it answers** | "What new blog/landing topics should I create, and where do they sit in the funnel?" |
| **Output view** | **Blog & Topic Ideas by Funnel** — keywords clustered into topics, grouped into TOFU / MOFU / BOFU, each with a content decision |
| **"Pull live GSC" button** | Hidden (there's no site data to pull against) |

This is the *"what should I create next"* view.

### Side-by-side

| | GSC | SEMrush / Ahrefs |
|---|---|---|
| Data is about | Your site | The whole market |
| Has pages/clicks? | Yes | No |
| Question answered | Optimize existing pages | Discover new topics |
| Output | Ranked page opportunities | Funnel-grouped topic ideas |
| Funnel (TOFU/MOFU/BOFU) pills | No | Yes |
| "Pull live GSC" button | Shown | Hidden |

### Why they can't look the same

The funnel stage (TOFU/MOFU/BOFU) only makes sense when you're planning *new*
content, which is why it appears for SEMrush uploads and not GSC ones. And the
app can't score "existing pages" from a SEMrush file because that file has no
pages in it — only market keywords. Different input columns → different
question → different output. Uploading the wrong file type simply gives you the
wrong view, not an error.

**Rule of thumb:** upload **GSC** when you want to know *what to fix on your own
site*; upload **SEMrush/Ahrefs** when you want to know *what new content to
create*.

---

## Documentation index

- [AI Content Strategy Engine v1](AI%20Content%20Strategy%20Engine%20v1.md) — how the SEMrush keyword → funnel-topic engine works
- [SEMrush Upload - Explained](SEMrush%20Upload%20-%20Explained%20for%20Kriti.md) — deeper walkthrough of the SEMrush flow
- [Blog Automation Workflow and Sales Replication](Blog%20Automation%20Workflow%20and%20Sales%20Replication.md) — the brief → draft → validate → publish pipeline
- [Feature Checklist and Status](Feature%20Checklist%20and%20Status.md) — what's built and what's planned
- [GSC Live API](GSC_LIVE_API.md) — connecting live Google Search Console data
- [MAAI - Stage 1A Roadmap](MAAI%20-%20Stage%201A%20Roadmap.md) — delivery roadmap
