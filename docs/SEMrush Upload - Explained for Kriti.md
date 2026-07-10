# Your SEMrush Upload — What Happened, and What It Does Now

*Written 10 July 2026 · In simple English*

---

## 1. What you told us

> "This is the SEMrush file. After this it should be suggesting me blog and topics
> based on different funnel. Which it does not… or either I don't know how to use
> this tool."

**You were right.** The tool did not do this before. It was not your mistake.
This document explains why it happened, and what the tool does for you now.

---

## 2. Why it did not work before (the diagnosis)

The Discover page was built for **one type of file only**: a **Google Search
Console (GSC) export**. That file is about **your website** — which pages you
have, how many clicks and impressions they get.

The file you uploaded was a **SEMrush keyword file**. That file is about the
**market** — what people search for, how often, and how hard it is to rank.

They look similar (both are spreadsheets full of keywords), but inside they are
different:

| | GSC export | SEMrush keyword file |
|---|---|---|
| What it describes | Your website | The search market |
| Columns inside | query, page, clicks, impressions, position | Keyword, Intent, Volume, Difficulty, CPC |
| Right question to ask it | "Which of my pages should I improve?" | "What content should I create?" |

The old tool only knew the first question. When it received your SEMrush file,
it could not find any pages — so it just showed your keywords back to you with
a warning, and stopped. No topics, no funnel, no suggestions.

**In one line:** the tool received market data but only knew how to analyse
website data. That gap is what we fixed.

---

## 3. What the tool does now

Now, when you upload a SEMrush keyword file, the tool understands it
automatically. You do not need to change anything about your export. It then
works in two steps:

### Step 1 — Organise (fast, always the same result)

The system reads every keyword and:

- removes duplicates and groups similar keywords into **topics**
  (for example: *"self storage business for sale"*, *"self storage businesses
  for sale"* and *"buy self storage business"* become one topic)
- adds up the **search volume** and averages the **difficulty** for each topic
- places every topic into a **funnel stage** (explained below)
- gives every topic a **score**, so the best opportunities appear first

### Step 2 — AI SEO strategist (the reasoning)

Then an AI looks at the top topics in each funnel stage and acts like an SEO
strategist. For each topic it decides:

- **Blog or Landing Page?**
- a ready-to-use **title**
- **who** is searching (the persona)
- a suggested **call-to-action** or content hook
- **why** it recommends this
- a **priority** (High / Medium / Low)

---

## 4. What "funnel" means here

The funnel is the journey a person takes before they buy:

| Stage | Meaning | Person is thinking… | Best content |
|---|---|---|---|
| **TOFU** — Top | Awareness | "I want to learn about this" | Blog article |
| **MOFU** — Middle | Consideration | "I am comparing my options" | Comparison / review content |
| **BOFU** — Bottom | Decision | "I am ready to buy / act" | Landing page |

SEMrush marks some keywords as Informational, Commercial or Transactional — we
use that. But in your file, SEMrush left this blank for most keywords. For
those, the system reads the words themselves: *"how to start…"* means TOFU,
*"best software…"* means MOFU, *"…for sale"* or *"near me"* means BOFU.

---

## 5. Real results from YOUR file

Your file had **1,708 keywords**. The tool grouped them into **1,331 topics**:

- **926 TOFU** topics (awareness)
- **229 MOFU** topics (consideration)
- **176 BOFU** topics (decision)

Examples of what it now suggests:

| Funnel | Suggested content | Type | For whom | Why |
|---|---|---|---|---|
| TOFU | *"How to Write a Self Storage Business Plan: Step-by-Step Guide for 2026"* | Blog | New business planners | People at this stage are learning, not buying yet |
| MOFU | *"Is Self Storage a Good Business? 2026 Profitability Analysis"* | Blog | Aspiring entrepreneurs | They are weighing the decision — help them compare |
| BOFU | *"Self Storage Businesses For Sale Near You in 2026"* | Landing Page | Investors ready to acquire | 4,070 searches/month from people ready to act |

Every card also shows the search volume, the number of keywords in the topic,
the difficulty, and a confidence percentage.

---

## 6. How to use it

1. Open the Discover page.
2. Upload your SEMrush file (XLSX or CSV) — the same file you already have.
3. Wait a moment (about 30–60 seconds while the AI thinks).
4. You will see three sections — **TOFU, MOFU, BOFU** — each with topic cards,
   best opportunities first.
5. Cards marked **✦ AI strategist** were written by the AI. The rest use the
   fast rule engine.

The GSC upload still works exactly as before. The tool now simply recognises
which type of file you gave it.

---

## 7. One honest limitation (and the next step)

Your SEMrush file describes the **market**, not **your website**. So the tool
cannot yet know if you **already have** a page for a topic. Right now every
suggestion says **"Create New"**.

**Next step:** if you give us a simple list of your website's page URLs (no
API, no access needed — just the list), the tool will also tell you:

- **No Change** — you already cover this topic well
- **Improve Existing Page** — you have a page, it can do better
- **Create New** — you have nothing for this topic yet

That completes the picture: *what to create, what to improve, and what to
leave alone.*

---

## Summary

- **Your feedback was correct** — the tool did not suggest blogs and topics by funnel.
- **Cause found:** it only understood Google Search Console files, not SEMrush keyword files.
- **Fixed and delivered:** upload your SEMrush file and you now get blog and
  landing-page topic suggestions, organised by funnel stage, with titles,
  personas, reasons and priorities.
- **Optional next step:** share your page URL list to unlock "improve existing
  vs create new" recommendations.
