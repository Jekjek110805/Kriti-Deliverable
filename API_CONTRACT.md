# Kriti Platform — Complete API Contract

**Base URL:** `http://<server-ip>:8000`
**Swagger UI:** `http://<server-ip>:8000/docs`

All responses are JSON unless otherwise noted. CORS enabled for all origins.

---

## 1. DISCOVER OPPORTUNITIES (Stage 1A)

### POST `/api/stage1a/analyze`
Upload GSC CSV → run pipeline → ranked opportunities.

**Request:** `multipart/form-data` with `file` field (CSV)

**Response:**
```json
{
  "status": "ok",
  "opportunities_found": 16,
  "excluded": 4,
  "opportunities": [...],
  "excluded_details": [...],
  "files": { "markdown_report": "...", "csv_output": "...", "yaml_approval_queue": "..." }
}
```

Each opportunity includes: keyword, page, position, impressions, clicks, intent, commercial_potential, volume, keyword_difficulty, scores (existing_page, position, impressions, intent, commercial, kd), total_score, priority, recommendation, reason, approval_status.

### GET `/api/stage1a/report` — Markdown report
### GET `/api/stage1a/csv` — CSV output
### GET `/api/stage1a/yaml` — YAML approval queue

---

## 2. CONTENT CALENDAR (Phase 1)

### GET `/api/calendar?month=2026-06&client=clinic-crm&status=planned`
List calendar entries. Optional filters: month (YYYY-MM), client, status.

### POST `/api/calendar`
Add single entry. Body: `{keyword, client, intent, funnel_stage, action_type, source, gsc_position, impressions, volume, keyword_difficulty, status, notes, month}`

### POST `/api/calendar/bulk`
Add multiple entries at once. Body: array of calendar entry objects.

### PATCH `/api/calendar/{entry_id}`
Update an entry. Body: `{field: value}` for any updatable field.

### DELETE `/api/calendar/{entry_id}`
Remove an entry.

**Status values:** planned, approved, in_review, in_progress, published, rejected

---

## 3. APPROVAL QUEUE

### GET `/api/queue`
Get current approval queue with live statuses.

### GET `/api/queue/stats`
Get counts: `{total, needs_review, approved, rejected, blocked}`

### POST `/api/queue/{keyword}/approve`
### POST `/api/queue/{keyword}/reject`
### POST `/api/queue/{keyword}/block`
Update approval status for a keyword.

---

## 4. PHASE 0 — KEYWORD VALIDATION

### POST `/api/phase0/validate`
Validate a keyword before writing. Body: `{keyword, has_existing_page, gsc_position, impressions}`

**Response:**
```json
{
  "keyword": "best crm software",
  "detected_intent": "BOFU",
  "overall": "pass",
  "checks": [
    {"criterion": "...", "pass": true, "details": [...]},
    ...
  ],
  "next_action": "Proceed to Phase 2 (brief creation)"
}
```

**4 criteria checked:**
1. Keyword from real opportunity (GSC position 3-20, commercial term, or BOFU modifier)
2. Intent is BOFU or MOFU (not TOFU)
3. No existing page can win this instead
4. Keyword logged in content calendar

---

## 5. BLOG REVIEW CHECKLIST (Phase 2-8)

### GET `/api/review/sop`
Get full SOP checklist structure for building UI. Returns 7 phases with all items.

### POST `/api/review/submit`
Submit a blog draft for review. Body: `{keyword, title, content, url_slug, meta_description, client}`

**Response:** Automated check results + human checklist with pass/fail/pending status per item.

### GET `/api/review/{keyword}`
Get the latest review for a keyword.

### PATCH `/api/review/{keyword}/checklist`
Update human checklist items. Body: `{item_id: {status: "pass"|"fail"|"na", notes: "..."}}`

---

## Scoring Reference

| Factor | Max points |
|--------|-----------|
| Existing page opportunity | 25 |
| Position upside | 20 |
| Impressions | 15 |
| Intent | 20 |
| Commercial potential | 10 |
| SEMrush KD fit | 10 |
| **Total** | **100** |

**Priority thresholds:** Critical (80+), High (65-79), Medium (50-64), Low (<50)

**Recommendation types:**
- `Improve Existing` — page ranks position ≤10 with BOFU/MOFU intent
- `Expand Existing` — page ranks position 11-20, needs more depth
- `Create New Content` — no existing page found

**Allowed approval statuses:** needs_review, approved, rejected, blocked
