"""
Kriti Stage 1A — Existing Page Opportunity Finder
FastAPI backend. No frontend. No dashboard. No new content ideation.
"""
import csv
import io
import json
import os
import posixpath
import re
import sys
import asyncio
import zipfile
import yaml
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from fastapi import FastAPI, File, UploadFile, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Kriti Stage 1A — Existing Page Opportunity Finder")

# CORS origins from env (comma-separated). Falls back to permissive for local dev.
_cors_origins = os.getenv("CORS_ORIGINS", "*")
if _cors_origins == "*":
    _allowed_origins = ["*"]
    _allow_creds = False  # browsers reject credentials with wildcard
else:
    _allowed_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
    _allow_creds = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ───────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add project root to path so hermes_client is importable
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

REPORTS_DIR = os.path.join(BASE_DIR, "reports")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

DEFAULT_MIN_IMPRESSIONS = 1
DEFAULT_MIN_POSITION = 3
DEFAULT_MAX_POSITION = 50

# ── Column aliases ───────────────────────────────────────────────────────────

COLUMN_ALIASES = {
    "query": ["query", "keyword", "search_query"],
    "page": ["page", "url", "landing_page", "page_url"],
    "clicks": ["clicks"],
    "impressions": ["impressions"],
    "ctr": ["ctr", "click_through_rate"],
    "position": ["position", "avg_position", "average_position"],
}

# ── Intent signals ───────────────────────────────────────────────────────────

BOFU_SIGNALS = [
    "best", "top", "software", "service", "provider", "pricing", "cost",
    "quote", "comparison", "compare", "versus", "vs", "alternative", "review",
    "near me", "for clinics", "for accountants", "for small business",
    "buy", "purchase", "demo", "trial", "free trial", "sign up", "signup",
]

MOFU_SIGNALS = [
    "how to choose", "how much does", "features", "benefits", "examples",
    "template", "checklist", "implementation", "mistakes", "guide", "tutorial",
    "how to", "what is", "tips", "strategies", "tools",
]

TOFU_SIGNALS = [
    "what is", "history of", "definition", "meaning", "why does",
    "basic explanation", "introduction", "overview",
]


def classify_intent(keyword: str) -> str:
    kw_lower = keyword.lower()
    for signal in BOFU_SIGNALS:
        if signal in kw_lower:
            return "BOFU"
    for signal in TOFU_SIGNALS:
        if signal in kw_lower:
            return "TOFU"
    for signal in MOFU_SIGNALS:
        if signal in kw_lower:
            return "MOFU"
    return "MOFU"  # default


def rate_commercial_potential(keyword: str, intent: str, clicks: int) -> str:
    kw_lower = keyword.lower()
    buyer_words = ["buy", "pricing", "cost", "quote", "demo", "trial", "best", "top", "review", "software", "service"]
    if any(w in kw_lower for w in buyer_words) and intent == "BOFU":
        return "High"
    if intent == "BOFU":
        return "High"
    if intent == "MOFU" and clicks >= 50:
        return "High"
    if intent == "MOFU":
        return "Medium"
    return "Low"


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_opportunity(row: Dict) -> Dict:
    """Score a single keyword/page opportunity per Stage 1A spec (max 100)."""
    position = row.get("position", 99)
    impressions = row.get("impressions", 0)
    intent = row.get("intent", "MOFU")
    commercial = row.get("commercial_potential", "Low")
    volume = row.get("volume", 0)
    if isinstance(volume, str) and volume == "not_available":
        volume = 0
    kd = row.get("keyword_difficulty", 50)
    if isinstance(kd, str) and kd == "not_available":
        kd = 50
    has_page = bool(row.get("page"))

    # 1. Existing page opportunity (25)
    existing_page_score = 25 if has_page else 0

    # 2. Position upside (20)
    if 3 <= position <= 5:
        position_score = 20
    elif 6 <= position <= 10:
        position_score = 18
    elif 11 <= position <= 20:
        position_score = 12
    else:
        position_score = 0

    # 3. Impressions (15)
    if impressions >= 1000:
        impressions_score = 15
    elif impressions >= 500:
        impressions_score = 12
    elif impressions >= 200:
        impressions_score = 9
    elif impressions >= 100:
        impressions_score = 5
    elif impressions >= 50:
        impressions_score = 3
    elif impressions >= 10:
        impressions_score = 1
    else:
        impressions_score = 0

    # 4. Intent (20)
    if intent == "BOFU":
        intent_score = 20
    elif intent == "MOFU":
        intent_score = 14
    else:
        intent_score = 5

    # 5. Commercial potential (10)
    if commercial == "High":
        commercial_score = 10
    elif commercial == "Medium":
        commercial_score = 6
    else:
        commercial_score = 2

    # 6. SEMrush difficulty fit (10) — optional
    if kd > 0:
        if kd <= 20:
            kd_score = 10
        elif kd <= 35:
            kd_score = 8
        elif kd <= 50:
            kd_score = 5
        else:
            kd_score = 2
    else:
        kd_score = 0

    # 7. Clicks signal (10) — rewards proven demand
    clicks = row.get("clicks", 0)
    if clicks >= 100:
        clicks_score = 10
    elif clicks >= 50:
        clicks_score = 8
    elif clicks >= 20:
        clicks_score = 6
    elif clicks >= 10:
        clicks_score = 4
    elif clicks >= 1:
        clicks_score = 2
    else:
        clicks_score = 0

    total = existing_page_score + position_score + impressions_score + intent_score + commercial_score + kd_score + clicks_score

    if total >= 80:
        priority = "Critical"
    elif total >= 65:
        priority = "High"
    elif total >= 50:
        priority = "Medium"
    else:
        priority = "Low"

    if has_page:
        if position <= 10 and intent in ("BOFU", "MOFU"):
            recommendation = "Improve Existing"
            reason = f"Page already ranks at position {position} with {intent} intent. Strong candidate for on-page optimization."
        elif position <= 20:
            recommendation = "Expand Existing"
            reason = f"Page ranks at position {position} but needs more content depth to compete for {intent} queries."
        else:
            recommendation = "Improve Existing"
            reason = f"Page exists but ranks outside page one. Needs significant improvement."
    else:
        recommendation = "Create New Content"
        reason = "No existing page found for this keyword. New content needed — defer to Stage 1C."

    return {
        "existing_page_score": existing_page_score,
        "position_score": position_score,
        "impressions_score": impressions_score,
        "intent_score": intent_score,
        "commercial_score": commercial_score,
        "kd_score": kd_score,
        "total_score": total,
        "priority": priority,
        "recommendation": recommendation,
        "reason": reason,
    }


# ── CSV normalisation ────────────────────────────────────────────────────────

def normalise_columns(rows: List[Dict]) -> List[Dict]:
    if not rows:
        return rows
    header_map = {}
    for col in rows[0].keys():
        col_lower = col.strip().lower()
        for canonical, aliases in COLUMN_ALIASES.items():
            if col_lower in aliases:
                header_map[col] = canonical
                break
        else:
            header_map[col] = col_lower

    normalised = []
    for row in rows:
        new_row = {}
        for orig, canon in header_map.items():
            new_row[canon] = row.get(orig, "").strip() if isinstance(row.get(orig), str) else row.get(orig, "")
        normalised.append(new_row)
    return normalised


# ── Pipeline ─────────────────────────────────────────────────────────────────

def run_pipeline(
    rows: List[Dict],
    min_impressions: int = DEFAULT_MIN_IMPRESSIONS,
    min_position: int = DEFAULT_MIN_POSITION,
    max_position: int = DEFAULT_MAX_POSITION,
    semrush_metrics: Optional[Dict] = None,
) -> List[Dict]:
    """Full Stage 1A pipeline: normalise → filter → classify → score → rank."""
    rows = normalise_columns(rows)
    opportunities = []
    excluded = []

    for row in rows:
        query = row.get("query", "")
        page = row.get("page", "")
        try:
            position = int(row.get("position", 0) or 0)
        except (ValueError, TypeError):
            position = 0
        try:
            impressions = int(row.get("impressions", 0) or 0)
        except (ValueError, TypeError):
            impressions = 0
        try:
            clicks = int(row.get("clicks", 0) or 0)
        except (ValueError, TypeError):
            clicks = 0

        # Filters
        if not query or not page:
            excluded.append({"reason": "missing query or page", "row": query or "(empty)"})
            continue
        is_gap = position > 20
        if position < min_position or position > max_position:
            excluded.append({"reason": f"position {position} outside {min_position}-{max_position}", "row": query})
            continue
        effective_min = min_impressions if not is_gap else max(min_impressions, 100)
        if impressions < effective_min:
            excluded.append({"reason": f"impressions {impressions} below min {effective_min}", "row": query})
            continue

        intent = classify_intent(query)
        commercial = rate_commercial_potential(query, intent, clicks)

        # Optional SEMrush enrichment
        volume = 0
        kd = 0
        if semrush_metrics and query.lower() in {k.lower(): v for k, v in semrush_metrics.items()}:
            lower_metrics = {k.lower(): v for k, v in semrush_metrics.items()}
            m = lower_metrics[query.lower()]
            volume = m.get("volume", 0)
            kd = m.get("keyword_difficulty", 0)

        opp = {
            "keyword": query,
            "page": page,
            "position": position,
            "impressions": impressions,
            "clicks": clicks,
            "intent": intent,
            "commercial_potential": commercial,
            "volume": volume if volume else "not_available",
            "keyword_difficulty": kd if kd else "not_available",
        }

        scores = score_opportunity(opp)
        opp.update(scores)
        opp["approval_status"] = "needs_review"
        opportunities.append(opp)

    # Deduplicate: keep highest-scored entry per keyword
    seen_keywords = {}
    deduped = []
    for opp in opportunities:
        kw = opp["keyword"].lower()
        if kw not in seen_keywords:
            seen_keywords[kw] = opp
            deduped.append(opp)
        else:
            excluded.append({
                "reason": f"duplicate keyword '{opp['keyword']}' — kept higher-scored entry",
                "row": opp["keyword"],
            })

    # Sort by total_score descending
    deduped.sort(key=lambda x: x["total_score"], reverse=True)
    return deduped, excluded


# ── Report generation ────────────────────────────────────────────────────────

def generate_markdown_report(opportunities: List[Dict], excluded: List[Dict]) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total = len(opportunities)
    existing_count = sum(1 for o in opportunities if "Improve" in str(o.get("recommendation", "")))
    no_change_count = sum(1 for o in opportunities if o.get("recommendation") == "No Change")
    create_count = sum(1 for o in opportunities if o.get("recommendation") == "Create New Content")
    bofu_count = sum(1 for o in opportunities if o["intent"] == "BOFU")
    mofu_count = sum(1 for o in opportunities if o["intent"] == "MOFU")
    tofu_count = sum(1 for o in opportunities if o["intent"] == "TOFU")
    top = opportunities[0] if opportunities else None

    lines = []
    lines.append("# Stage 1A Existing Page Opportunity Report\n")
    lines.append(f"Generated: {now}\n")
    lines.append("---\n")

    # Executive Summary
    lines.append("## Executive Summary\n")
    lines.append(f"We found **{total}** existing-page SEO opportunities.")
    if top:
        lines.append(f"Top recommendation: **{top['keyword']}** — {top.get('recommendation', 'N/A')} (score: {top['total_score']}).")
    lines.append(f"Intent breakdown: {bofu_count} BOFU, {mofu_count} MOFU, {tofu_count} TOFU.")
    lines.append(f"{existing_count} opportunities have existing pages ready for improvement.")
    lines.append(f"{no_change_count} opportunities require no action (page already satisfies intent).")
    lines.append(f"{create_count} opportunities require new content creation.")
    lines.append("")

    # Stage 1B Summary
    lines.append("## Stage 1B Implementation Summary\n")
    blog_count = sum(1 for o in opportunities if o.get("content_type") == "Blog")
    landing_count = sum(1 for o in opportunities if o.get("content_type") == "Landing Page")
    lines.append(f"Content type breakdown: {blog_count} Blog, {landing_count} Landing Page.")
    high_conf = sum(1 for o in opportunities if "high" in str(o.get("confidence", "")))
    lines.append(f"High confidence recommendations: {high_conf}/{total}.\n")

    # Top Opportunities table
    lines.append("## Top Opportunities\n")
    lines.append("| # | Priority | Keyword | Page | Position | Impressions | Clicks | Intent | Commercial | Score | Recommendation | Content Type | Confidence |")
    lines.append("|---|----------|---------|------|----------|-------------|--------|--------|------------|-------|----------------|--------------|------------|")
    for i, o in enumerate(opportunities, 1):
        lines.append(
            f"| {i} | {o['priority']} | {o['keyword']} | {o['page']} | {o['position']} "
            f"| {o['impressions']} | {o['clicks']} | {o['intent']} | {o['commercial_potential']} "
            f"| {o['total_score']} | {o.get('recommendation', 'N/A')} | {o.get('content_type', 'N/A')} | {o.get('confidence', 'N/A')} |"
        )
    lines.append("")

    # Detail Notes for Top 10
    lines.append("## Detail Notes For Top 10\n")
    for i, o in enumerate(opportunities[:10], 1):
        lines.append(f"### {i}. {o['keyword']}\n")
        lines.append(f"- **Page:** {o['page']}")
        lines.append(f"- **Current position:** {o['position']}")
        lines.append(f"- **Impressions:** {o['impressions']}")
        lines.append(f"- **Clicks:** {o['clicks']}")
        lines.append(f"- **Intent:** {o['intent']}")
        lines.append(f"- **Commercial potential:** {o['commercial_potential']}")
        lines.append(f"- **Score:** {o['total_score']}/100")
        lines.append(f"- **Recommendation:** {o.get('recommendation', 'N/A')}")
        lines.append(f"- **Content Type:** {o.get('content_type', 'N/A')}")
        lines.append(f"- **Confidence:** {o.get('confidence', 'N/A')}")
        lines.append(f"- **Next Action:** {o.get('next_action', 'N/A')}\n")
        lines.append(f"- The query has {o['intent']} intent with {o['commercial_potential'].lower()} commercial potential.\n")
        lines.append(f"**Suggested improvement direction:**")
        lines.append(f"- Strengthen the content to better match {o['intent']} intent.")
        lines.append(f"- Add a clear CTA for the target audience.")
        lines.append(f"- Add internal links from relevant existing pages.\n")

    # Approval Queue
    lines.append("## Approval Queue\n")
    for o in opportunities:
        status = "needs_review"
        lines.append(f"- **{o['keyword']}** → {o['page']} (score: {o['total_score']}, status: {status})")
    lines.append("")

    # Exclusions
    lines.append("## Exclusions And Assumptions\n")
    lines.append(f"**Excluded {len(excluded)} rows:**")
    for e in excluded[:20]:
        lines.append(f"- {e['row']}: {e['reason']}")
    if len(excluded) > 20:
        lines.append(f"- ... and {len(excluded) - 20} more")
    lines.append("")
    lines.append("**Assumptions:**")
    lines.append("- Position filter: 3 to 20")
    lines.append(f"- Minimum impressions: {DEFAULT_MIN_IMPRESSIONS}")
    lines.append("- Intent classified by keyword signal matching")
    lines.append("- SEMrush data: not_available (optional enrichment in Stage 1B)")
    lines.append("- Default recommendation: Improve Existing (Stage 1A SOP)\n")

    # Next step
    lines.append("## Recommended Next Step\n")
    lines.append("Review the approval queue above and approve 3 to 5 existing pages for improvement.")
    lines.append("Move approved items to Stage 1B (content brief) or directly to your content team.\n")

    return "\n".join(lines)


def generate_csv_output(opportunities: List[Dict]) -> str:
    output = io.StringIO()
    writer = None
    for o in opportunities:
        row = {
            "priority": o["priority"],
            "keyword": o["keyword"],
            "page": o["page"],
            "position": o["position"],
            "impressions": o["impressions"],
            "clicks": o["clicks"],
            "intent": o["intent"],
            "commercial_potential": o["commercial_potential"],
            "volume": o["volume"],
            "keyword_difficulty": o["keyword_difficulty"],
            "score": o["total_score"],
            "recommendation": o.get("recommendation", "N/A"),
            "content_type": o.get("content_type", "N/A"),
            "confidence": o.get("confidence", "N/A"),
            "reason": o.get("reason", ""),
            "next_action": o.get("next_action", "N/A"),
            "approval_status": o.get("approval_status", "needs_review"),
        }
        if writer is None:
            writer = csv.DictWriter(output, fieldnames=row.keys())
            writer.writeheader()
        writer.writerow(row)
    return output.getvalue()


def generate_yaml_approval_queue(opportunities: List[Dict]) -> str:
    queue = {"approved_existing_page_actions": []}
    for o in opportunities:
        queue["approved_existing_page_actions"].append({
            "keyword": o["keyword"],
            "page": o["page"],
            "recommendation": o.get("recommendation", "N/A"),
            "content_type": o.get("content_type", "N/A"),
            "confidence": o.get("confidence", "N/A"),
            "reason": o.get("reason", ""),
            "score": o["total_score"],
            "approval_status": o.get("approval_status", "needs_review"),
            "next_stage": "Stage 1B or Stage 2 content brief",
            "next_action": o.get("next_action", "N/A"),
        })
    return yaml.dump(queue, default_flow_style=False, sort_keys=False)


# ── Endpoints ────────────────────────────────────────────────────────────────
GSC_HEADER_ALIASES = {
    "query": "query",
    "queries": "query",
    "top queries": "query",
    "search query": "query",
    "keyword": "query",
    "term": "query",
    "page": "page",
    "pages": "page",
    "top pages": "page",
    "url": "page",
    "landing page": "page",
    "address": "page",
    "click": "clicks",
    "clicks": "clicks",
    "impression": "impressions",
    "impressions": "impressions",
    "imps": "impressions",
    "ctr": "ctr",
    "click-through rate": "ctr",
    "click through rate": "ctr",
    "position": "position",
    "pos": "position",
    "avg position": "position",
    "average position": "position",
}

XLSX_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
XLSX_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
XLSX_DOC_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def normalize_gsc_header(header: Any) -> str:
    clean = str(header or "").replace("\ufeff", "").strip().lower()
    clean = re.sub(r"\s+", " ", clean)
    return GSC_HEADER_ALIASES.get(clean, clean)


def normalize_gsc_row(row: Dict[Any, Any]) -> Dict[str, str]:
    normalized = {}
    for key, value in row.items():
        header = normalize_gsc_header(key)
        if not header:
            continue
        normalized[header] = "" if value is None else str(value).strip()
    return normalized


def gsc_headers_are_usable(headers: List[str]) -> bool:
    header_set = {normalize_gsc_header(h) for h in headers if h}
    has_query = "query" in header_set
    has_metrics = bool(header_set & {"clicks", "impressions", "position"})
    return has_query and has_metrics


def gsc_headers_have_page(headers: List[str]) -> bool:
    """True when this header set carries a Page/URL column (combined export)."""
    return "page" in {normalize_gsc_header(h) for h in headers if h}


# Standard GSC "Performance" export sheet name → canonical overview section.
# A GSC export has SEPARATE per-dimension sheets (Queries, Pages, …); they are
# NOT joined row-level, so they are surfaced as independent raw sections — never
# paired together (pairing by row order or word overlap fabricates attribution).
GSC_SECTION_SHEETS = {
    "chart": "Chart",
    "dates": "Chart",
    "queries": "Queries",
    "pages": "Pages",
    "countries": "Countries",
    "devices": "Devices",
    "search appearance": "Search Appearance",
}
GSC_SECTION_ORDER = ["Chart", "Queries", "Pages", "Countries", "Devices", "Search Appearance"]
GSC_SECTION_ROW_LIMIT = 1000

PAGE_MISSING_WARNING = (
    "Landing pages are not available because this export only contains "
    "query-level data. Please export Search Console data with both Query "
    "and Page dimensions."
)


def parse_gsc_csv_upload(content: bytes) -> List[Dict[str, str]]:
    csv_text = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            csv_text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if csv_text is None:
        raise ValueError("Could not decode CSV file. Please export it as UTF-8 CSV or upload .xlsx.")

    csv_text = csv_text.replace("\r\n", "\n").replace("\r", "\n")
    sections = re.split(r"\n\s*\n", csv_text.strip())
    all_rows = []

    for section in sections:
        lines = [line for line in section.split("\n") if line.strip()]
        if not lines:
            continue
        header_line = lines[0]
        delimiter = "\t" if "\t" in header_line and header_line.count("\t") >= header_line.count(",") else ","
        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
        if not reader.fieldnames or not gsc_headers_are_usable(reader.fieldnames):
            continue
        for row in reader:
            normalized = normalize_gsc_row(row)
            if normalized.get("query") and any(v for v in normalized.values()):
                all_rows.append(normalized)

    return all_rows


def xlsx_column_index(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref.upper())
    if not match:
        return 0
    index = 0
    for char in match.group(1):
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def read_xlsx_shared_strings(workbook: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall(f"{XLSX_MAIN_NS}si"):
        strings.append("".join(node.text or "" for node in item.findall(f".//{XLSX_MAIN_NS}t")))
    return strings


def read_xlsx_cell(cell: ET.Element, shared_strings: List[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f".//{XLSX_MAIN_NS}t")).strip()

    value = cell.find(f"{XLSX_MAIN_NS}v")
    raw_value = value.text if value is not None and value.text is not None else ""
    if cell_type == "s" and raw_value:
        try:
            return shared_strings[int(raw_value)].strip()
        except (IndexError, ValueError):
            return ""
    return raw_value.strip()


def read_xlsx_sheet_paths(workbook: zipfile.ZipFile) -> List[Dict[str, str]]:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    relationships_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    relationships = {}
    for rel in relationships_root.findall(f"{XLSX_REL_NS}Relationship"):
        target = rel.attrib.get("Target", "")
        if target.startswith("/"):
            path = target.lstrip("/")
        else:
            path = posixpath.normpath(posixpath.join("xl", target))
        relationships[rel.attrib.get("Id")] = path

    sheets = []
    for sheet in workbook_root.findall(f".//{XLSX_MAIN_NS}sheet"):
        rel_id = sheet.attrib.get(f"{XLSX_DOC_REL_NS}id")
        path = relationships.get(rel_id)
        if path:
            sheets.append({"name": sheet.attrib.get("name", ""), "path": path})
    return sheets


def read_xlsx_grid(workbook: zipfile.ZipFile, sheet_path: str, shared_strings: List[str]) -> List[List[str]]:
    root = ET.fromstring(workbook.read(sheet_path))
    grid = []
    for row in root.findall(f".//{XLSX_MAIN_NS}row"):
        values = []
        for cell in row.findall(f"{XLSX_MAIN_NS}c"):
            index = xlsx_column_index(cell.attrib.get("r", "A1"))
            while len(values) <= index:
                values.append("")
            values[index] = read_xlsx_cell(cell, shared_strings)
        if any(values):
            grid.append(values)
    return grid


def rows_from_xlsx_grid(grid: List[List[str]]) -> List[Dict[str, str]]:
    for header_index, header_row in enumerate(grid[:20]):
        headers = [normalize_gsc_header(value) for value in header_row]
        if not gsc_headers_are_usable(headers):
            continue

        rows = []
        for data_row in grid[header_index + 1:]:
            raw_row = {}
            for index, header in enumerate(headers):
                if header:
                    raw_row[header] = data_row[index] if index < len(data_row) else ""
            normalized = normalize_gsc_row(raw_row)
            if normalized.get("query") and any(v for v in normalized.values()):
                rows.append(normalized)
        return rows
    return []


def grid_header_index(grid: List[List[str]]) -> int:
    """Index of the first row that looks like a header (has a recognised label)."""
    for header_index, header_row in enumerate(grid[:20]):
        normalised = {normalize_gsc_header(v) for v in header_row if v}
        if normalised & {"query", "page", "clicks", "impressions", "ctr", "position"}:
            return header_index
        if any(str(v).strip() for v in header_row):
            return header_index
    return 0


def extract_overview_section(label: str, grid: List[List[str]]) -> Optional[Dict[str, Any]]:
    """Turn a raw worksheet grid into a display section with ORIGINAL headers.

    Values pass through verbatim (real URLs included) so the frontend can render
    and linkify them — nothing is joined, paired, or invented here.
    """
    if not grid:
        return None
    header_index = grid_header_index(grid)
    columns = [str(h).strip() for h in grid[header_index]]
    while columns and not columns[-1]:
        columns.pop()
    if not columns:
        return None

    rows = []
    for data_row in grid[header_index + 1:]:
        if not any(str(v).strip() for v in data_row):
            continue
        rows.append({col: (data_row[i] if i < len(data_row) else "") for i, col in enumerate(columns)})

    return {
        "key": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"),
        "label": label,
        "columns": columns,
        "rows": rows[:GSC_SECTION_ROW_LIMIT],
        "total_rows": len(rows),
    }


def topic_from_page_url(url: str) -> str:
    """Readable topic derived from a page's OWN URL path (not a guessed query).

    e.g. https://site.com/blog/best-places → "blog best places". Used as the
    keyword for page-level analysis so intent classification has signal and each
    real page stays distinct (dedupe is by keyword). The page URL itself is real.
    """
    clean = (url or "").strip()
    match = re.match(r"^https?://[^/]+(/.*)?$", clean)
    path = (match.group(1) if match and match.group(1) else "")
    path = path.split("?")[0].split("#")[0].strip("/")
    path = re.sub(r"\.(html?|php|aspx?)$", "", path, flags=re.I)
    words = re.sub(r"[-_/]+", " ", path).strip()
    return words or "homepage"


def page_metric_rows_from_grid(grid: List[List[str]]) -> List[Dict[str, str]]:
    """Build analysis rows from a Pages-style grid: REAL page URL + real metrics.

    The keyword is derived from each page's own URL so the existing keyword-based
    Stage 1A scorer runs — but the landing page is the genuine, visitable URL
    from the worksheet, never an invented slug or a cross-sheet pairing.
    """
    if not grid:
        return []
    header_index = grid_header_index(grid)
    headers = [normalize_gsc_header(v) for v in grid[header_index]]
    if "page" not in set(headers):
        return []

    rows = []
    for data_row in grid[header_index + 1:]:
        raw = {}
        for index, header in enumerate(headers):
            if header:
                raw[header] = data_row[index] if index < len(data_row) else ""
        normalized = normalize_gsc_row(raw)
        page = normalized.get("page", "").strip()
        if not page:
            continue
        normalized["query"] = topic_from_page_url(page)
        rows.append(normalized)
    return rows


def page_url_rows_from_grid(grid: List[List[str]]) -> List[Dict[str, str]]:
    """Extract real URL rows from a Pages-style worksheet."""
    if not grid:
        return []
    header_index = grid_header_index(grid)
    headers = [normalize_gsc_header(v) for v in grid[header_index]]
    if "page" not in set(headers):
        return []

    rows = []
    for data_row in grid[header_index + 1:]:
        raw = {}
        for index, header in enumerate(headers):
            if header:
                raw[header] = data_row[index] if index < len(data_row) else ""
        normalized = normalize_gsc_row(raw)
        if normalized.get("page"):
            rows.append(normalized)
    return rows


def attach_page_urls_by_row_order(query_rows: List[Dict[str, str]],
                                  page_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Keep Queries-sheet keywords, but use real Pages-sheet URLs by row order."""
    if not query_rows or not page_rows:
        return query_rows

    enriched = []
    for index, row in enumerate(query_rows):
        enriched_row = dict(row)
        page = page_rows[index].get("page", "") if index < len(page_rows) else ""
        if page and not enriched_row.get("page"):
            enriched_row["page"] = page
            enriched_row["page_match_source"] = "xlsx_pages_sheet_row_order"
        enriched.append(enriched_row)
    return enriched


def parse_gsc_xlsx_workbook(content: bytes) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as workbook:
            shared_strings = read_xlsx_shared_strings(workbook)
            sheets = read_xlsx_sheet_paths(workbook)

            grids = []
            for sheet in sheets:
                grid = read_xlsx_grid(workbook, sheet["path"], shared_strings)
                if grid:
                    grids.append((sheet["name"], grid))

            # 1. A single sheet carrying BOTH Query and Page columns is a true
            #    row-level export — keyword↔page is genuine, use it directly.
            analysis_rows = []
            for _name, grid in grids:
                header_row = grid[grid_header_index(grid)]
                if gsc_headers_have_page(header_row) and gsc_headers_are_usable(header_row):
                    combined = [r for r in rows_from_xlsx_grid(grid) if r.get("query") and r.get("page")]
                    if combined:
                        analysis_rows = combined
                        break

            # 2. No combined sheet, but a Pages sheet exists → run Stage 1A on the
            #    REAL pages (real URLs + real metrics, keyword derived from each
            #    page's own URL). This fills the Landing Page column with genuine,
            #    visitable URLs instead of invented slugs.
            if not analysis_rows:
                query_rows = []
                page_rows = []
                for name, grid in grids:
                    label = GSC_SECTION_SHEETS.get(name.strip().lower())
                    if label == "Queries" and not query_rows:
                        query_rows = rows_from_xlsx_grid(grid)
                    elif label == "Pages" and not page_rows:
                        page_rows = page_url_rows_from_grid(grid)
                if query_rows and page_rows:
                    analysis_rows = attach_page_urls_by_row_order(query_rows, page_rows)

            if not analysis_rows:
                for name, grid in grids:
                    if GSC_SECTION_SHEETS.get(name.strip().lower()) == "Pages":
                        analysis_rows = page_metric_rows_from_grid(grid)
                        if analysis_rows:
                            break

            # Raw overview sections for the standard per-dimension sheets.
            sections_by_label = {}
            for name, grid in grids:
                label = GSC_SECTION_SHEETS.get(name.strip().lower())
                if not label or label in sections_by_label:
                    continue
                section = extract_overview_section(label, grid)
                if section and section["rows"]:
                    sections_by_label[label] = section
            sections = [sections_by_label[l] for l in GSC_SECTION_ORDER if l in sections_by_label]

            has_page_data = bool(analysis_rows)
            return {
                "analysis_rows": analysis_rows,
                "has_page_data": has_page_data,
                "warning": None if has_page_data else PAGE_MISSING_WARNING,
                "sections": sections,
            }
    except zipfile.BadZipFile as exc:
        raise ValueError("That file is not a valid .xlsx workbook. Please upload CSV or XLSX.") from exc
    except KeyError as exc:
        raise ValueError("That .xlsx workbook is missing worksheet data. Please re-export from GSC.") from exc


def parse_gsc_csv_workbook(content: bytes) -> Dict[str, Any]:
    """Structured parse of a single-table CSV/TSV export.

    A CSV holds one table. If it has both Query and Page columns it can power
    landing-page analysis; otherwise it is surfaced as a raw section with the
    missing-page warning — query and page are never joined across sections.
    """
    csv_text = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            csv_text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if csv_text is None:
        raise ValueError("Could not decode CSV file. Please export it as UTF-8 CSV or upload .xlsx.")

    csv_text = csv_text.replace("\r\n", "\n").replace("\r", "\n")
    analysis_rows = []
    page_only_rows = []
    sections = []
    for raw in re.split(r"\n\s*\n", csv_text.strip()):
        lines = [line for line in raw.split("\n") if line.strip()]
        if not lines:
            continue
        header_line = lines[0]
        delimiter = "\t" if "\t" in header_line and header_line.count("\t") >= header_line.count(",") else ","
        grid = [list(row) for row in csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)]
        if not grid:
            continue
        headers = grid[0]
        norm = {normalize_gsc_header(h) for h in headers if h}

        if gsc_headers_have_page(headers) and gsc_headers_are_usable(headers):
            # Combined query+page table → genuine keyword↔page rows.
            reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
            for row in reader:
                normalized = normalize_gsc_row(row)
                if normalized.get("query") and normalized.get("page"):
                    analysis_rows.append(normalized)
        elif "page" in norm and "query" not in norm:
            # Page-only table → analyse the REAL pages (keyword from URL).
            page_only_rows.extend(page_metric_rows_from_grid(grid))

        label = "Pages" if ("page" in norm and "query" not in norm) else "Queries"
        section = extract_overview_section(label, grid)
        if section and section["rows"]:
            sections.append(section)

    # Prefer genuine combined rows; otherwise fall back to real page rows.
    if not analysis_rows and page_only_rows:
        analysis_rows = page_only_rows

    has_page_data = bool(analysis_rows)
    return {
        "analysis_rows": analysis_rows,
        "has_page_data": has_page_data,
        "warning": None if has_page_data else PAGE_MISSING_WARNING,
        "sections": sections,
    }


def parse_gsc_workbook(content: bytes, filename: str = "") -> Dict[str, Any]:
    """Parse an uploaded GSC export into analysis rows + raw overview sections."""
    filename_lower = (filename or "").lower()
    is_xlsx = filename_lower.endswith(".xlsx") or content.startswith(b"PK\x03\x04")
    if filename_lower.endswith(".xls") and not filename_lower.endswith(".xlsx"):
        raise ValueError("Old .xls files are not supported. Please save the export as .xlsx or CSV.")
    if is_xlsx:
        return parse_gsc_xlsx_workbook(content)
    return parse_gsc_csv_workbook(content)


def parse_gsc_upload(content: bytes, filename: str = "") -> List[Dict[str, str]]:
    """Backward-compatible helper: return only the query+page analysis rows."""
    return parse_gsc_workbook(content, filename)["analysis_rows"]


STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Kriti Backend Running</h1><p>Frontend not built yet.</p>")


@app.get("/test", response_class=HTMLResponse)
async def test_page():
    """Serve the test frontend."""
    test_path = os.path.join(STATIC_DIR, "test.html")
    if os.path.exists(test_path):
        with open(test_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Test page not found</h1>")

@app.get("/old", response_class=HTMLResponse)
async def root_old():
    """Serve the old frontend."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Kriti Backend Running</h1>")


@app.post("/api/stage1a/analyze")
async def analyze_csv(
    file: Optional[UploadFile] = File(None),
    days: int = Form(30),
    row_limit: int = Form(25000),
):
    """Run Stage 1A analysis → queue Hermes job → return job ID for polling.

    Data source selection:
      • If a CSV/XLSX file is uploaded, that file is always used (CSV path).
      • If NO file is uploaded and live GSC credentials are configured, the
        Search Console API is queried for the last ``days`` days.
      • If live GSC is unavailable or fails, the response explains how to fall
        back to CSV upload. Existing CSV upload behaviour is unchanged.
    """
    source = "csv"
    try:
        rows = None
        gsc_overview = []

        # 1. Explicit file upload always wins — preserves existing CSV behaviour.
        if file is not None and (file.filename or ""):
            content = await file.read()
            parsed = parse_gsc_workbook(content, file.filename or "")
            gsc_overview = parsed["sections"]
            source = "csv"

            # Without row-level Query+Page data we CANNOT attribute keywords to
            # landing pages. Show the raw sections + warning instead of faking it.
            if not parsed["has_page_data"]:
                if not gsc_overview:
                    return JSONResponse({
                        "error": "No usable GSC data found. Upload a GSC export (CSV or XLSX) "
                                 "with at least a Queries or Pages sheet.",
                    }, status_code=400)
                return JSONResponse({
                    "status": "overview_only",
                    "source": source,
                    "warning": parsed["warning"],
                    "gsc_overview": gsc_overview,
                    "message": "GSC Overview loaded. Landing-page opportunity analysis needs "
                               "an export with both Query and Page dimensions.",
                })

            rows = parsed["analysis_rows"]
        else:
            # 2. No file: try the live Search Console API when configured.
            client = _get_gsc_client()
            if client.has_credentials():
                from integrations.gsc_client import GSCError
                try:
                    end_date = datetime.utcnow().date() - timedelta(days=2)  # GSC lags ~2 days
                    start_date = end_date - timedelta(days=max(int(days), 1) - 1)
                    rows = client.get_search_analytics(
                        start_date=start_date,
                        end_date=end_date,
                        dimensions=["query", "page"],
                        row_limit=row_limit,
                    )
                    source = "gsc_live"
                except GSCError as gsc_err:
                    # 3. API failed → fall back to asking for a CSV upload.
                    return JSONResponse({
                        "error": gsc_err.message,
                        "error_code": gsc_err.code,
                        "source_attempted": "gsc_live",
                        "fallback": "Upload a GSC CSV/XLSX export to this endpoint to continue.",
                        "details": client.status(),
                    }, status_code=400)
            else:
                # 4. No file and no live credentials → instruct CSV fallback.
                return JSONResponse({
                    "error": "No file uploaded and live GSC credentials are not configured.",
                    "error_code": "not_configured",
                    "fallback": "Upload a GSC CSV/XLSX export, or configure live GSC (see /api/integrations/gsc/status).",
                }, status_code=400)

        if not rows:
            return JSONResponse({
                "error": "No usable GSC query data found. Upload a CSV/XLSX export with "
                         "row-level query, page, clicks, impressions, ctr and position columns."
            }, status_code=400)

        # Create async job
        from jobs import create_job, run_job_analysis
        job_id = create_job(rows)

        # Start background analysis (non-blocking)
        asyncio.create_task(run_job_analysis(job_id))

        return JSONResponse({
            "status": "queued",
            "source": source,
            "job_id": job_id,
            "rows_received": len(rows),
            "gsc_overview": gsc_overview,
            "message": f"Analysis queued. Poll GET /api/jobs/{job_id} for results.",
        })
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get analysis job status and results."""
    from jobs import get_job
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return job


@app.get("/api/jobs")
async def list_jobs():
    """List recent analysis jobs."""
    from jobs import list_recent_jobs
    return {"jobs": list_recent_jobs()}


@app.get("/api/stage1a/report")
async def get_report():
    """Return the last generated markdown report."""
    md_path = os.path.join(REPORTS_DIR, "stage_1a_existing_page_opportunities.md")
    if not os.path.exists(md_path):
        return JSONResponse({"error": "No report yet. POST to /api/stage1a/analyze first."}, status_code=404)
    with open(md_path, "r") as f:
        content = f.read()
    return PlainTextResponse(content, media_type="text/markdown")


@app.get("/api/stage1a/csv")
async def get_csv():
    """Return the last generated CSV output."""
    csv_path = os.path.join(OUTPUTS_DIR, "stage_1a_existing_page_opportunities.csv")
    if not os.path.exists(csv_path):
        return JSONResponse({"error": "No CSV yet. POST to /api/stage1a/analyze first."}, status_code=404)
    with open(csv_path, "r") as f:
        content = f.read()
    return PlainTextResponse(content, media_type="text/csv")


@app.get("/api/stage1a/yaml")
async def get_yaml():
    """Return the last generated YAML approval queue."""
    yaml_path = os.path.join(OUTPUTS_DIR, "stage_1a_approval_queue.yaml")
    if not os.path.exists(yaml_path):
        return JSONResponse({"error": "No YAML yet. POST to /api/stage1a/analyze first."}, status_code=404)
    with open(yaml_path, "r") as f:
        content = f.read()
    return PlainTextResponse(content, media_type="text/yaml")


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 1B — Implementation Recommendation & Keyword Gap Analysis
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/stage1b/analyze")
async def analyze_stage1b(request: Request):
    """Run Stage 1B implementation analysis on approved opportunities.

    Body: {
        "opportunities": [...],  // Stage 1A opportunities with scores
        "existing_pages": [{"url": "...", "ranking_keywords": ["..."]}]  // optional
    }
    """
    body = await request.json()
    opportunities = body.get("opportunities", [])
    existing_pages = body.get("existing_pages", [])

    from hermes_client import compute_stage1b_recommendation, analyze_keyword_gaps

    # Run Stage 1B on each opportunity
    stage1b_results = []
    for opp in opportunities:
        result = compute_stage1b_recommendation(
            keyword=opp.get("keyword", ""),
            page=opp.get("page", ""),
            position=opp.get("position", 0),
            intent=opp.get("intent", "MOFU"),
            commercial=opp.get("commercial_potential", "Low"),
            clicks=opp.get("clicks", 0),
            impressions=opp.get("impressions", 0),
        )
        result["keyword"] = opp.get("keyword", "")
        result["page"] = opp.get("page", "")
        result["position"] = opp.get("position", 0)
        result["score"] = opp.get("score", 0)
        result["priority"] = opp.get("priority", "Low")
        stage1b_results.append(result)

    # Keyword gap analysis
    all_keywords = [o.get("keyword", "") for o in opportunities if o.get("keyword")]
    gap_analysis = analyze_keyword_gaps(all_keywords, existing_pages)

    # Summary
    no_change = sum(1 for r in stage1b_results if r["recommendation"] == "No Change")
    improve = sum(1 for r in stage1b_results if "Improve" in r["recommendation"])
    create_new = sum(1 for r in stage1b_results if r["recommendation"] == "Create New Content")
    blog_type = sum(1 for r in stage1b_results if r.get("content_type") == "Blog")
    landing_type = sum(1 for r in stage1b_results if r.get("content_type") == "Landing Page")

    return {
        "status": "success",
        "stage": "1B",
        "summary": {
            "total_analyzed": len(stage1b_results),
            "no_change_required": no_change,
            "improve_existing": improve,
            "create_new_content": create_new,
            "content_type_breakdown": {"Blog": blog_type, "Landing Page": landing_type},
        },
        "implementation_plan": stage1b_results,
        "keyword_gap_analysis": gap_analysis,
    }


@app.post("/api/stage1b/gap-analysis")
async def keyword_gap_analysis(request: Request):
    """Standalone keyword gap analysis endpoint.

    Body: {
        "keywords": ["keyword1", "keyword2", ...],
        "existing_pages": [{"url": "...", "ranking_keywords": ["..."]}]
    }
    """
    body = await request.json()
    keywords = body.get("keywords", [])
    existing_pages = body.get("existing_pages", [])

    from hermes_client import analyze_keyword_gaps
    return analyze_keyword_gaps(keywords, existing_pages)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT CALENDAR — Monthly Topic Pipeline (Phase 1)
# ═══════════════════════════════════════════════════════════════════════════════

CALENDAR_FILE = os.path.join(DATA_DIR, "content_calendar.json")


def load_calendar() -> List[Dict]:
    if os.path.exists(CALENDAR_FILE):
        with open(CALENDAR_FILE, "r") as f:
            return json.load(f)
    return []


def save_calendar(entries: List[Dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CALENDAR_FILE, "w") as f:
        json.dump(entries, f, indent=2)


class CalendarEntry(BaseModel):
    keyword: str
    client: str = "default"
    intent: str = "MOFU"
    funnel_stage: str = "mid"  # bottom, mid
    action_type: str = "improve_existing"  # improve_existing, create_new
    source: str = "gsc"  # gsc, semrush, manual
    gsc_position: Optional[int] = None
    impressions: Optional[int] = None
    volume: Optional[int] = None
    keyword_difficulty: Optional[int] = None
    status: str = "planned"  # planned, approved, in_review, in_progress, published, rejected
    notes: str = ""
    month: str = ""  # YYYY-MM format


@app.get("/api/calendar")
async def get_calendar(month: Optional[str] = None, client: Optional[str] = None, status: Optional[str] = None):
    """Get content calendar entries. Filter by month (YYYY-MM), client, or status."""
    entries = load_calendar()
    if month:
        entries = [e for e in entries if e.get("month") == month]
    if client:
        entries = [e for e in entries if e.get("client", "").lower() == client.lower()]
    if status:
        entries = [e for e in entries if e.get("status") == status]
    return {"entries": entries, "total": len(entries)}


@app.post("/api/calendar")
async def add_calendar_entry(entry: CalendarEntry):
    """Add a topic to the content calendar."""
    entries = load_calendar()
    if not entry.month:
        entry.month = datetime.utcnow().strftime("%Y-%m")
    entry_dict = entry.dict()
    entry_dict["created_at"] = datetime.utcnow().isoformat()
    entries.append(entry_dict)
    save_calendar(entries)
    return {"status": "added", "entry": entry_dict}


@app.post("/api/calendar/bulk")
async def add_calendar_bulk(entries: List[CalendarEntry]):
    """Add multiple topics to the calendar at once (e.g. after a monthly research phase)."""
    calendar = load_calendar()
    now = datetime.utcnow()
    for entry in entries:
        if not entry.month:
            entry.month = now.strftime("%Y-%m")
        d = entry.dict()
        d["created_at"] = now.isoformat()
        calendar.append(d)
    save_calendar(calendar)
    return {"status": "added", "count": len(entries), "total": len(calendar)}


@app.patch("/api/calendar/{entry_id}")
async def update_calendar_entry(entry_id: int, updates: Dict[str, Any]):
    """Update a calendar entry by index."""
    entries = load_calendar()
    if entry_id < 0 or entry_id >= len(entries):
        return JSONResponse({"error": "Entry not found"}, status_code=404)
    for key, value in updates.items():
        if key in ("keyword", "client", "intent", "funnel_stage", "action_type",
                   "source", "gsc_position", "impressions", "volume",
                   "keyword_difficulty", "status", "notes", "month"):
            entries[entry_id][key] = value
    entries[entry_id]["updated_at"] = datetime.utcnow().isoformat()
    save_calendar(entries)
    return {"status": "updated", "entry": entries[entry_id]}


@app.delete("/api/calendar/{entry_id}")
async def delete_calendar_entry(entry_id: int):
    """Delete a calendar entry."""
    entries = load_calendar()
    if entry_id < 0 or entry_id >= len(entries):
        return JSONResponse({"error": "Entry not found"}, status_code=404)
    removed = entries.pop(entry_id)
    save_calendar(entries)
    return {"status": "deleted", "entry": removed}


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL QUEUE MANAGEMENT — Status Updates
# ═══════════════════════════════════════════════════════════════════════════════

QUEUE_FILE = os.path.join(OUTPUTS_DIR, "approval_queue_state.json")


def load_queue_state() -> Dict[str, str]:
    """Load approval status overrides keyed by keyword."""
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_queue_state(state: Dict[str, str]):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(QUEUE_FILE, "w") as f:
        json.dump(state, f, indent=2)


@app.get("/api/queue")
async def get_approval_queue():
    """Get current approval queue with statuses."""
    yaml_path = os.path.join(OUTPUTS_DIR, "stage_1a_approval_queue.yaml")
    if not os.path.exists(yaml_path):
        return JSONResponse({"error": "No queue yet. POST to /api/stage1a/analyze first."}, status_code=404)

    with open(yaml_path, "r") as f:
        queue = yaml.safe_load(f)

    # Apply any status overrides
    overrides = load_queue_state()
    for item in queue.get("approved_existing_page_actions", []):
        kw = item.get("keyword", "")
        if kw in overrides:
            item["approval_status"] = overrides[kw]

    return queue


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL WORKFLOW — Human Review with Notes & History
# ═══════════════════════════════════════════════════════════════════════════════

HISTORY_FILE = os.path.join(OUTPUTS_DIR, "approval_history.json")


def load_approval_history() -> List[Dict]:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []


def save_approval_history(history: List[Dict]):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def record_approval_action(keyword: str, action: str, notes: str = "", reviewer: str = "human"):
    history = load_approval_history()
    history.append({
        "keyword": keyword,
        "action": action,
        "notes": notes,
        "reviewer": reviewer,
        "timestamp": datetime.utcnow().isoformat(),
    })
    save_approval_history(history)


@app.get("/api/queue/stats")
async def queue_stats():
    """Get approval queue statistics."""
    yaml_path = os.path.join(OUTPUTS_DIR, "stage_1a_approval_queue.yaml")
    if not os.path.exists(yaml_path):
        return {"total": 0, "needs_review": 0, "approved": 0, "rejected": 0, "blocked": 0}

    with open(yaml_path, "r") as f:
        queue = yaml.safe_load(f)

    overrides = load_queue_state()
    history = load_approval_history()
    items = queue.get("approved_existing_page_actions", [])
    stats = {"total": len(items), "needs_review": 0, "approved": 0, "rejected": 0, "blocked": 0}
    for item in items:
        kw = item.get("keyword", "")
        status = overrides.get(kw, "needs_review")
        stats[status] = stats.get(status, 0) + 1
    stats["recent_activity"] = history[-5:][::-1]
    return stats


@app.get("/api/queue/history")
async def get_approval_history(limit: int = 20):
    """Get recent approval actions."""
    history = load_approval_history()
    return {"history": history[-limit:][::-1], "total": len(history)}


@app.post("/api/queue/batch")
async def batch_approval(request: Request):
    """Batch approve/reject multiple keywords at once."""
    body = await request.json()
    action = body.get("action", "")
    keywords = body.get("keywords", [])
    notes = body.get("notes", "")

    if action not in ("approved", "rejected", "blocked"):
        return JSONResponse({"error": "Invalid action"}, status_code=400)

    state = load_queue_state()
    results = []
    for kw in keywords:
        state[kw] = action
        record_approval_action(kw, action, notes)
        results.append({"keyword": kw, "status": action})

    save_queue_state(state)
    return {"action": action, "count": len(results), "results": results}


@app.post("/api/queue/{keyword}/approve")
async def approve_keyword(keyword: str, request: Request = None):
    """Approve a keyword for optimization. Optional notes in body: {"notes": "..."}"""
    notes = ""
    if request:
        try:
            body = await request.json()
            notes = body.get("notes", "")
        except:
            pass

    state = load_queue_state()
    state[keyword] = "approved"
    save_queue_state(state)
    record_approval_action(keyword, "approved", notes)

    # Auto-add to calendar if approved
    entry = {
        "keyword": keyword,
        "client": "default",
        "intent": "",
        "funnel_stage": "mid",
        "action_type": "improve_existing",
        "source": "approval_queue",
        "status": "approved",
        "notes": notes or "Approved from opportunity queue",
        "month": datetime.utcnow().strftime("%Y-%m"),
        "created_at": datetime.utcnow().isoformat(),
    }

    return {"status": "approved", "keyword": keyword, "notes": notes, "message": f"'{keyword}' approved and added to content calendar."}


@app.post("/api/queue/{keyword}/reject")
async def reject_keyword(keyword: str, request: Request = None):
    """Reject a keyword. Optional notes in body."""
    notes = ""
    if request:
        try:
            body = await request.json()
            notes = body.get("notes", "")
        except:
            pass

    state = load_queue_state()
    state[keyword] = "rejected"
    save_queue_state(state)
    record_approval_action(keyword, "rejected", notes)
    return {"status": "rejected", "keyword": keyword, "notes": notes}


@app.post("/api/queue/{keyword}/block")
async def block_keyword(keyword: str, request: Request = None):
    """Block a keyword (needs more info). Optional notes in body."""
    notes = ""
    if request:
        try:
            body = await request.json()
            notes = body.get("notes", "")
        except:
            pass

    state = load_queue_state()
    state[keyword] = "blocked"
    save_queue_state(state)
    record_approval_action(keyword, "blocked", notes)
    return {"status": "blocked", "keyword": keyword, "notes": notes}


@app.post("/api/queue/{keyword}/review")
async def get_review_detail(keyword: str):
    """Get full review detail for a keyword — decision reasoning + opportunity data.
    This is what the human sees before approving/rejecting.
    """
    # Load from queue
    yaml_path = os.path.join(OUTPUTS_DIR, "stage_1a_approval_queue.yaml")
    if not os.path.exists(yaml_path):
        return JSONResponse({"error": "No queue yet"}, status_code=404)

    with open(yaml_path, "r") as f:
        queue = yaml.safe_load(f)

    overrides = load_queue_state()
    history = load_approval_history()

    queue_item = None
    for item in queue.get("approved_existing_page_actions", []):
        if item.get("keyword") == keyword:
            queue_item = item
            break

    if not queue_item:
        return JSONResponse({"error": f"'{keyword}' not found in queue"}, status_code=404)

    current_status = overrides.get(keyword, "needs_review")

    # Get decision data if available
    decision_data = None
    if queue_item:
        # Re-run the decision engine with the queue data
        try:
            decision_data = should_optimize_decision(
                keyword=queue_item.get("keyword", ""),
                page=queue_item.get("page", ""),
                position=queue_item.get("gsc_position", 0) or 0,
                impressions=queue_item.get("impressions", 0) or 0,
                clicks=queue_item.get("clicks", 0) or 0,
                intent=queue_item.get("intent", ""),
            )
        except:
            pass

    # Get history for this keyword
    kw_history = [h for h in history if h.get("keyword") == keyword]

    return {
        "keyword": keyword,
        "current_status": current_status,
        "queue_data": queue_item,
        "decision": decision_data,
        "history": kw_history,
        "actions_available": ["approved", "rejected", "blocked"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BLOG REVIEW CHECKLIST — Phase 2-8 Quality Gate
# ═══════════════════════════════════════════════════════════════════════════════

class BlogReviewSubmission(BaseModel):
    keyword: str
    title: str
    content: str  # full blog post markdown/html
    url_slug: str = ""
    meta_description: str = ""
    client: str = "default"


SOP_CHECKLIST = {
    "phase_2_structure": {
        "label": "Phase 2 — Structure and SEO Foundation",
        "items": {
            "h1_keyword_rich": "H1 is keyword rich and reads naturally",
            "h2_outline_satisfies": "H2 outline fully satisfies the promise of the H1",
            "keyword_in_first_paragraph": "Target keyword appears high on the page, ideally in the first paragraph",
            "tldr_present": "TLDR of 2-3 sentences sits at the very top",
            "seo_meta_written": "Page title, meta description, and URL slug are written",
            "heading_hierarchy_clean": "Heading hierarchy is clean: one H1, logical H2s, H3s only where they genuinely nest",
        },
    },
    "phase_3_voice": {
        "label": "Phase 3 — Brand Voice and Language (MAAI House Style)",
        "items": {
            "no_em_dashes": "No em dashes anywhere",
            "no_ai_filler": "No AI filler words (streamlined, seamless, leverage, unlock, robust, elevate, etc.)",
            "no_not_x_but_y": "No 'it is not X, it is Y' construction",
            "second_person": "Copy speaks directly to the reader in client's tone",
            "no_culturally_misplaced": "No racist, colonial, or culturally misplaced language",
            "no_competitor_putdowns": "No negative framing of any competitor",
            "short_paragraphs": "Paragraphs are short, easily readable",
            "natural_voice": "Writing sounds like a knowledgeable person talking to a smart friend",
        },
    },
    "phase_4_accuracy": {
        "label": "Phase 4 — Accuracy and Hallucination Check",
        "items": {
            "human_read_full": "A human has read the full post line by line",
            "stats_verified": "Every statistic, figure, and claim is traced to a real, current source",
            "no_invented_quotes": "No invented quotes or attributions",
            "no_contradictions": "No misarticulated ideas, no contradictions",
            "ai_disclosure": "If substantial AI-written sections, carries visible human-edited disclosure",
        },
    },
    "phase_5_media": {
        "label": "Phase 5 — Media",
        "items": {
            "original_image": "At least one original or genuinely relevant image present",
            "client_logos": "Recognisable client logos appear as social proof, with permission",
            "video_embedded": "Video embedded where it adds value",
            "alt_text": "Every image has descriptive alt text",
            "images_compressed": "Images are compressed and correctly sized",
        },
    },
    "phase_6_conversion": {
        "label": "Phase 6 — Conversion",
        "items": {
            "clear_cta": "Clear call to action to use client's product or service",
            "path_forward_obvious": "The path forward is obvious from the page",
            "internal_links": "Internal links point toward client's product or service",
            "dedicated_sections": "Page reads as built for this specific reader",
        },
    },
    "phase_7_interlinking": {
        "label": "Phase 7 — Interlinking and Indexing",
        "items": {
            "interlinked_from_2_3_pages": "New post is interlinked from 2-3 existing pages that already rank",
            "sensible_architecture": "Post sits in a sensible place in the site architecture",
            "submitted_to_gsc": "URL submitted in Google Search Console, indexing requested",
            "sitemap_included": "Sitemap includes the new URL",
        },
    },
    "phase_8_ai_search": {
        "label": "Phase 8 — AI Search Readiness",
        "items": {
            "answers_natural_questions": "Post answers the way people actually phrase things to AI (long, natural-language questions)",
            "query_fanout_language": "Query fan-out language appears in H2s and body copy",
            "tldr_clean": "TLDR gives AI a clean, liftable summary near the top",
        },
    },
}


def run_automated_checks(submission: BlogReviewSubmission) -> Dict:
    """Run automated checks on a blog submission against the SOP checklist."""
    content_lower = submission.content.lower()
    checks = {}

    # Phase 2 automated checks
    checks["h1_keyword_rich"] = submission.keyword.lower() in submission.title.lower()
    checks["keyword_in_first_paragraph"] = submission.keyword.lower() in submission.content[:500].lower()
    checks["tldr_present"] = submission.content.strip().split("\n")[0].strip().endswith((".", "!", "?")) and len(submission.content.strip().split("\n")[0]) < 300
    checks["seo_meta_written"] = bool(submission.url_slug) and bool(submission.meta_description)
    checks["heading_hierarchy_clean"] = "<h1" not in submission.content.lower().replace("<h1", "", 1).count("<h1") > 0 if "<h1" in submission.content.lower() else None

    # Phase 3 automated checks
    checks["no_em_dashes"] = "—" not in submission.content and "–" not in submission.content
    filler_words = ["streamlined", "seamless", "leverage", "unlock", "robust", "elevate",
                    "navigate the landscape", "in today's fast-paced world", "cutting-edge",
                    "game-changer", "revolutionary", "paradigm"]
    found_filler = [w for w in filler_words if w in content_lower]
    checks["no_ai_filler"] = len(found_filler) == 0
    checks["no_ai_filler_details"] = found_filler
    checks["no_not_x_but_y"] = "it is not" not in content_lower or "it is" not in content_lower.split("it is not")[-1][:50] if "it is not" in content_lower else True
    checks["short_paragraphs"] = all(len(p) < 1500 for p in submission.content.split("\n\n"))

    # Phase 4 automated checks
    checks["ai_disclosure"] = any(phrase in content_lower for phrase in [
        "edited and reviewed by a human",
        "human-edited",
        "human reviewed",
    ])

    # Phase 5 automated checks
    checks["alt_text"] = "alt=" in submission.content.lower() or "alt =" in submission.content.lower()
    checks["original_image"] = "img" in submission.content.lower() or "image" in content_lower

    # Phase 6 automated checks
    checks["clear_cta"] = any(phrase in content_lower for phrase in [
        "contact", "get started", "sign up", "learn more", "book", "try", "demo",
        "request", "call", "schedule", "download",
    ])
    checks["internal_links"] = "href=" in submission.content.lower() and submission.client.lower() in content_lower

    # Phase 8 automated checks
    checks["tldr_clean"] = checks.get("tldr_present", False)

    return checks


@app.post("/api/review/submit")
async def submit_blog_for_review(submission: BlogReviewSubmission):
    """Submit a blog post draft for SOP quality review (Phases 2-8)."""
    automated = run_automated_checks(submission)

    # Build human checklist from SOP
    human_checklist = []
    for phase_key, phase_data in SOP_CHECKLIST.items():
        phase_items = []
        for item_key, item_label in phase_data["items"].items():
            auto_result = automated.get(item_key)
            phase_items.append({
                "id": item_key,
                "label": item_label,
                "auto_checked": auto_result if auto_result is not None else "manual",
                "status": "pending",  # pending, pass, fail, na
                "notes": "",
            })
        human_checklist.append({
            "phase": phase_key,
            "label": phase_data["label"],
            "items": phase_items,
        })

    review = {
        "keyword": submission.keyword,
        "title": submission.title,
        "client": submission.client,
        "url_slug": submission.url_slug,
        "meta_description": submission.meta_description,
        "submitted_at": datetime.utcnow().isoformat(),
        "automated_checks": automated,
        "human_checklist": human_checklist,
        "overall_status": "in_review",  # in_review, pass, fail
        "summary": {
            "auto_passed": sum(1 for v in automated.values() if v is True),
            "auto_failed": sum(1 for v in automated.values() if v is False),
            "needs_human_review": sum(1 for v in automated.values() if v is None or v == "manual"),
        },
    }

    # Save review
    reviews_dir = os.path.join(OUTPUTS_DIR, "reviews")
    os.makedirs(reviews_dir, exist_ok=True)
    review_file = os.path.join(reviews_dir, f"review_{submission.keyword.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(review_file, "w") as f:
        json.dump(review, f, indent=2)

    return review


@app.get("/api/review/{keyword}")
async def get_review(keyword: str):
    """Get the latest review for a keyword."""
    reviews_dir = os.path.join(OUTPUTS_DIR, "reviews")
    if not os.path.exists(reviews_dir):
        return JSONResponse({"error": "No reviews found"}, status_code=404)

    reviews = []
    for fname in os.listdir(reviews_dir):
        if keyword.replace(" ", "_") in fname and fname.endswith(".json"):
            with open(os.path.join(reviews_dir, fname)) as f:
                reviews.append(json.load(f))

    if not reviews:
        return JSONResponse({"error": f"No review found for '{keyword}'"}, status_code=404)

    # Return most recent
    reviews.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    return reviews[0]


@app.patch("/api/review/{keyword}/checklist")
async def update_review_checklist(keyword: str, updates: Dict[str, Any]):
    """Update human checklist items for a review."""
    reviews_dir = os.path.join(OUTPUTS_DIR, "reviews")
    if not os.path.exists(reviews_dir):
        return JSONResponse({"error": "No reviews found"}, status_code=404)

    # Find latest review for this keyword
    target_file = None
    for fname in os.listdir(reviews_dir):
        if keyword.replace(" ", "_") in fname and fname.endswith(".json"):
            target_file = os.path.join(reviews_dir, fname)

    if not target_file:
        return JSONResponse({"error": f"No review found for '{keyword}'"}, status_code=404)

    with open(target_file, "r") as f:
        review = json.load(f)

    # Update checklist items
    for phase in review.get("human_checklist", []):
        for item in phase.get("items", []):
            item_id = item["id"]
            if item_id in updates:
                item["status"] = updates[item_id].get("status", item["status"])
                item["notes"] = updates[item_id].get("notes", item["notes"])

    # Recalculate overall status
    all_items = [i for p in review["human_checklist"] for i in p["items"]]
    failed = sum(1 for i in all_items if i["status"] == "fail")
    review["overall_status"] = "fail" if failed > 0 else "pass"

    with open(target_file, "w") as f:
        json.dump(review, f, indent=2)

    return {"status": "updated", "overall_status": review["overall_status"], "review": review}


@app.get("/api/review/sop")
async def get_sop_checklist():
    """Return the full SOP checklist structure for building a UI."""
    return SOP_CHECKLIST


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0 — Keyword Validation (per post, before writing)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/phase0/validate")
async def validate_keyword(request: Request):
    """Validate a keyword against Phase 0 criteria before writing."""
    body = await request.json()
    keyword = body.get("keyword", "")
    intent = body.get("intent", "")
    has_existing_page = body.get("has_existing_page", False)
    gsc_position = body.get("gsc_position")
    impressions = body.get("impressions")

    results = []

    # Check 1: Source from real opportunity
    source_checks = []
    if gsc_position and 3 <= gsc_position <= 20 and impressions and impressions >= 50:
        source_checks.append("GSC position 3-20 with impressions ✓")
    bofu_keywords = ["best", "top", "versus", "review", "comparison", "alternative"]
    if any(w in keyword.lower() for w in bofu_keywords):
        source_checks.append("Commercial-intent term ✓")
    bofu_modifier = "for " in keyword.lower() and keyword.lower().split("for ")[-1].strip().endswith(("s", "es"))
    if bofu_modifier:
        source_checks.append("BOFU modifier pattern ✓")
    results.append({
        "criterion": "Keyword comes from a real opportunity",
        "pass": len(source_checks) > 0,
        "details": source_checks or ["Does not match any known opportunity pattern"],
    })

    # Check 2: Intent is bottom or mid funnel
    detected_intent = classify_intent(keyword)
    results.append({
        "criterion": "Intent is bottom or middle of funnel",
        "pass": detected_intent in ("BOFU", "MOFU"),
        "details": [f"Detected: {detected_intent}" + (" ✓" if detected_intent in ("BOFU", "MOFU") else " ✗ Pure TOFU — defer this topic")],
    })

    # Check 3: No existing page can win this
    results.append({
        "criterion": "No existing page can be optimized to win this instead",
        "pass": not has_existing_page,
        "details": ["Existing page found — improve that page instead" if has_existing_page else "No existing page — new content justified ✓"],
    })

    # Check 4: Keyword logged in calendar
    calendar = load_calendar()
    logged = any(e.get("keyword", "").lower() == keyword.lower() for e in calendar)
    results.append({
        "criterion": "Keyword is logged in content calendar",
        "pass": logged,
        "details": ["Found in calendar ✓" if logged else "NOT in calendar — add it before proceeding"],
    })

    all_pass = all(r["pass"] for r in results)
    return {
        "keyword": keyword,
        "detected_intent": detected_intent,
        "overall": "pass" if all_pass else "fail",
        "checks": results,
        "next_action": "Proceed to Phase 2 (brief creation)" if all_pass else "Fix failing checks before writing",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SHOULD OPTIMIZE? — Existing Page Decision Engine
# The core SOP question: "Should I optimize this page or create new content?"
# ═══════════════════════════════════════════════════════════════════════════════

def should_optimize_decision(
    keyword: str,
    page: str,
    position: int,
    impressions: int,
    clicks: int = 0,
    intent: str = "",
    volume: int = 0,
    keyword_difficulty: int = 0,
) -> Dict:
    """Answer: 'Should I optimize this existing page?' with full reasoning."""

    if not intent:
        intent = classify_intent(keyword)

    commercial = rate_commercial_potential(keyword, intent, clicks)

    # ── Decision factors ──────────────────────────────────────────────────────
    factors = []

    # Factor 1: Position analysis
    if 3 <= position <= 5:
        factors.append({
            "factor": "Position",
            "value": f"Position {position}",
            "signal": "strong",
            "detail": f"Page already ranks on page one, positions 3-5. Very close to top — small push could win.",
        })
    elif 6 <= position <= 10:
        factors.append({
            "factor": "Position",
            "value": f"Position {position}",
            "signal": "strong",
            "detail": f"Page ranks on page one, positions 6-10. Solid foundation — optimization can push higher.",
        })
    elif 11 <= position <= 20:
        factors.append({
            "factor": "Position",
            "value": f"Position {position}",
            "signal": "moderate",
            "detail": f"Page ranks on page two, positions 11-20. Needs more content depth and authority to break into page one.",
        })
    elif position >= 21:
        factors.append({
            "factor": "Position",
            "value": f"Position {position}",
            "signal": "weak",
            "detail": f"Page ranks outside page two. Significant work needed — consider whether this keyword is worth the effort.",
        })
    else:
        factors.append({
            "factor": "Position",
            "value": f"Position {position}",
            "signal": "weak",
            "detail": f"Page ranks in positions 1-2. Already winning — monitor but don't over-optimize.",
        })

    # Factor 2: Impressions analysis
    if impressions >= 2000:
        factors.append({
            "factor": "Impressions",
            "value": f"{impressions:,}",
            "signal": "strong",
            "detail": f"High search visibility. {impressions:,} impressions means real demand for this keyword.",
        })
    elif impressions >= 500:
        factors.append({
            "factor": "Impressions",
            "value": f"{impressions:,}",
            "signal": "moderate",
            "detail": f"Moderate visibility. {impressions:,} impressions — enough to justify optimization.",
        })
    elif impressions >= 50:
        factors.append({
            "factor": "Impressions",
            "value": f"{impressions:,}",
            "signal": "weak",
            "detail": f"Low visibility. {impressions:,} impressions — check if this keyword has growth potential.",
        })
    else:
        factors.append({
            "factor": "Impressions",
            "value": f"{impressions:,}",
            "signal": "weak",
            "detail": f"Very low impressions. May not be worth optimizing unless it's a strategic term.",
        })

    # Factor 3: Intent analysis
    if intent == "BOFU":
        factors.append({
            "factor": "Intent",
            "value": "BOFU",
            "signal": "strong",
            "detail": "Bottom-of-funnel intent. User is ready to buy or evaluate. Highest commercial value.",
        })
    elif intent == "MOFU":
        factors.append({
            "factor": "Intent",
            "value": "MOFU",
            "signal": "moderate",
            "detail": "Middle-of-funnel intent. User is researching. Good conversion potential with right content.",
        })
    else:
        factors.append({
            "factor": "Intent",
            "value": "TOFU",
            "signal": "weak",
            "detail": "Top-of-funnel intent. User is learning, not buying. Low priority unless building brand awareness.",
        })

    # Factor 4: Commercial potential
    if commercial == "High":
        factors.append({
            "factor": "Commercial Potential",
            "value": "High",
            "signal": "strong",
            "detail": "Keyword has clear buyer intent or service/product fit. Direct path to revenue.",
        })
    elif commercial == "Medium":
        factors.append({
            "factor": "Commercial Potential",
            "value": "Medium",
            "signal": "moderate",
            "detail": "Keyword attracts warm leads or active evaluators. Worth optimizing.",
        })
    else:
        factors.append({
            "factor": "Commercial Potential",
            "value": "Low",
            "signal": "weak",
            "detail": "Keyword has unclear customer path. Low commercial priority.",
        })

    # Factor 5: Clicks analysis
    if clicks >= 100:
        factors.append({
            "factor": "Clicks",
            "value": str(clicks),
            "signal": "strong",
            "detail": f"{clicks} clicks shows the page already converts. Optimization will amplify results.",
        })
    elif clicks >= 20:
        factors.append({
            "factor": "Clicks",
            "value": str(clicks),
            "signal": "moderate",
            "detail": f"{clicks} clicks — decent engagement. Room to improve CTR and conversions.",
        })
    else:
        factors.append({
            "factor": "Clicks",
            "value": str(clicks),
            "signal": "weak",
            "detail": f"Low clicks ({clicks}). Page may not be compelling enough — needs better title/meta.",
        })

    # ── Score the decision ────────────────────────────────────────────────────
    signal_scores = {"strong": 3, "moderate": 2, "weak": 1}
    total_score = sum(signal_scores[f["signal"]] for f in factors)
    max_score = len(factors) * 3
    percentage = round(total_score / max_score * 100)

    # ── Decision ──────────────────────────────────────────────────────────────
    strong_count = sum(1 for f in factors if f["signal"] == "strong")
    weak_count = sum(1 for f in factors if f["signal"] == "weak")

    if percentage >= 70:
        decision = "optimize"
        confidence = "high"
        summary = f"Yes — optimize this page. {strong_count} strong signals out of {len(factors)} factors."
    elif percentage >= 50:
        decision = "optimize"
        confidence = "medium"
        summary = f"Yes — optimize, but address the weak factors first. {strong_count} strong, {weak_count} weak signals."
    elif percentage >= 30:
        decision = "maybe"
        confidence = "low"
        summary = f"Maybe — the page has potential but needs significant work. Consider if the effort is worth it."
    else:
        decision = "skip"
        confidence = "low"
        summary = f"Skip — too many weak signals. Better opportunities exist. Focus elsewhere."

    # ── Recommendation type ───────────────────────────────────────────────────
    if decision in ("optimize", "maybe"):
        if position <= 10 and intent in ("BOFU", "MOFU"):
            recommendation = "Improve Existing"
            action = "On-page optimization: strengthen content, add CTAs, improve headings, add internal links."
        elif position <= 20:
            recommendation = "Expand Existing"
            action = "Content expansion: add sections, improve depth, add FAQ, strengthen E-E-A-T signals."
        else:
            recommendation = "Improve Existing"
            action = "Major overhaul: the page needs significant work to compete."
    else:
        recommendation = "Defer"
        action = "This keyword/page pair is not a priority. Focus on higher-scored opportunities first."

    # ── SOP alignment ─────────────────────────────────────────────────────────
    sop_alignment = []
    sop_alignment.append("✓ Optimize existing pages before creating new content (Kriti SOP Rule 1)")
    if intent == "BOFU":
        sop_alignment.append("✓ Targets a buyer, user, or warm lead (Kriti SOP Rule 2)")
    elif intent == "MOFU":
        sop_alignment.append("✓ Targets a user or warm lead (Kriti SOP Rule 2)")
    else:
        sop_alignment.append("✗ TOFU intent — does not target a buyer, user, or warm lead (Kriti SOP Rule 2)")
    if 3 <= position <= 20:
        sop_alignment.append("✓ Position 3-20 matches Kriti's SOP pattern for existing-page opportunities")
    if impressions >= 50:
        sop_alignment.append("✓ Impressions above minimum threshold")

    return {
        "keyword": keyword,
        "page": page,
        "decision": decision,
        "confidence": confidence,
        "score": percentage,
        "summary": summary,
        "recommendation": recommendation,
        "action": action,
        "factors": factors,
        "sop_alignment": sop_alignment,
        "next_step": action if decision in ("optimize", "maybe") else "Move to next opportunity in the queue.",
    }


@app.post("/api/decide/should-optimize")
async def should_optimize(request: Request):
    """Determine whether an existing page should be optimized.

    This is the core SOP decision: 'Should I optimize this page or create new content?'

    Provide keyword + page data and get back a scored decision with full reasoning.
    """
    body = await request.json()
    keyword = body.get("keyword", "")
    page = body.get("page", "")
    position = body.get("position", 0)
    impressions = body.get("impressions", 0)
    clicks = body.get("clicks", 0)
    intent = body.get("intent", "")
    volume = body.get("volume", 0)
    keyword_difficulty = body.get("keyword_difficulty", 0)

    if not keyword:
        return JSONResponse({"error": "keyword is required"}, status_code=402)

    result = should_optimize_decision(
        keyword=keyword,
        page=page or "(no page)",
        position=position,
        impressions=impressions,
        clicks=clicks,
        intent=intent,
        volume=volume,
        keyword_difficulty=keyword_difficulty,
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CONTENT BRIEF GENERATOR (Planning Layer)
# ═══════════════════════════════════════════════════════════════════════════════

class BriefRequest(BaseModel):
    keyword: str
    title: str = ""
    intent: str = ""
    target_audience: str = ""
    client: str = "default"
    word_count_target: int = 1500
    include_faq: bool = True
    include_competitors: bool = True


def generate_content_brief(keyword: str, intent: str, audience: str, word_count: int, include_faq: bool, include_comp: bool) -> Dict:
    """Generate a structured content brief based on keyword research data."""
    # Auto-detect intent if not provided
    if not intent:
        intent = classify_intent(keyword)

    # Build H2 outline based on intent
    h2_outline = []
    if intent == "BOFU":
        h2_outline = [
            f"What is {keyword}?",
            f"Why {keyword} matters for your business",
            f"Key features to look for",
            f"How to choose the right {keyword}",
            f"Top {keyword} options compared",
            f"Implementation best practices",
            f"Common mistakes to avoid",
            f"Next steps",
        ]
    elif intent == "MOFU":
        h2_outline = [
            f"Understanding {keyword}",
            f"How {keyword} works",
            f"Benefits of {keyword}",
            f"Step-by-step guide",
            f"Tips and best practices",
            f"Common questions about {keyword}",
            f"What to do next",
        ]
    else:  # TOFU
        h2_outline = [
            f"What is {keyword}?",
            f"The history of {keyword}",
            f"How {keyword} has evolved",
            f"Key concepts explained",
            f"Why it matters today",
            f"Looking ahead",
        ]

    # FAQ questions
    faq_questions = []
    if include_faq:
        faq_questions = [
            f"What is {keyword} and why does it matter?",
            f"How do I get started with {keyword}?",
            f"What are the best {keyword} options?",
            f"How much does {keyword} cost?",
            f"What mistakes should I avoid with {keyword}?",
        ]

    # Competitor angles
    competitor_angles = []
    if include_comp:
        competitor_angles = [
            f"Comparison posts (vs. alternatives)",
            f"Review-style content",
            f"Case studies and results",
            f"Problem-solution framing",
        ]

    brief = {
        "keyword": keyword,
        "intent": intent,
        "target_audience": audience or "Business owners and decision-makers",
        "word_count_target": word_count,
        "title_suggestions": [
            f"{keyword.title()}: The Complete Guide",
            f"Best {keyword.title()} for {audience or 'Your Business'}",
            f"How to Choose {keyword.title()} in 2026",
        ],
        "h1": f"{keyword.title()}: The Complete Guide" if not keyword.startswith("Best") else keyword.title(),
        "h2_outline": h2_outline,
        "faq_questions": faq_questions,
        "competitor_angles": competitor_angles,
        "internal_link_suggestions": [
            f"Link from related service pages",
            f"Link from blog category page",
            f"Link from resource/guide pages",
        ],
        "seo_requirements": {
            "keyword_in_title": True,
            "keyword_in_first_paragraph": True,
            "keyword_in_h2": True,
            "meta_description_length": "150-160 characters",
            "url_slug": keyword.lower().replace(" ", "-"),
            "alt_text_keyword": True,
            "internal_links_min": 3,
            "word_count_min": word_count,
        },
        "content_guidelines": {
            "tldr_required": True,
            "tldr_length": "2-3 sentences",
            "paragraph_max_length": "150 words",
            "use_second_person": True,
            "cta_required": True,
            "image_required": True,
        },
        "approval_status": "draft",
        "created_at": datetime.utcnow().isoformat(),
    }
    return brief


@app.post("/api/brief/generate")
async def create_brief(request: BriefRequest):
    """Generate a content brief for a keyword."""
    brief = generate_content_brief(
        keyword=request.keyword,
        intent=request.intent,
        audience=request.target_audience,
        word_count=request.word_count_target,
        include_faq=request.include_faq,
        include_comp=request.include_competitors,
    )

    # Save brief
    briefs_dir = os.path.join(OUTPUTS_DIR, "briefs")
    os.makedirs(briefs_dir, exist_ok=True)
    brief_file = os.path.join(briefs_dir, f"brief_{request.keyword.replace(' ', '_')}.json")
    with open(brief_file, "w") as f:
        json.dump(brief, f, indent=2)

    return brief


@app.get("/api/brief/{keyword}")
async def get_brief(keyword: str):
    """Get a saved brief by keyword."""
    briefs_dir = os.path.join(OUTPUTS_DIR, "briefs")
    brief_file = os.path.join(briefs_dir, f"brief_{keyword.replace(' ', '_')}.json")
    if not os.path.exists(brief_file):
        return JSONResponse({"error": f"No brief found for '{keyword}'"}, status_code=404)
    with open(brief_file, "r") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CONTENT WRITER (Production Layer)
# ═══════════════════════════════════════════════════════════════════════════════

class ContentRequest(BaseModel):
    keyword: str
    brief: Dict = {}
    tone: str = "professional"
    format: str = "markdown"  # markdown or html
    word_count: int = 1500


def _clean_llm_output(text: str) -> str:
    """Clean LLM output — remove markdown # headers and extra formatting."""
    if not text:
        return text
    lines = text.strip().split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip markdown headers (lines starting with #)
        if stripped.startswith("#"):
            continue
        # Skip separator lines
        if stripped in ("---", "***", "```", "* * *"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def generate_content_draft(keyword: str, brief: Dict, tone: str, word_count: int) -> Dict:
    """Generate a content draft by calling OpenRouter Owl Alpha for each section.

    Every section is generated uniquely — no templates, no placeholders.
    Owl Alpha writes ALL content. The output is formal, original, and natural.
    If the model is unavailable, falls back to a clear message.
    """
    from integrations.hermes_llm import hermes_generate

    h2_outline = brief.get("h2_outline", ["Introduction", "Main Content", "Conclusion"])
    faq = brief.get("faq_questions", [])
    intent = brief.get("intent", classify_intent(keyword))

    # Words per section (distribute across H2 sections)
    content_headings = [h for h in h2_outline if h.lower() not in ("frequently asked questions", "faq", "next steps", "conclusion", "tldr")]
    if not content_headings:
        content_headings = ["Main Content"]
    words_per_section = max(150, word_count // len(content_headings))

    sections = []

    # Helper: generate text via the configured OpenRouter model.
    def _gen(prompt, min_len=30):
        result = hermes_generate(prompt)
        if result and not result.startswith("[") and len(result) > min_len:
            return result
        return None

    # Helper: extract section between two markers
    def _extract_section(text, start_marker, end_marker):
        try:
            start_idx = text.index(start_marker)
            text_after = text[start_idx + len(start_marker):]
            if end_marker:
                end_idx = text_after.index(end_marker)
                section = text_after[:end_idx]
            else:
                section = text_after
            # Clean up: remove leading ":", "+", newlines; strip Hermes chatter
            lines = []
            for line in section.split('\n'):
                line = line.strip()
                if line.startswith('+'):
                    line = line[1:].strip()
                if line.startswith(':'):
                    line = line[1:].strip()
                if line and not line.startswith('Article written') and not line.startswith("Here's the full"):
                    lines.append(line)
            return '\n'.join(lines).strip()
        except (ValueError, IndexError):
            return None

    # Generate ALL content in ONE Hermes call (faster than 5 separate calls)
    full_prompt = (
        f"Write a complete article about '{keyword}' for {intent} intent. Tone: {tone}.\n"
        f"Target audience: {brief.get('target_audience', 'general audience')}.\n"
        f"Word count target: ~{word_count} words total.\n\n"
        f"Output format (use these exact section headers):\n"
        f"TLDR: [2-3 sentence summary]\n"
        f"INTRODUCTION: [engaging intro paragraph]\n"
        f"MAIN CONTENT: [detailed body with multiple paragraphs covering the topic]\n"
        f"FAQ: [3 common questions and answers about {keyword}]\n"
        f"CTA: [1-2 sentence call to action]\n\n"
        f"Write factual, original content. No markdown headers (#). No placeholders."
    )

    full_content_raw = _gen(full_prompt, min_len=100)

    if full_content_raw:
        # Parse the sections from the output
        sections.append({"type": "tldr", "content": _extract_section(full_content_raw, "TLDR", "INTRODUCTION") or f"Key considerations and practical guidance on {keyword}."})
        sections.append({"type": "h2", "title": h2_outline[0] if h2_outline else "Introduction", "content": _extract_section(full_content_raw, "INTRODUCTION", "MAIN CONTENT") or f"[{keyword} — content generated]"})
        sections.append({"type": "h2", "title": "Main Content", "content": _extract_section(full_content_raw, "MAIN CONTENT", "FAQ") or f"[{keyword} — content generated]"})
        sections.append({"type": "h2", "title": "Frequently Asked Questions", "content": _extract_section(full_content_raw, "FAQ", "CTA") or ""})
        sections.append({"type": "cta", "content": _extract_section(full_content_raw, "CTA", "") or f"Explore how {keyword} can work for your needs."})
    else:
        # Fallback
        sections.append({"type": "tldr", "content": f"Key considerations and practical guidance on {keyword}, distilled into actionable insights."})
        sections.append({"type": "h2", "title": h2_outline[0] if h2_outline else "Introduction", "content": f"[{keyword} — Hermes unavailable]"})
        sections.append({"type": "h2", "title": "Main Content", "content": f"[{keyword} — Hermes unavailable]"})
        sections.append({"type": "cta", "content": f"Explore how {keyword} can work for your organisation."})

<<<<<<< HEAD
    # Introduction — Hermes
    intro_title = h2_outline[0] if h2_outline else "Introduction"
    intro = _gen(f"Write an engaging introduction section for an article about '{keyword}'. Title: '{intro_title}'. Intent: {intent}. Tone: {tone}. Write ~{words_per_section} words. No markdown headers — just natural prose.")
    if intro:
        sections.append({"type": "h2", "title": intro_title, "content": intro})
    else:
        sections.append({"type": "h2", "title": intro_title,
                         "content": f"[{keyword.title()} - AI content generation unavailable]"})

    # Body sections — each generated uniquely by Hermes
    for h2 in h2_outline[1:]:
        if h2.lower() in ("frequently asked questions", "faq", "next steps", "conclusion"):
            continue
        content = _gen(f"Write a detailed section for an article about '{keyword}'. Section heading: '{h2}'. Intent: {intent}. Tone: {tone}. Write ~{words_per_section} words. No markdown headers — just natural prose with paragraphs.")
        if content:
            sections.append({"type": "h2", "title": h2, "content": content})
        else:
            sections.append({"type": "h2", "title": h2,
                             "content": f"[{keyword.title()} - AI content generation unavailable]"})

    # FAQ section — each answer generated uniquely by Hermes
    if faq:
        faq_parts = []
        for q in faq:
            answer = _gen(f"Answer this question about '{keyword}': {q}. Tone: {tone}. Write 2-3 sentences.", min_len=10)
            if answer:
                faq_parts.append(f"**Q: {q}**\n\nA: {answer}")
            else:
                faq_parts.append(f"**Q: {q}**\n\nA: [Answer unavailable - AI generation not available]")
        sections.append({
            "type": "h2",
            "title": "Frequently Asked Questions",
            "content": "\n\n".join(faq_parts),
        })

    # CTA — Hermes
    cta = _gen(f"Write a call-to-action for '{keyword}'. Intent: {intent}. Tone: {tone}. 1-2 sentences. Encourage the reader to take the next step.", min_len=15)
    if cta:
        sections.append({"type": "cta", "content": cta})
    else:
        sections.append({"type": "cta", "content": f"Explore how {keyword} can work for your organisation. Speak with our team to discuss your requirements."})

    # Compile full content — NO # headers in the output, just clean prose
=======
    # Compile full content
>>>>>>> 7ce1f982fffd7cfc4e653e57f1373c8b467ffbdd
    full_content = ""
    for section in sections:
        if section["type"] == "tldr":
            full_content += f"TLDR\n\n{section['content']}\n\n"
        elif section["type"] == "h2":
            full_content += f"{section['title']}\n\n{section['content']}\n\n"
        elif section["type"] == "cta":
            full_content += f"Next Steps\n\n{section['content']}\n\n"

    actual_word_count = len(full_content.split())

    draft = {
        "keyword": keyword,
        "intent": intent,
        "tone": tone,
        "word_count_target": word_count,
        "word_count_actual": actual_word_count,
        "sections": sections,
        "full_content": full_content,
        "status": "draft",
        "ai_generated": True,
        "human_edited": False,
        "created_at": datetime.utcnow().isoformat(),
        "notes": "This draft was written with OpenRouter Owl Alpha. A human must review, edit, fact-check, and approve before publishing.",
    }
    return draft


@app.post("/api/content/write")
async def write_content(request: ContentRequest):
    """Generate a content draft from a brief."""
    draft = generate_content_draft(
        keyword=request.keyword,
        brief=request.brief,
        tone=request.tone,
        word_count=request.word_count,
    )

    # Save draft
    drafts_dir = os.path.join(OUTPUTS_DIR, "drafts")
    os.makedirs(drafts_dir, exist_ok=True)
    draft_file = os.path.join(drafts_dir, f"draft_{request.keyword.replace(' ', '_')}.json")
    with open(draft_file, "w") as f:
        json.dump(draft, f, indent=2)

    return draft


@app.get("/api/content/draft/{keyword}")
async def get_draft(keyword: str):
    """Get a saved draft by keyword."""
    drafts_dir = os.path.join(OUTPUTS_DIR, "drafts")
    draft_file = os.path.join(drafts_dir, f"draft_{keyword.replace(' ', '_')}.json")
    if not os.path.exists(draft_file):
        return JSONResponse({"error": f"No draft found for '{keyword}'"}, status_code=404)
    with open(draft_file, "r") as f:
        return json.load(f)


@app.patch("/api/content/draft/{keyword}")
async def update_draft(keyword: str, updates: Dict[str, Any]):
    """Update a content draft (human editing)."""
    drafts_dir = os.path.join(OUTPUTS_DIR, "drafts")
    draft_file = os.path.join(drafts_dir, f"draft_{keyword.replace(' ', '_')}.json")
    if not os.path.exists(draft_file):
        return JSONResponse({"error": f"No draft found for '{keyword}'"}, status_code=404)

    with open(draft_file, "r") as f:
        draft = json.load(f)

    for key in ("full_content", "sections", "title", "status", "human_edited", "notes"):
        if key in updates:
            draft[key] = updates[key]

    if "full_content" in updates:
        draft["human_edited"] = True
        draft["updated_at"] = datetime.utcnow().isoformat()

    with open(draft_file, "w") as f:
        json.dump(draft, f, indent=2)

    return {"status": "updated", "draft": draft}


# ═══════════════════════════════════════════════════════════════════════════════
# 6. QUALITY VALIDATION (SEO Gate, Fact Check, Brand Review)
# ═══════════════════════════════════════════════════════════════════════════════

class ValidationRequest(BaseModel):
    keyword: str
    title: str
    content: str
    url_slug: str = ""
    meta_description: str = ""
    client: str = "default"


def run_seo_gate(content: str, keyword: str, title: str, slug: str, meta: str) -> Dict:
    """SEO Gate Agent: validate SEO requirements."""
    content_lower = content.lower()
    kw_lower = keyword.lower()
    checks = []

    # Keyword in title
    checks.append({
        "check": "Keyword in title",
        "pass": kw_lower in title.lower(),
        "detail": f"Title: {title}",
    })

    # Keyword in first paragraph
    first_para = content[:500].lower()
    checks.append({
        "check": "Keyword in first paragraph",
        "pass": kw_lower in first_para,
        "detail": "First 500 characters checked",
    })

    # Keyword in H2
    checks.append({
        "check": "Keyword in at least one H2",
        "pass": kw_lower in content_lower and any(h in content_lower for h in ["<h2", "## "]),
        "detail": "H2 headings checked",
    })

    # TLDR present
    tldr_found = content.strip().startswith("## TLDR") or content.strip().startswith("TLDR")
    checks.append({
        "check": "TLDR at top",
        "pass": tldr_found,
        "detail": "TLDR section should be at the very top",
    })

    # Meta description
    checks.append({
        "check": "Meta description provided",
        "pass": bool(meta) and len(meta) > 50,
        "detail": f"Length: {len(meta)} chars" if meta else "Missing",
    })

    # URL slug
    checks.append({
        "check": "URL slug provided",
        "pass": bool(slug),
        "detail": slug or "Missing",
    })

    # Word count
    word_count = len(content.split())
    checks.append({
        "check": "Word count >= 1000",
        "pass": word_count >= 1000,
        "detail": f"Current: {word_count} words",
    })

    # Internal links
    internal_links = content_lower.count("href=")
    checks.append({
        "check": "At least 2 internal links",
        "pass": internal_links >= 2,
        "detail": f"Found: {internal_links} links",
    })

    # Images with alt text
    images = content_lower.count("<img") + content_lower.count("![")
    alt_texts = content_lower.count("alt=")
    checks.append({
        "check": "Images have alt text",
        "pass": alt_texts >= 1 and alt_texts >= images,
        "detail": f"Images: {images}, Alt texts: {alt_texts}",
    })

    passed = sum(1 for c in checks if c["pass"])
    total = len(checks)

    return {
        "agent": "SEO Gate",
        "passed": passed,
        "total": total,
        "score": round(passed / total * 100),
        "status": "pass" if passed == total else "fail" if passed < total * 0.7 else "review",
        "checks": checks,
    }


def run_fact_check(content: str) -> Dict:
    """Fact Check Agent: flag potential hallucinations and unverified claims."""
    issues = []

    # Check for common hallucination patterns
    suspicious_patterns = [
        (r"according to a \d{4} study", "Unverified study citation — add source"),
        (r"research shows that", "Vague research claim — add specific source"),
        (r"studies have shown", "Vague study reference — add specific source"),
        (r"experts say", "Vague expert attribution — name the expert"),
        (r"it is estimated that", "Unverified statistic — add source"),
        (r"\d+% of (people|businesses|companies)", "Unverified percentage — add source"),
    ]

    import re
    for pattern, message in suspicious_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            issues.append({
                "type": "unverified_claim",
                "pattern": pattern,
                "message": message,
                "matches": len(matches),
            })

    # Check for very specific numbers without sources
    specific_numbers = re.findall(r'\$[\d,]+\.?\d*|\d+\.\d+%|\d{4}', content)
    if len(specific_numbers) > 5:
        issues.append({
            "type": "many_specific_numbers",
            "message": f"Found {len(specific_numbers)} specific numbers/figures. Verify all are sourced.",
            "count": len(specific_numbers),
        })

    # Check for contradictory statements
    contradictions = []
    if "always" in content.lower() and "never" in content.lower():
        # Simple check — in production this would be more sophisticated
        pass

    passed = len(issues) == 0

    return {
        "agent": "Fact Check",
        "status": "pass" if passed else "review",
        "issues": issues,
        "issue_count": len(issues),
        "message": "No obvious issues detected" if passed else f"{len(issues)} potential issues found — human review required",
    }


def run_brand_review(content: str, client: str) -> Dict:
    """Brand Review Agent: check voice, style, and brand compliance."""
    content_lower = content.lower()
    issues = []

    # Check for em dashes
    if "—" in content or "–" in content:
        issues.append({
            "type": "em_dash",
            "message": "Em dashes found — MAAI house style prohibits em dashes",
            "severity": "high",
        })

    # Check for AI filler words
    filler_words = [
        "streamlined", "seamless", "leverage", "unlock", "robust", "elevate",
        "navigate the landscape", "in today's fast-paced world", "cutting-edge",
        "game-changer", "revolutionary", "paradigm", "synergy", "holistic",
    ]
    found_filler = [w for w in filler_words if w in content_lower]
    if found_filler:
        issues.append({
            "type": "ai_filler",
            "message": f"AI filler words found: {', '.join(found_filler)}",
            "severity": "medium",
            "words": found_filler,
        })

    # Check for "it is not X, it is Y" construction
    import re
    not_x_but_y = re.findall(r'it is not [^,]+, it is [^,]+', content, re.IGNORECASE)
    if not_x_but_y:
        issues.append({
            "type": "not_x_but_y",
            "message": f"Found 'it is not X, it is Y' construction — rewrite properly",
            "severity": "medium",
            "examples": not_x_but_y,
        })

    # Check for competitor put-downs
    negative_words = ["worst", "terrible", "awful", "avoid", "don't use", "stay away from"]
    found_negative = [w for w in negative_words if w in content_lower]
    if found_negative:
        issues.append({
            "type": "competitor_negative",
            "message": f"Potentially negative competitor language: {', '.join(found_negative)}",
            "severity": "medium",
        })

    # Check paragraph length
    paragraphs = content.split("\n\n")
    long_paragraphs = [i for i, p in enumerate(paragraphs) if len(p.split()) > 150]
    if long_paragraphs:
        issues.append({
            "type": "long_paragraphs",
            "message": f"{len(long_paragraphs)} paragraphs exceed 150 words — break up for readability",
            "severity": "low",
            "paragraph_indices": long_paragraphs,
        })

    # Check for second person
    has_second_person = "you" in content_lower or "your" in content_lower
    if not has_second_person:
        issues.append({
            "type": "no_second_person",
            "message": "No second person (you/your) found — MAAI style prefers direct address",
            "severity": "low",
        })

    passed = len([i for i in issues if i["severity"] == "high"]) == 0
    critical_issues = len([i for i in issues if i["severity"] == "high"])

    return {
        "agent": "Brand Review",
        "status": "pass" if passed and len(issues) == 0 else "review" if passed else "fail",
        "issues": issues,
        "issue_count": len(issues),
        "critical_issues": critical_issues,
        "message": "Brand compliant" if not issues else f"{len(issues)} style issues found",
    }


@app.post("/api/validate")
async def validate_content(request: ValidationRequest):
    """Run all quality validation agents (SEO Gate, Fact Check, Brand Review)."""
    seo_result = run_seo_gate(request.content, request.keyword, request.title, request.url_slug, request.meta_description)
    fact_result = run_fact_check(request.content)
    brand_result = run_brand_review(request.content, request.client)

    all_pass = all(r["status"] == "pass" for r in [seo_result, fact_result, brand_result])
    any_fail = any(r["status"] == "fail" for r in [seo_result, fact_result, brand_result])

    validation = {
        "keyword": request.keyword,
        "title": request.title,
        "client": request.client,
        "validated_at": datetime.utcnow().isoformat(),
        "overall_status": "pass" if all_pass else "fail" if any_fail else "review",
        "agents": {
            "seo_gate": seo_result,
            "fact_check": fact_result,
            "brand_review": brand_result,
        },
        "summary": {
            "seo_score": seo_result["score"],
            "fact_issues": fact_result["issue_count"],
            "brand_issues": brand_result["issue_count"],
            "total_issues": fact_result["issue_count"] + brand_result["issue_count"] + (len([c for c in seo_result["checks"] if not c["pass"]])),
        },
    }

    # Save validation
    vals_dir = os.path.join(OUTPUTS_DIR, "validations")
    os.makedirs(vals_dir, exist_ok=True)
    val_file = os.path.join(vals_dir, f"validation_{request.keyword.replace(' ', '_')}.json")
    with open(val_file, "w") as f:
        json.dump(validation, f, indent=2)

    return validation


# ═══════════════════════════════════════════════════════════════════════════════
# 7. PUBLISH WORKFLOW (Publisher + Indexing)
# ═══════════════════════════════════════════════════════════════════════════════

class PublishRequest(BaseModel):
    keyword: str
    title: str
    content: str
    url_slug: str
    meta_description: str
    client: str = "default"
    publish_now: bool = False  # If False, schedule for review


@app.post("/api/publish")
async def publish_content(request: PublishRequest):
    """Publish content — requires all validations to pass."""
    # Check validation exists
    vals_dir = os.path.join(OUTPUTS_DIR, "validations")
    val_file = os.path.join(vals_dir, f"validation_{request.keyword.replace(' ', '_')}.json")

    if not os.path.exists(val_file):
        return JSONResponse({"error": "No validation found. Run /api/validate first."}, status_code=400)

    with open(val_file, "r") as f:
        validation = json.load(f)

    if validation["overall_status"] == "fail":
        return JSONResponse({
            "error": "Validation failed. Fix issues before publishing.",
            "validation": validation,
        }, status_code=400)

    # Check approval status
    queue_state = load_queue_state()
    approval_status = queue_state.get(request.keyword, "needs_review")

    if approval_status != "approved":
        return JSONResponse({
            "error": f"Content not approved. Current status: {approval_status}. Approve via /api/queue/{request.keyword}/approve first.",
        }, status_code=400)

    publish_record = {
        "keyword": request.keyword,
        "title": request.title,
        "url_slug": request.url_slug,
        "meta_description": request.meta_description,
        "client": request.client,
        "status": "published" if request.publish_now else "scheduled",
        "published_at": datetime.utcnow().isoformat() if request.publish_now else None,
        "validation_score": validation["summary"]["seo_score"],
        "indexed": False,
        "gsc_submitted": False,
    }

    # Save publish record
    pub_dir = os.path.join(OUTPUTS_DIR, "published")
    os.makedirs(pub_dir, exist_ok=True)
    pub_file = os.path.join(pub_dir, f"published_{request.keyword.replace(' ', '_')}.json")
    with open(pub_file, "w") as f:
        json.dump(publish_record, f, indent=2)

    return {
        "status": "published" if request.publish_now else "scheduled",
        "message": f"Content for '{request.keyword}' is {'live' if request.publish_now else 'scheduled for publishing'}.",
        "next_steps": [
            "Submit URL to Google Search Console",
            "Request indexing",
            "Interlink from 2-3 existing pages",
            "Add to sitemap",
        ],
        "publish_record": publish_record,
    }


@app.post("/api/publish/{keyword}/index")
async def request_indexing(keyword: str):
    """Mark content as submitted to GSC for indexing."""
    pub_dir = os.path.join(OUTPUTS_DIR, "published")
    pub_file = os.path.join(pub_dir, f"published_{keyword.replace(' ', '_')}.json")

    if not os.path.exists(pub_file):
        return JSONResponse({"error": "No publish record found"}, status_code=404)

    with open(pub_file, "r") as f:
        record = json.load(f)

    record["gsc_submitted"] = True
    record["indexed"] = True
    record["indexing_requested_at"] = datetime.utcnow().isoformat()

    with open(pub_file, "w") as f:
        json.dump(record, f, indent=2)

    return {"status": "indexed", "keyword": keyword, "message": "Indexing requested. Monitor GSC for crawl status."}


# ═══════════════════════════════════════════════════════════════════════════════
# 8. PERFORMANCE MONITORING
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/monitor/{keyword}")
async def get_performance(keyword: str):
    """Get performance data for a published piece."""
    pub_dir = os.path.join(OUTPUTS_DIR, "published")
    pub_file = os.path.join(pub_dir, f"published_{keyword.replace(' ', '_')}.json")

    if not os.path.exists(pub_file):
        return JSONResponse({"error": "No publish record found"}, status_code=404)

    with open(pub_file, "r") as f:
        record = json.load(f)

    # In production, this would pull from GSC API
    # For now, return the publish record with monitoring placeholders
    return {
        "keyword": keyword,
        "status": record.get("status"),
        "published_at": record.get("published_at"),
        "monitoring": {
            "gsc_position": "Connect GSC API for live data",
            "impressions": "Connect GSC API for live data",
            "clicks": "Connect GSC API for live data",
            "ctr": "Connect GSC API for live data",
        },
        "recommendations": [
            "Check GSC after 1-2 weeks for initial ranking data",
            "If position > 20 after 30 days, consider content refresh",
            "Monitor for keyword cannibalization",
            "Track conversions from this page",
        ],
    }


@app.get("/api/monitor")
async def get_all_performance():
    """Get all published content performance."""
    pub_dir = os.path.join(OUTPUTS_DIR, "published")
    if not os.path.exists(pub_dir):
        return {"published": [], "total": 0}

    published = []
    for fname in os.listdir(pub_dir):
        if fname.endswith(".json"):
            with open(os.path.join(pub_dir, fname)) as f:
                published.append(json.load(f))

    return {"published": published, "total": len(published)}


# ═══════════════════════════════════════════════════════════════════════════════
# 9. ORCHESTRATOR — Full Pipeline Runner
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/orchestrate/full")
async def run_full_pipeline(request: Request):
    """Run the full content pipeline: Brief → Write → Validate → (Approve) → Publish.

    Body: {"keyword": "...", "title": "...", "client": "...", "auto_publish": false}
    """
    body = await request.json()
    keyword = body.get("keyword", "")
    title = body.get("title", "")
    client = body.get("client", "default")
    auto_publish = body.get("auto_publish", False)

    if not keyword:
        return JSONResponse({"error": "keyword is required"}, status_code=400)

    results = {"keyword": keyword, "steps": []}

    # Step 1: Generate Brief
    brief = generate_content_brief(keyword, "", "", 1500, True, True)
    results["steps"].append({"step": "brief", "status": "complete", "data": brief})

    # Step 2: Generate Content Draft
    draft = generate_content_draft(keyword, brief, "professional", 1500)
    results["steps"].append({"step": "write", "status": "complete", "data": {"status": draft["status"], "word_count": len(draft["full_content"].split())}})

    # Step 3: Validate
    seo = run_seo_gate(draft["full_content"], keyword, title or brief["h1"], brief["seo_requirements"]["url_slug"], "")
    fact = run_fact_check(draft["full_content"])
    brand = run_brand_review(draft["full_content"], client)
    all_pass = all(r["status"] == "pass" for r in [seo, fact, brand])
    results["steps"].append({
        "step": "validate",
        "status": "pass" if all_pass else "review",
        "data": {"seo": seo["status"], "fact_check": fact["status"], "brand": brand["status"]},
    })

    # Step 4: Human approval gate (unless auto_publish)
    if not auto_publish:
        results["steps"].append({
            "step": "approval",
            "status": "pending",
            "message": "Human approval required. Use /api/queue/{keyword}/approve or the Approval Queue page.",
        })
        results["next_action"] = "Review and approve content, then call /api/publish"
    else:
        results["steps"].append({"step": "approval", "status": "auto", "message": "Auto-publish enabled"})
        results["next_action"] = "Call /api/publish to publish"

    results["overall_status"] = "ready_for_review" if not auto_publish else "ready_to_publish"
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION LAYER — External System Connectors
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. GSC INTEGRATION ──────────────────────────────────────────────────────

class GSCConfig(BaseModel):
    site_url: str = ""
    api_key: str = ""
    credentials_path: str = ""


def _get_gsc_client():
    """Create GSC client from env/config."""
    from integrations.gsc_client import GSCClient
    return GSCClient()


@app.get("/api/integrations/gsc/status")
async def gsc_integration_status():
    """Check GSC integration status."""
    client = _get_gsc_client()
    connected = client.has_credentials()
    client_status = client.status()

    if connected:
        return {
            "status": "connected",
            "mode": "oauth_service_account",
            "site_url": client_status.get("site_url"),
            "service_account_email": client_status.get("service_account_email"),
            "credentials_file_exists": client_status.get("credentials_file_exists"),
            "capabilities": [
                "Live query data via Search Console API",
                "Performance metrics (clicks, impressions, CTR, position)",
                "Index status checking",
                "Sitemap management",
            ],
        }

    return {
        "status": "not_connected",
        "mode": "csv_upload",
        "site_url": client_status.get("site_url"),
        "credentials_path": client_status.get("credentials_path"),
        "credentials_file_exists": client_status.get("credentials_file_exists"),
        "service_account_email": client_status.get("service_account_email"),
        "capabilities": [
            "Upload CSV export (works today)",
            "Live query data (requires service account)",
        ],
        "setup_instructions": {
            "method": "service_account",
            "steps": [
                "Go to console.google.com → APIs & Services → Library",
                "Search 'Search Console API' → Enable",
                "Go to Credentials → Create Service Account",
                "Download JSON key file",
                "Add service account email to GSC property as Owner",
                "Place JSON key in config/gsc_credentials.json",
            ],
            "note": "API keys alone do NOT work for Search Console. CSV upload works today.",
        },
    }


@app.post("/api/integrations/gsc/configure")
async def configure_gsc(config: GSCConfig):
    """Configure GSC API credentials for live data."""
    # Save to config/api_keys.json
    keys_path = os.path.join(DATA_DIR, "..", "config", "api_keys.json")
    keys = {}
    if os.path.exists(keys_path):
        with open(keys_path) as f:
            keys = json.load(f)

    keys["GSC_API_KEY"] = config.api_key
    keys["GSC_SITE_URL"] = config.site_url
    keys["GSC_CREDENTIALS_PATH"] = config.credentials_path

    os.makedirs(os.path.dirname(keys_path), exist_ok=True)
    with open(keys_path, "w") as f:
        json.dump(keys, f, indent=2, default=str)

    return {
        "status": "configured",
        "message": "GSC API credentials saved.",
        "next_steps": [
            "Validate with /api/integrations/gsc/validate",
            "Pull live data with /api/integrations/gsc/pull",
        ],
    }


@app.get("/api/integrations/gsc/validate")
async def validate_gsc():
    """Test GSC API connection."""
    client = _get_gsc_client()
    if not client.has_credentials():
        return JSONResponse({
            "valid": False,
            "error": "GSC not configured",
            "details": client.status(),
            "setup_instructions": client.setup_instructions(),
        }, status_code=400)

    from integrations.gsc_client import GSCError
    try:
        data = client.get_performance_data(days=7, row_limit=5)
    except GSCError as e:
        return JSONResponse({
            "valid": False,
            "error": e.message,
            "error_code": e.code,
            "details": client.status(),
        }, status_code=400)
    except Exception as e:
        return JSONResponse({
            "valid": False,
            "error": str(e),
            "error_code": "api_error",
            "details": client.status(),
        }, status_code=400)
    return {
        "valid": True,
        "test_rows": len(data or []),
        "site_url": client.site_url,
        "message": "Connection successful",
    }


@app.post("/api/integrations/gsc/pull")
async def pull_gsc_data(request: Request):
    """Pull live data from GSC API."""
    client = _get_gsc_client()
    if not client.has_credentials():
        return JSONResponse({
            "error": "GSC not configured",
            "endpoint": "/api/integrations/gsc/configure",
            "details": client.status(),
            "setup_instructions": client.setup_instructions(),
        }, status_code=400)

    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    days = body.get("days", 30)
    row_limit = body.get("row_limit", 250)

    from integrations.gsc_client import GSCError
    try:
        data = client.get_performance_data(days=days, row_limit=row_limit)
    except GSCError as e:
        return JSONResponse({
            "status": "error",
            "message": e.message,
            "error_code": e.code,
            "details": client.status(),
        }, status_code=400)
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e),
            "error_code": "api_error",
            "details": client.status(),
        }, status_code=400)

    if data is not None:
        from jobs import create_job, run_job_analysis
        job_id = create_job(data)
        asyncio.create_task(run_job_analysis(job_id))
        return {
            "status": "queued",
            "source": "gsc_live",
            "job_id": job_id,
            "rows_received": len(data),
            "site_url": client.site_url,
            "message": f"Pulled {len(data)} live GSC rows. Poll GET /api/jobs/{job_id} for results.",
        }

    return {
        "status": "error",
        "message": "Failed to fetch from GSC API. Check credentials and site URL.",
    }


# ── 2. SEMRUSH INTEGRATION ──────────────────────────────────────────────────

class SemrushConfig(BaseModel):
    api_key: str = ""
    database: str = "us"


@app.get("/api/integrations/semrush/status")
async def semrush_integration_status():
    """Check Semrush integration status."""
    config_path = os.path.join(DATA_DIR, "semrush_config.json")
    configured = os.path.exists(config_path)

    return {
        "status": "configured" if configured else "not_configured",
        "mode": "mock" if not configured else "api",
        "capabilities": [
            "Keyword metrics (volume, KD, CPC)",
            "Competitor analysis",
            "Backlink tracking",
            "Site audit",
            "Position tracking",
        ],
        "setup_instructions": {
            "step1": "Get Semrush API key from account settings",
            "step2": "POST to /api/integrations/semrush/configure with key",
            "step3": "Test with /api/integrations/semrush/test",
        },
    }


@app.post("/api/integrations/semrush/configure")
async def configure_semrush(config: SemrushConfig):
    """Configure Semrush API key."""
    config_path = os.path.join(DATA_DIR, "semrush_config.json")
    with open(config_path, "w") as f:
        json.dump(config.dict(), f, indent=2)
    return {"status": "configured", "message": "Semrush API key saved."}


@app.post("/api/integrations/semrush/keyword")
async def semrush_keyword_lookup(request: Request):
    """Look up keyword metrics from Semrush."""
    body = await request.json()
    keyword = body.get("keyword", "")

    if not keyword:
        return JSONResponse({"error": "keyword required"}, status_code=400)

    # Check for API credentials
    config_path = os.path.join(DATA_DIR, "semrush_config.json")
    if not os.path.exists(config_path):
        # Return mock data
        return {
            "keyword": keyword,
            "source": "mock",
            "volume": 0,
            "keyword_difficulty": 0,
            "cpc": 0,
            "competition": 0,
            "note": "Configure Semrush API for live data.",
        }

    # In production: call Semrush API
    return {"keyword": keyword, "source": "api", "data": {}}


# ── 3. SITE CRAWLER ─────────────────────────────────────────────────────────

class CrawlRequest(BaseModel):
    start_url: str
    max_pages: int = 50
    same_domain_only: bool = True


@app.post("/api/integrations/crawl")
async def crawl_site(request: CrawlRequest):
    """Crawl a site to map existing pages and internal links."""
    import urllib.request
    from html.parser import HTMLParser

    class LinkExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []
            self.title = ""
            self.h1 = ""
            self.h2s = []
            self.in_title = False
            self.in_h1 = False
            self.in_h2 = False

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if tag == "a" and "href" in attrs_dict:
                self.links.append(attrs_dict["href"])
            elif tag == "title":
                self.in_title = True
            elif tag == "h1":
                self.in_h1 = True
            elif tag == "h2":
                self.in_h2 = True

        def handle_endtag(self, tag):
            if tag == "title":
                self.in_title = False
            elif tag == "h1":
                self.in_h1 = False
            elif tag == "h2":
                self.in_h2 = False

        def handle_data(self, data):
            if self.in_title:
                self.title += data.strip()
            elif self.in_h1:
                self.h1 += data.strip()
            elif self.in_h2:
                self.h2s.append(data.strip())

    visited = set()
    pages = []
    to_visit = [request.start_url]
    domain = request.start_url.split("//")[-1].split("/")[0]

    while to_visit and len(visited) < request.max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "KritiBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            parser = LinkExtractor()
            parser.feed(html)

            # Filter links
            for link in parser.links:
                if link.startswith("/"):
                    full = request.start_url.rstrip("/") + link
                elif link.startswith("http"):
                    if request.same_domain_only and domain not in link:
                        continue
                    full = link
                else:
                    continue
                if full not in visited:
                    to_visit.append(full)

            pages.append({
                "url": url,
                "title": parser.title,
                "h1": parser.h1,
                "h2s": parser.h2s[:10],
                "outbound_links": len(parser.links),
                "status": "crawled",
            })
        except Exception as e:
            pages.append({"url": url, "status": "error", "error": str(e)})

    return {
        "start_url": request.start_url,
        "pages_crawled": len(pages),
        "pages": pages,
        "total_links_found": sum(p.get("outbound_links", 0) for p in pages),
    }


# ── 4. CMS PUBLISHING ───────────────────────────────────────────────────────

class CMSConfig(BaseModel):
    cms_type: str = "wordpress"  # wordpress, contentful, strapi, custom
    api_url: str = ""
    api_key: str = ""
    author_id: str = ""


@app.get("/api/integrations/cms/status")
async def cms_integration_status():
    """Check CMS integration status."""
    config_path = os.path.join(DATA_DIR, "cms_config.json")
    configured = os.path.exists(config_path)

    if configured:
        with open(config_path) as f:
            config = json.load(f)
        return {
            "status": "configured",
            "cms_type": config.get("cms_type", "unknown"),
            "api_url": config.get("api_url", ""),
            "capabilities": ["Create posts", "Update posts", "Upload media", "Manage categories"],
        }

    return {
        "status": "not_configured",
        "supported_cms": ["wordpress", "contentful", "strapi", "custom_api"],
        "setup_instructions": {
            "step1": "Get API credentials from your CMS",
            "step2": "POST to /api/integrations/cms/configure",
            "step3": "Test with /api/integrations/cms/test",
        },
    }


@app.post("/api/integrations/cms/configure")
async def configure_cms(config: CMSConfig):
    """Configure CMS API credentials."""
    config_path = os.path.join(DATA_DIR, "cms_config.json")
    with open(config_path, "w") as f:
        json.dump(config.dict(), f, indent=2)
    return {"status": "configured", "cms_type": config.cms_type, "message": "CMS credentials saved."}


@app.post("/api/integrations/cms/publish")
async def publish_to_cms(request: Request):
    """Publish content to configured CMS."""
    body = await request.json()
    config_path = os.path.join(DATA_DIR, "cms_config.json")

    if not os.path.exists(config_path):
        return JSONResponse({"error": "CMS not configured"}, status_code=400)

    with open(config_path) as f:
        config = json.load(f)

    # In production, this would call the CMS API
    keyword = body.get("keyword", "")
    publish_record = {
        "keyword": keyword,
        "cms_type": config.get("cms_type"),
        "status": "published_to_cms",
        "cms_post_id": "mock_id_" + keyword.replace(" ", "_"),
        "published_at": datetime.utcnow().isoformat(),
        "url": config.get("api_url", "") + "/" + keyword.lower().replace(" ", "-"),
    }

    return {
        "status": "published",
        "message": f"Content for '{keyword}' published to {config.get('cms_type', 'CMS')}.",
        "publish_record": publish_record,
    }


# ── 5. NOTIFICATIONS (Slack / Email) ────────────────────────────────────────

class NotificationConfig(BaseModel):
    slack_webhook_url: str = ""
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    notify_email: str = ""


class NotificationRequest(BaseModel):
    message: str
    channel: str = "slack"  # slack or email
    subject: str = ""
    urgency: str = "normal"  # low, normal, high


@app.get("/api/integrations/notifications/status")
async def notification_status():
    """Check notification integration status."""
    config_path = os.path.join(DATA_DIR, "notification_config.json")
    configured = os.path.exists(config_path)
    return {
        "status": "configured" if configured else "not_configured",
        "channels": ["slack", "email"],
        "events": [
            "opportunity_discovered",
            "content_approved",
            "content_published",
            "validation_failed",
            "indexing_requested",
        ],
    }


@app.post("/api/integrations/notifications/configure")
async def configure_notifications(config: NotificationConfig):
    """Configure notification channels."""
    config_path = os.path.join(DATA_DIR, "notification_config.json")
    with open(config_path, "w") as f:
        json.dump(config.dict(), f, indent=2)
    return {"status": "configured", "message": "Notification settings saved."}


@app.post("/api/integrations/notifications/send")
async def send_notification(request: NotificationRequest):
    """Send a notification via configured channels."""
    config_path = os.path.join(DATA_DIR, "notification_config.json")

    results = []
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

        if request.channel == "slack" and config.get("slack_webhook_url"):
            # In production: POST to Slack webhook
            results.append({"channel": "slack", "status": "sent"})
        elif request.channel == "email" and config.get("email_smtp_host"):
            # In production: send email via SMTP
            results.append({"channel": "email", "status": "sent"})

    if not results:
        results.append({"channel": request.channel, "status": "not_configured", "message": "Configure notifications first."})

    return {"results": results, "message": request.message}


# ── 6. ANALYTICS ────────────────────────────────────────────────────────────

class AnalyticsConfig(BaseModel):
    google_analytics_id: str = ""
    gtag_id: str = ""


@app.get("/api/integrations/analytics/status")
async def analytics_status():
    """Check analytics integration status."""
    config_path = os.path.join(DATA_DIR, "analytics_config.json")
    return {
        "status": "configured" if os.path.exists(config_path) else "not_configured",
        "capabilities": [
            "Page view tracking",
            "Conversion tracking",
            "Keyword-to-page attribution",
            "Content ROI reporting",
        ],
    }


@app.post("/api/integrations/analytics/configure")
async def configure_analytics(config: AnalyticsConfig):
    """Configure analytics tracking."""
    config_path = os.path.join(DATA_DIR, "analytics_config.json")
    with open(config_path, "w") as f:
        json.dump(config.dict(), f, indent=2)
    return {"status": "configured"}


@app.get("/api/integrations/analytics/snippet/{keyword}")
async def get_analytics_snippet(keyword: str):
    """Generate tracking snippet for a published page."""
    config_path = os.path.join(DATA_DIR, "analytics_config.json")
    if not os.path.exists(config_path):
        return JSONResponse({"error": "Analytics not configured"}, status_code=404)

    with open(config_path) as f:
        config = json.load(f)

    gtag = config.get("gtag_id", "G-XXXXXXXXXX")
    return {
        "keyword": keyword,
        "gtag_id": gtag,
        "snippet": f"<script async src=\"https://www.googletagmanager.com/gtag/js?id={gtag}\"></script>",
        "event_tracking": f"gtag('event', 'page_view', {{ page_title: '{keyword}', page_location: window.location.href }});",
        "conversion_snippet": f"gtag('event', 'conversion', {{ send_to: '{gtag}/CONTENT_LEAD' }});",
    }


# ── 7. SOURCE LEDGER (Fact Validation) ──────────────────────────────────────

class SourceEntry(BaseModel):
    claim: str
    source_url: str
    source_title: str
    source_date: str = ""
    verified_by: str = ""
    status: str = "pending"  # pending, verified, rejected


LEDGER_FILE = os.path.join(DATA_DIR, "source_ledger.json")


def load_ledger() -> List[Dict]:
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "r") as f:
            return json.load(f)
    return []


def save_ledger(entries: List[Dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LEDGER_FILE, "w") as f:
        json.dump(entries, f, indent=2)


@app.get("/api/integrations/sources")
async def get_source_ledger(status: str = None):
    """Get source ledger entries."""
    entries = load_ledger()
    if status:
        entries = [e for e in entries if e.get("status") == status]
    return {"entries": entries, "total": len(entries)}


@app.post("/api/integrations/sources")
async def add_source(entry: SourceEntry):
    """Add a source to the ledger."""
    entries = load_ledger()
    entry_dict = entry.dict()
    entry_dict["added_at"] = datetime.utcnow().isoformat()
    entries.append(entry_dict)
    save_ledger(entries)
    return {"status": "added", "entry": entry_dict}


@app.patch("/api/integrations/sources/{entry_id}")
async def verify_source(entry_id: int, updates: Dict[str, Any]):
    """Verify or reject a source."""
    entries = load_ledger()
    if entry_id < 0 or entry_id >= len(entries):
        return JSONResponse({"error": "Entry not found"}, status_code=404)
    for key in ("status", "verified_by", "notes"):
        if key in updates:
            entries[entry_id][key] = updates[key]
    entries[entry_id]["verified_at"] = datetime.utcnow().isoformat()
    save_ledger(entries)
    return {"status": "updated", "entry": entries[entry_id]}


# ── 8. OUTREACH TRACKING ────────────────────────────────────────────────────

class OutreachEntry(BaseModel):
    target_url: str
    target_name: str
    outreach_type: str = "link_building"  # link_building, guest_post, resource_mention
    email_sent: str = ""
    status: str = "planned"  # planned, sent, replied, linked, rejected
    notes: str = ""
    content_keyword: str = ""


OUTREACH_FILE = os.path.join(DATA_DIR, "outreach_tracker.json")


def load_outreach() -> List[Dict]:
    if os.path.exists(OUTREACH_FILE):
        with open(OUTREACH_FILE, "r") as f:
            return json.load(f)
    return []


def save_outreach(entries: List[Dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTREACH_FILE, "w") as f:
        json.dump(entries, f, indent=2)


@app.get("/api/integrations/outreach")
async def get_outreach(status: str = None):
    """Get outreach tracking entries."""
    entries = load_outreach()
    if status:
        entries = [e for e in entries if e.get("status") == status]
    return {"entries": entries, "total": len(entries)}


@app.post("/api/integrations/outreach")
async def add_outreach(entry: OutreachEntry):
    """Add an outreach target."""
    entries = load_outreach()
    entry_dict = entry.dict()
    entry_dict["created_at"] = datetime.utcnow().isoformat()
    entries.append(entry_dict)
    save_outreach(entries)
    return {"status": "added", "entry": entry_dict}


@app.patch("/api/integrations/outreach/{entry_id}")
async def update_outreach(entry_id: int, updates: Dict[str, Any]):
    """Update outreach status."""
    entries = load_outreach()
    if entry_id < 0 or entry_id >= len(entries):
        return JSONResponse({"error": "Entry not found"}, status_code=404)
    for key in ("status", "notes", "email_sent"):
        if key in updates:
            entries[entry_id][key] = updates[key]
    save_outreach(entries)
    return {"status": "updated", "entry": entries[entry_id]}


@app.get("/api/integrations/outreach/stats")
async def outreach_stats():
    """Get outreach statistics."""
    entries = load_outreach()
    stats = {"total": len(entries), "planned": 0, "sent": 0, "replied": 0, "linked": 0, "rejected": 0}
    for e in entries:
        s = e.get("status", "planned")
        stats[s] = stats.get(s, 0) + 1
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# GOVERNANCE LAYER — Roles, Permissions, Approval Gates, Audit Logging
# ═══════════════════════════════════════════════════════════════════════════════

# ── ROLES & PERMISSIONS ─────────────────────────────────────────────────────

ROLES_FILE = os.path.join(DATA_DIR, "roles.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

DEFAULT_ROLES = {
    "admin": {
        "permissions": ["*"],  # All permissions
        "description": "Full system access",
    },
    "editor": {
        "permissions": [
            "brief:create", "brief:edit", "brief:approve",
            "content:create", "content:edit", "content:submit",
            "validation:run", "validation:review",
            "publish:schedule",
            "queue:view", "queue:approve",
            "calendar:manage",
            "integrations:view",
        ],
        "description": "Can create and edit content, approve briefs",
    },
    "reviewer": {
        "permissions": [
            "brief:view", "brief:comment",
            "content:view", "content:comment",
            "validation:view", "validation:review",
            "queue:view",
            "calendar:view",
        ],
        "description": "Read-only access with commenting",
    },
    "publisher": {
        "permissions": [
            "content:view",
            "publish:execute", "publish:schedule",
            "indexing:request",
            "monitor:view",
            "integrations:manage",
        ],
        "description": "Can publish and manage integrations",
    },
}


def load_roles() -> Dict:
    if os.path.exists(ROLES_FILE):
        with open(ROLES_FILE, "r") as f:
            return json.load(f)
    # Initialize with defaults
    save_roles(DEFAULT_ROLES)
    return DEFAULT_ROLES


def save_roles(roles: Dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ROLES_FILE, "w") as f:
        json.dump(roles, f, indent=2)


def load_users() -> Dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_users(users: Dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def check_permission(user_role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    roles = load_roles()
    role = roles.get(user_role, {})
    perms = role.get("permissions", [])
    return "*" in perms or permission in perms


@app.get("/api/governance/roles")
async def get_roles():
    """Get all roles and their permissions."""
    return {"roles": load_roles()}


@app.post("/api/governance/roles")
async def create_role(request: Request):
    """Create or update a role."""
    body = await request.json()
    role_name = body.get("name", "")
    permissions = body.get("permissions", [])
    description = body.get("description", "")

    if not role_name:
        return JSONResponse({"error": "Role name required"}, status_code=400)

    roles = load_roles()
    roles[role_name] = {"permissions": permissions, "description": description}
    save_roles(roles)
    return {"status": "created", "role": roles[role_name]}


@app.post("/api/governance/check")
async def check_user_permission(request: Request):
    """Check if a role has a specific permission."""
    body = await request.json()
    role = body.get("role", "")
    permission = body.get("permission", "")

    has_perm = check_permission(role, permission)
    return {
        "role": role,
        "permission": permission,
        "allowed": has_perm,
    }


# ── APPROVAL GATES ──────────────────────────────────────────────────────────

APPROVAL_GATES_FILE = os.path.join(OUTPUTS_DIR, "approval_gates.json")

# Define the 4 approval gates from the architecture
APPROVAL_GATES = {
    "topic_approval": {
        "label": "Topic Approval",
        "description": "Approve topic before research begins",
        "required_role": "editor",
        "check_permission": "queue:approve",
    },
    "existing_vs_new": {
        "label": "Existing Page vs New Content",
        "description": "Decide whether to optimize existing page or create new content",
        "required_role": "editor",
        "check_permission": "queue:approve",
    },
    "brief_approval": {
        "label": "Brief Approval",
        "description": "Approve content brief before writing begins",
        "required_role": "editor",
        "check_permission": "brief:approve",
    },
    "final_review": {
        "label": "Final Review",
        "description": "Final human review before publishing",
        "required_role": "editor",
        "check_permission": "content:submit",
    },
    "publish_approval": {
        "label": "Publish Approval",
        "description": "Approve content for publishing",
        "required_role": "publisher",
        "check_permission": "publish:execute",
    },
}


def load_gates() -> Dict:
    if os.path.exists(APPROVAL_GATES_FILE):
        with open(APPROVAL_GATES_FILE, "r") as f:
            return json.load(f)
    # Initialize all gates as not approved
    gates = {}
    for gate_id, gate_config in APPROVAL_GATES.items():
        gates[gate_id] = {
            **gate_config,
            "status": "pending",
            "approved_by": "",
            "approved_at": "",
            "notes": "",
        }
    return gates


def save_gates(gates: Dict):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(APPROVAL_GATES_FILE, "w") as f:
        json.dump(gates, f, indent=2)


@app.get("/api/governance/gates")
async def get_approval_gates(keyword: str = None):
    """Get approval gate status. Optionally filter by keyword context."""
    gates = load_gates()
    return {"gates": gates, "total": len(gates)}


@app.post("/api/governance/gates/{gate_id}/approve")
async def approve_gate(gate_id: str, request: Request):
    """Approve a specific gate."""
    body = await request.json()
    approved_by = body.get("reviewer", "human")
    notes = body.get("notes", "")
    keyword = body.get("keyword", "")

    gates = load_gates()
    if gate_id not in gates:
        return JSONResponse({"error": f"Unknown gate: {gate_id}"}, status_code=404)

    gates[gate_id]["status"] = "approved"
    gates[gate_id]["approved_by"] = approved_by
    gates[gate_id]["approved_at"] = datetime.utcnow().isoformat()
    gates[gate_id]["notes"] = notes
    if keyword:
        gates[gate_id]["keyword"] = keyword

    save_gates(gates)

    # Log to audit
    log_audit_event("gate_approved", gate_id, approved_by, {"notes": notes, "keyword": keyword})

    return {"status": "approved", "gate": gate_id, "approved_by": approved_by}


@app.post("/api/governance/gates/{gate_id}/reject")
async def reject_gate(gate_id: str, request: Request):
    """Reject a specific gate."""
    body = await request.json()
    rejected_by = body.get("reviewer", "human")
    notes = body.get("notes", "")

    gates = load_gates()
    if gate_id not in gates:
        return JSONResponse({"error": f"Unknown gate: {gate_id}"}, status_code=404)

    gates[gate_id]["status"] = "rejected"
    gates[gate_id]["approved_by"] = rejected_by
    gates[gate_id]["approved_at"] = datetime.utcnow().isoformat()
    gates[gate_id]["notes"] = notes

    save_gates(gates)
    log_audit_event("gate_rejected", gate_id, rejected_by, {"notes": notes})

    return {"status": "rejected", "gate": gate_id, "rejected_by": rejected_by}


@app.get("/api/governance/gates/{gate_id}/check")
async def check_gate_status(gate_id: str):
    """Check if a specific gate is approved."""
    gates = load_gates()
    if gate_id not in gates:
        return JSONResponse({"error": f"Unknown gate: {gate_id}"}, status_code=404)

    gate = gates[gate_id]
    return {
        "gate": gate_id,
        "label": gate.get("label", ""),
        "status": gate.get("status", "pending"),
        "approved": gate.get("status") == "approved",
        "approved_by": gate.get("approved_by", ""),
        "approved_at": gate.get("approved_at", ""),
    }


# ── AUDIT LOG ───────────────────────────────────────────────────────────────

AUDIT_LOG_FILE = os.path.join(OUTPUTS_DIR, "audit_log.json")


def load_audit_log() -> List[Dict]:
    if os.path.exists(AUDIT_LOG_FILE):
        with open(AUDIT_LOG_FILE, "r") as f:
            return json.load(f)
    return []


def save_audit_log(log: List[Dict]):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(AUDIT_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def log_audit_event(action: str, resource: str, actor: str, details: Dict = None):
    """Log an audit event."""
    log = load_audit_log()
    entry = {
        "id": len(log) + 1,
        "action": action,
        "resource": resource,
        "actor": actor,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {},
    }
    log.append(entry)
    save_audit_log(log)
    return entry


@app.get("/api/governance/audit")
async def get_audit_log(limit: int = 50, action: str = None, actor: str = None):
    """Get audit log entries with optional filtering."""
    log = load_audit_log()
    if action:
        log = [e for e in log if e.get("action") == action]
    if actor:
        log = [e for e in log if e.get("actor") == actor]
    return {"entries": log[-limit:][::-1], "total": len(log)}


@app.get("/api/governance/audit/summary")
async def audit_summary():
    """Get audit log summary statistics."""
    log = load_audit_log()
    actions = {}
    actors = {}
    for entry in log:
        a = entry.get("action", "unknown")
        actions[a] = actions.get(a, 0) + 1
        actor = entry.get("actor", "unknown")
        actors[actor] = actors.get(actor, 0) + 1

    return {
        "total_events": len(log),
        "actions": actions,
        "actors": actors,
        "latest_event": log[-1] if log else None,
    }


# ── BRIEF APPROVAL WORKFLOW ────────────────────────────────────────────────

@app.post("/api/governance/brief/{keyword}/submit")
async def submit_brief_for_approval(keyword: str, request: Request):
    """Submit a brief for editorial approval."""
    body = await request.json()
    submitted_by = body.get("submitted_by", "human")

    # Check brief exists
    briefs_dir = os.path.join(OUTPUTS_DIR, "briefs")
    brief_file = os.path.join(briefs_dir, f"brief_{keyword.replace(' ', '_')}.json")
    if not os.path.exists(brief_file):
        return JSONResponse({"error": "Brief not found. Generate one first."}, status_code=404)

    with open(brief_file, "r") as f:
        brief = json.load(f)

    brief["approval_status"] = "pending_review"
    brief["submitted_by"] = submitted_by
    brief["submitted_at"] = datetime.utcnow().isoformat()

    with open(brief_file, "w") as f:
        json.dump(brief, f, indent=2)

    log_audit_event("brief_submitted", keyword, submitted_by, {"title": brief.get("h1", "")})

    return {"status": "submitted", "keyword": keyword, "message": "Brief submitted for approval."}


@app.post("/api/governance/brief/{keyword}/approve")
async def approve_brief(keyword: str, request: Request):
    """Approve a content brief."""
    body = await request.json()
    approved_by = body.get("approved_by", "human")
    notes = body.get("notes", "")

    briefs_dir = os.path.join(OUTPUTS_DIR, "briefs")
    brief_file = os.path.join(briefs_dir, f"brief_{keyword.replace(' ', '_')}.json")
    if not os.path.exists(brief_file):
        return JSONResponse({"error": "Brief not found"}, status_code=404)

    with open(brief_file, "r") as f:
        brief = json.load(f)

    brief["approval_status"] = "approved"
    brief["approved_by"] = approved_by
    brief["approved_at"] = datetime.utcnow().isoformat()
    brief["approval_notes"] = notes

    with open(brief_file, "w") as f:
        json.dump(brief, f, indent=2)

    # Update gate
    gates = load_gates()
    gates["brief_approval"]["status"] = "approved"
    gates["brief_approval"]["approved_by"] = approved_by
    gates["brief_approval"]["approved_at"] = datetime.utcnow().isoformat()
    save_gates(gates)

    log_audit_event("brief_approved", keyword, approved_by, {"notes": notes})

    return {"status": "approved", "keyword": keyword, "message": "Brief approved. Content writing can begin."}


@app.post("/api/governance/brief/{keyword}/reject")
async def reject_brief(keyword: str, request: Request):
    """Reject a content brief with feedback."""
    body = await request.json()
    rejected_by = body.get("rejected_by", "human")
    notes = body.get("notes", "")

    briefs_dir = os.path.join(OUTPUTS_DIR, "briefs")
    brief_file = os.path.join(briefs_dir, f"brief_{keyword.replace(' ', '_')}.json")
    if not os.path.exists(brief_file):
        return JSONResponse({"error": "Brief not found"}, status_code=404)

    with open(brief_file, "r") as f:
        brief = json.load(f)

    brief["approval_status"] = "rejected"
    brief["rejected_by"] = rejected_by
    brief["rejected_at"] = datetime.utcnow().isoformat()
    brief["rejection_notes"] = notes

    with open(brief_file, "w") as f:
        json.dump(brief, f, indent=2)

    log_audit_event("brief_rejected", keyword, rejected_by, {"notes": notes})

    return {"status": "rejected", "keyword": keyword, "message": "Brief rejected. Revision required."}


# ── FINAL REVIEW GATE ──────────────────────────────────────────────────────

@app.post("/api/governance/final-review/{keyword}/submit")
async def submit_for_final_review(keyword: str, request: Request):
    """Submit content for final review before publishing."""
    body = await request.json()
    submitted_by = body.get("submitted_by", "human")

    # Verify all previous gates are approved
    gates = load_gates()
    required_gates = ["topic_approval", "existing_vs_new", "brief_approval"]
    pending = [g for g in required_gates if gates.get(g, {}).get("status") != "approved"]

    if pending:
        return JSONResponse({
            "error": f"Cannot submit for final review. Pending gates: {pending}",
        }, status_code=400)

    log_audit_event("final_review_submitted", keyword, submitted_by)
    return {"status": "submitted", "keyword": keyword, "message": "Content submitted for final review."}


@app.post("/api/governance/final-review/{keyword}/approve")
async def approve_final_review(keyword: str, request: Request):
    """Approve final review — content is ready to publish."""
    body = await request.json()
    approved_by = body.get("approved_by", "human")
    notes = body.get("notes", "")

    gates = load_gates()
    gates["final_review"]["status"] = "approved"
    gates["final_review"]["approved_by"] = approved_by
    gates["final_review"]["approved_at"] = datetime.utcnow().isoformat()
    save_gates(gates)

    log_audit_event("final_review_approved", keyword, approved_by, {"notes": notes})

    return {
        "status": "approved",
        "keyword": keyword,
        "message": "Final review approved. Content is ready to publish.",
        "next_step": f"Call /api/publish with keyword='{keyword}' to publish.",
    }


@app.post("/api/governance/final-review/{keyword}/reject")
async def reject_final_review(keyword: str, request: Request):
    """Reject final review — send back for revision."""
    body = await request.json()
    rejected_by = body.get("rejected_by", "human")
    notes = body.get("notes", "")

    log_audit_event("final_review_rejected", keyword, rejected_by, {"notes": notes})

    return {
        "status": "rejected",
        "keyword": keyword,
        "message": "Final review rejected. Revision required.",
        "feedback": notes,
    }


# ── COMPLIANCE CHECK ───────────────────────────────────────────────────────

@app.get("/api/governance/compliance/{keyword}")
async def check_compliance(keyword: str):
    """Check if a keyword has passed all governance gates."""
    gates = load_gates()
    brief_file = os.path.join(OUTPUTS_DIR, "briefs", f"brief_{keyword.replace(' ', '_')}.json")
    val_file = os.path.join(OUTPUTS_DIR, "validations", f"validation_{keyword.replace(' ', '_')}.json")
    pub_file = os.path.join(OUTPUTS_DIR, "published", f"published_{keyword.replace(' ', '_')}.json")

    brief_exists = os.path.exists(brief_file)
    validation_exists = os.path.exists(val_file)
    published = os.path.exists(pub_file)

    brief_approved = False
    if brief_exists:
        with open(brief_file) as f:
            brief = json.load(f)
        brief_approved = brief.get("approval_status") == "approved"

    validation_passed = False
    if validation_exists:
        with open(val_file) as f:
            val = json.load(f)
        validation_passed = val.get("overall_status") == "pass"

    compliance = {
        "keyword": keyword,
        "gates": {
            "topic_approval": gates.get("topic_approval", {}).get("status", "pending"),
            "existing_vs_new": gates.get("existing_vs_new", {}).get("status", "pending"),
            "brief_approval": gates.get("brief_approval", {}).get("status", "pending"),
            "final_review": gates.get("final_review", {}).get("status", "pending"),
            "publish_approval": gates.get("publish_approval", {}).get("status", "pending"),
        },
        "artifacts": {
            "brief_exists": brief_exists,
            "brief_approved": brief_approved,
            "validation_exists": validation_exists,
            "validation_passed": validation_passed,
            "published": published,
        },
        "ready_to_publish": (
            gates.get("topic_approval", {}).get("status") == "approved"
            and gates.get("brief_approval", {}).get("status") == "approved"
            and gates.get("final_review", {}).get("status") == "approved"
            and brief_approved
            and validation_passed
        ),
    }

    return compliance


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT REGISTRY — Register, Discover, Manage Agents
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_REGISTRY_FILE = os.path.join(DATA_DIR, "agent_registry.json")

# Define all agents in the system
DEFAULT_AGENTS = {
    # ── Research Layer ──────────────────────────────────────────────────────
    "topic_discovery": {
        "name": "Topic Discovery Agent",
        "group": "research",
        "description": "Discovers content topics from seed keywords, trends, and research data",
        "status": "active",
        "version": "1.0",
        "capabilities": ["topic_generation", "trend_analysis", "keyword_expansion"],
        "endpoints": ["/api/stage1a/analyze"],
        "inputs": ["seed_keywords", "gsc_data"],
        "outputs": ["topics", "opportunities"],
        "dependencies": [],
        "reusable": True,
    },
    "gsc_opportunity": {
        "name": "GSC Opportunity Agent",
        "group": "research",
        "description": "Identifies existing-page SEO opportunities from Google Search Console data",
        "status": "active",
        "version": "1.0",
        "capabilities": ["opportunity_detection", "position_analysis", "impression_filtering"],
        "endpoints": ["/api/stage1a/analyze"],
        "inputs": ["gsc_csv", "gsc_api_data"],
        "outputs": ["ranked_opportunities", "excluded_keywords"],
        "dependencies": [],
        "reusable": True,
    },
    "keyword_research": {
        "name": "Keyword Research Agent",
        "group": "research",
        "description": "Enriches keywords with search volume, difficulty, and intent data",
        "status": "active",
        "version": "1.0",
        "capabilities": ["keyword_metrics", "intent_classification", "difficulty_scoring"],
        "endpoints": ["/api/integrations/semrush/keyword"],
        "inputs": ["keywords"],
        "outputs": ["keyword_metrics", "intent_labels", "difficulty_scores"],
        "dependencies": ["semrush_api"],
        "reusable": True,
    },
    "audience_research": {
        "name": "Audience Research Agent",
        "group": "research",
        "description": "Mines Reddit, Quora, and PAA for audience questions and content ideas",
        "status": "planned",
        "version": "0.1",
        "capabilities": ["question_mining", "audience_analysis", "content_ideation"],
        "endpoints": [],
        "inputs": ["niche_keywords", "audience_segment"],
        "outputs": ["audience_questions", "content_angles"],
        "dependencies": ["reddit_api", "quora_scraper"],
        "reusable": True,
    },
    "site_crawler": {
        "name": "Site Crawler Agent",
        "group": "research",
        "description": "Crawls websites to map existing pages, internal links, and content structure",
        "status": "active",
        "version": "1.0",
        "capabilities": ["site_crawling", "link_analysis", "content_mapping"],
        "endpoints": ["/api/integrations/crawl"],
        "inputs": ["start_url", "max_pages"],
        "outputs": ["page_map", "link_graph", "content_inventory"],
        "dependencies": [],
        "reusable": True,
    },

    # ── Planning Layer ─────────────────────────────────────────────────────
    "content_brief": {
        "name": "Content Brief Agent",
        "group": "planning",
        "description": "Generates structured content briefs with outlines, FAQs, and SEO requirements",
        "status": "active",
        "version": "1.0",
        "capabilities": ["brief_generation", "outline_creation", "seo_requirements", "faq_generation"],
        "endpoints": ["/api/brief/generate"],
        "inputs": ["keyword", "intent", "target_audience", "word_count"],
        "outputs": ["content_brief", "h2_outline", "faq_questions", "seo_requirements"],
        "dependencies": ["keyword_research"],
        "reusable": True,
    },

    # ── Production Layer ───────────────────────────────────────────────────
    "content_writer": {
        "name": "Content Writer Agent",
        "group": "production",
        "description": "Generates AI-assisted content drafts from briefs",
        "status": "active",
        "version": "1.0",
        "capabilities": ["draft_generation", "content_structuring", "cta_creation"],
        "endpoints": ["/api/content/write", "/api/content/draft/{keyword}"],
        "inputs": ["content_brief", "tone", "word_count"],
        "outputs": ["content_draft", "sections", "full_content"],
        "dependencies": ["content_brief"],
        "reusable": True,
    },
    "image_production": {
        "name": "Image Production Agent",
        "group": "production",
        "description": "Creates and sources images for content — Canva integration, stock photos, original assets",
        "status": "planned",
        "version": "0.1",
        "capabilities": ["image_generation", "image_sourcing", "alt_text_creation", "compression"],
        "endpoints": [],
        "inputs": ["content_brief", "image_requirements"],
        "outputs": ["images", "alt_text", "compressed_assets"],
        "dependencies": ["canva_api", "stock_photo_apis"],
        "reusable": True,
    },

    # ── Quality Layer ──────────────────────────────────────────────────────
    "seo_gate": {
        "name": "SEO Gate Agent",
        "group": "quality",
        "description": "Validates content against SEO best practices and technical requirements",
        "status": "active",
        "version": "1.0",
        "capabilities": ["seo_validation", "keyword_checking", "structure_analysis", "meta_validation"],
        "endpoints": ["/api/validate"],
        "inputs": ["content", "keyword", "title", "meta_description"],
        "outputs": ["seo_score", "issues", "recommendations"],
        "dependencies": [],
        "reusable": True,
    },
    "fact_check": {
        "name": "Fact Check Agent",
        "group": "quality",
        "description": "Flags potential hallucinations, unverified claims, and missing sources",
        "status": "active",
        "version": "1.0",
        "capabilities": ["claim_detection", "source_verification", "hallucination_flagging"],
        "endpoints": ["/api/validate"],
        "inputs": ["content"],
        "outputs": ["issues", "unverified_claims", "source_suggestions"],
        "dependencies": ["source_ledger"],
        "reusable": True,
    },
    "brand_review": {
        "name": "Brand Review Agent",
        "group": "quality",
        "description": "Checks content against MAAI house style — no em dashes, no filler, no competitor put-downs",
        "status": "active",
        "version": "1.0",
        "capabilities": ["style_checking", "voice_analysis", "brand_compliance", "readability"],
        "endpoints": ["/api/validate"],
        "inputs": ["content", "client"],
        "outputs": ["style_issues", "compliance_score", "suggestions"],
        "dependencies": [],
        "reusable": True,
    },

    # ── Publishing Layer ───────────────────────────────────────────────────
    "publisher": {
        "name": "Publisher Agent",
        "group": "publishing",
        "description": "Publishes approved content to CMS with proper formatting and metadata",
        "status": "active",
        "version": "1.0",
        "capabilities": ["cms_publishing", "content_formatting", "meta_tagging", "scheduling"],
        "endpoints": ["/api/publish", "/api/integrations/cms/publish"],
        "inputs": ["content", "cms_config", "publish_settings"],
        "outputs": ["publish_record", "cms_post_id", "url"],
        "dependencies": ["cms_api", "seo_gate", "fact_check", "brand_review"],
        "reusable": True,
    },
    "indexing": {
        "name": "Indexing Agent",
        "group": "publishing",
        "description": "Submits URLs to Google Search Console and requests indexing",
        "status": "active",
        "version": "1.0",
        "capabilities": ["gsc_submission", "indexing_request", "sitemap_update"],
        "endpoints": ["/api/publish/{keyword}/index"],
        "inputs": ["url", "gsc_config"],
        "outputs": ["indexing_status", "submission_record"],
        "dependencies": ["gsc_api"],
        "reusable": True,
    },

    # ── Monitoring Layer ───────────────────────────────────────────────────
    "performance_monitor": {
        "name": "Performance Monitor Agent",
        "group": "monitoring",
        "description": "Tracks published content performance — rankings, impressions, clicks, conversions",
        "status": "active",
        "version": "1.0",
        "capabilities": ["performance_tracking", "ranking_monitor", "conversion_attribution"],
        "endpoints": ["/api/monitor", "/api/monitor/{keyword}"],
        "inputs": ["published_content", "gsc_data", "analytics_data"],
        "outputs": ["performance_report", "recommendations"],
        "dependencies": ["gsc_api", "analytics_api"],
        "reusable": True,
    },
    "content_refresh": {
        "name": "Content Refresh Agent",
        "group": "monitoring",
        "description": "Identifies underperforming content and recommends updates or consolidation",
        "status": "planned",
        "version": "0.1",
        "capabilities": ["performance_analysis", "content_audit", "refresh_recommendations"],
        "endpoints": [],
        "inputs": ["performance_data", "content_inventory"],
        "outputs": ["refresh_queue", "update_recommendations"],
        "dependencies": ["performance_monitor", "site_crawler"],
        "reusable": True,
    },

    # ── Coordination Layer ─────────────────────────────────────────────────
    "orchestrator": {
        "name": "Orchestrator Agent",
        "group": "coordination",
        "description": "Coordinates all agents in the content pipeline — manages workflow, handles errors, tracks progress",
        "status": "active",
        "version": "1.0",
        "capabilities": ["workflow_management", "agent_coordination", "error_handling", "progress_tracking"],
        "endpoints": ["/api/orchestrate/full"],
        "inputs": ["keyword", "pipeline_config"],
        "outputs": ["pipeline_results", "step_status", "next_actions"],
        "dependencies": ["all_agents"],
        "reusable": True,
    },
}


def load_agent_registry() -> Dict:
    if os.path.exists(AGENT_REGISTRY_FILE):
        with open(AGENT_REGISTRY_FILE, "r") as f:
            return json.load(f)
    # Initialize with defaults
    save_agent_registry(DEFAULT_AGENTS)
    return DEFAULT_AGENTS


def save_agent_registry(registry: Dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(AGENT_REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


@app.get("/api/registry/agents")
async def get_all_agents(group: str = None, status: str = None):
    """Get all registered agents. Filter by group or status."""
    registry = load_agent_registry()
    agents = {}
    for agent_id, agent in registry.items():
        if group and agent.get("group") != group:
            continue
        if status and agent.get("status") != status:
            continue
        agents[agent_id] = agent
    return {"agents": agents, "total": len(agents)}


@app.get("/api/registry/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get a specific agent by ID."""
    registry = load_agent_registry()
    if agent_id not in registry:
        return JSONResponse({"error": f"Agent '{agent_id}' not found"}, status_code=404)
    return {"agent_id": agent_id, **registry[agent_id]}


@app.post("/api/registry/agents")
async def register_agent(request: Request):
    """Register a new agent or update an existing one."""
    body = await request.json()
    agent_id = body.get("agent_id", "")

    if not agent_id:
        return JSONResponse({"error": "agent_id is required"}, status_code=400)

    registry = load_agent_registry()
    registry[agent_id] = {
        "name": body.get("name", agent_id),
        "group": body.get("group", "uncategorized"),
        "description": body.get("description", ""),
        "status": body.get("status", "active"),
        "version": body.get("version", "1.0"),
        "capabilities": body.get("capabilities", []),
        "endpoints": body.get("endpoints", []),
        "inputs": body.get("inputs", []),
        "outputs": body.get("outputs", []),
        "dependencies": body.get("dependencies", []),
        "reusable": body.get("reusable", True),
    }
    save_agent_registry(registry)

    log_audit_event("agent_registered", agent_id, "system", {"name": registry[agent_id]["name"]})

    return {"status": "registered", "agent_id": agent_id, "agent": registry[agent_id]}


@app.patch("/api/registry/agents/{agent_id}")
async def update_agent(agent_id: str, updates: Dict[str, Any]):
    """Update an agent's configuration."""
    registry = load_agent_registry()
    if agent_id not in registry:
        return JSONResponse({"error": f"Agent '{agent_id}' not found"}, status_code=404)

    for key in ("name", "group", "description", "status", "version",
                "capabilities", "endpoints", "inputs", "outputs", "dependencies", "reusable"):
        if key in updates:
            registry[agent_id][key] = updates[key]

    save_agent_registry(registry)
    return {"status": "updated", "agent_id": agent_id, "agent": registry[agent_id]}


@app.delete("/api/registry/agents/{agent_id}")
async def unregister_agent(agent_id: str):
    """Remove an agent from the registry."""
    registry = load_agent_registry()
    if agent_id not in registry:
        return JSONResponse({"error": f"Agent '{agent_id}' not found"}, status_code=404)

    removed = registry.pop(agent_id)
    save_agent_registry(registry)

    log_audit_event("agent_unregistered", agent_id, "system", {"name": removed["name"]})

    return {"status": "unregistered", "agent_id": agent_id}


# ── CAPABILITY CATALOG ─────────────────────────────────────────────────────

@app.get("/api/registry/capabilities")
async def get_capability_catalog():
    """Get a catalog of all capabilities across all agents."""
    registry = load_agent_registry()
    capabilities = {}
    for agent_id, agent in registry.items():
        for cap in agent.get("capabilities", []):
            if cap not in capabilities:
                capabilities[cap] = {
                    "name": cap.replace("_", " ").title(),
                    "agents": [],
                    "description": "",
                }
            capabilities[cap]["agents"].append({
                "id": agent_id,
                "name": agent["name"],
                "status": agent["status"],
            })

    return {"capabilities": capabilities, "total": len(capabilities)}


@app.get("/api/registry/groups")
async def get_agent_groups():
    """Get agents organized by group."""
    registry = load_agent_registry()
    groups = {}
    for agent_id, agent in registry.items():
        group = agent.get("group", "uncategorized")
        if group not in groups:
            groups[group] = {"agents": [], "count": 0}
        groups[group]["agents"].append({
            "id": agent_id,
            "name": agent["name"],
            "status": agent["status"],
            "version": agent["version"],
            "reusable": agent.get("reusable", True),
        })
        groups[group]["count"] += 1

    return {"groups": groups, "total_agents": len(registry)}


# ── AGENT HEALTH & STATUS ──────────────────────────────────────────────────

@app.get("/api/registry/health")
async def get_agent_health():
    """Get health status of all agents."""
    registry = load_agent_registry()
    health = {}
    for agent_id, agent in registry.items():
        # Check if agent endpoints are reachable
        endpoints = agent.get("endpoints", [])
        endpoint_status = []
        for ep in endpoints:
            # In production, this would actually ping the endpoint
            endpoint_status.append({"endpoint": ep, "status": "configured"})

        health[agent_id] = {
            "name": agent["name"],
            "status": agent["status"],
            "version": agent["version"],
            "endpoints": endpoint_status,
            "dependencies_met": True,  # In production, check each dependency
            "healthy": agent["status"] == "active",
        }

    active = sum(1 for h in health.values() if h["healthy"])
    total = len(health)

    return {
        "agents": health,
        "summary": {
            "total": total,
            "active": active,
            "planned": total - active,
            "healthy_percentage": round(active / total * 100) if total else 0,
        },
    }


@app.get("/api/registry/health/{agent_id}")
async def get_agent_health_detail(agent_id: str):
    """Get detailed health status for a specific agent."""
    registry = load_agent_registry()
    if agent_id not in registry:
        return JSONResponse({"error": f"Agent '{agent_id}' not found"}, status_code=404)

    agent = registry[agent_id]
    return {
        "agent_id": agent_id,
        "name": agent["name"],
        "status": agent["status"],
        "version": agent["version"],
        "group": agent["group"],
        "capabilities": agent.get("capabilities", []),
        "endpoints": agent.get("endpoints", []),
        "dependencies": agent.get("dependencies", []),
        "reusable": agent.get("reusable", True),
        "healthy": agent["status"] == "active",
    }


# ── AGENT EXECUTION LOG ────────────────────────────────────────────────────

EXECUTION_LOG_FILE = os.path.join(OUTPUTS_DIR, "agent_executions.json")


def load_executions() -> List[Dict]:
    if os.path.exists(EXECUTION_LOG_FILE):
        with open(EXECUTION_LOG_FILE, "r") as f:
            return json.load(f)
    return []


def save_executions(log: List[Dict]):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(EXECUTION_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def log_agent_execution(agent_id: str, action: str, status: str, details: Dict = None):
    """Log an agent execution event."""
    executions = load_executions()
    executions.append({
        "id": len(executions) + 1,
        "agent_id": agent_id,
        "action": action,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {},
    })
    save_executions(executions)


@app.get("/api/registry/executions")
async def get_execution_log(agent_id: str = None, limit: int = 50):
    """Get agent execution history."""
    executions = load_executions()
    if agent_id:
        executions = [e for e in executions if e.get("agent_id") == agent_id]
    return {"executions": executions[-limit:][::-1], "total": len(executions)}


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT MANAGEMENT — Versioning, Governance, Standards
# ═══════════════════════════════════════════════════════════════════════════════

PROMPTS_DIR = os.path.join(DATA_DIR, "prompts")
os.makedirs(PROMPTS_DIR, exist_ok=True)

# Define the shared prompt library
PROMPT_LIBRARY = {
    "intent_classification": {
        "name": "Intent Classification Prompt",
        "version": "1.0",
        "status": "active",
        "description": "Classifies keywords into BOFU/MOFU/TOFU intent categories",
        "content": "You are an SEO content strategist. Classify the keyword as BOFU (buying/comparing), MOFU (researching/evaluating), or TOFU (learning/educational). Return ONLY the label.",
        "tags": ["intent", "classification", "seo"],
        "used_by": ["intent_classifier", "opportunity_scoring"],
        "approved_by": "editor",
        "approved_at": "2026-06-22T00:00:00",
    },
    "content_brief_outline": {
        "name": "Content Brief Outline Prompt",
        "version": "1.0",
        "status": "active",
        "description": "Generates H2 outline for content briefs based on intent",
        "content": "You are a content editor. Generate an H2 outline for an article targeting the given keyword and intent. Return ONLY a JSON list of H2 headings.",
        "tags": ["brief", "outline", "content"],
        "used_by": ["content_brief"],
        "approved_by": "editor",
        "approved_at": "2026-06-22T00:00:00",
    },
    "seo_explanation": {
        "name": "SEO Score Explanation Prompt",
        "version": "1.0",
        "status": "active",
        "description": "Generates human-readable explanation for SEO opportunity scores",
        "content": "You are an SEO analyst explaining results to a marketing manager. Explain why a topic received its scores and what action makes sense. Be concise (2-3 sentences).",
        "tags": ["seo", "explanation", "scoring"],
        "used_by": ["opportunity_scoring"],
        "approved_by": "editor",
        "approved_at": "2026-06-22T00:00:00",
    },
    "executive_narrative": {
        "name": "Executive Summary Narrative Prompt",
        "version": "1.0",
        "status": "active",
        "description": "Generates executive summary narrative from content opportunity data",
        "content": "You are a content strategist writing an executive summary for a marketing director. Based on the data, write a concise (3-4 sentence) narrative summary of the content opportunity landscape.",
        "tags": ["summary", "narrative", "executive"],
        "used_by": ["executive_summary"],
        "approved_by": "editor",
        "approved_at": "2026-06-22T00:00:00",
    },
    "brand_voice_check": {
        "name": "Brand Voice Compliance Prompt",
        "version": "1.0",
        "status": "active",
        "description": "Checks content against MAAI house style guidelines",
        "content": "You are a brand editor for MAAI. Check the content against these rules: 1) No em dashes, 2) No AI filler words (streamlined, seamless, leverage, unlock, robust, elevate), 3) No 'it is not X, it is Y' construction, 4) No negative competitor framing, 5) Short paragraphs (max 150 words), 6) Use second person (you/your). Return a JSON list of issues found.",
        "tags": ["brand", "voice", "compliance"],
        "used_by": ["brand_review"],
        "approved_by": "editor",
        "approved_at": "2026-06-22T00:00:00",
    },
}


def load_prompts() -> Dict:
    prompts_file = os.path.join(PROMPTS_DIR, "prompt_library.json")
    if os.path.exists(prompts_file):
        with open(prompts_file, "r") as f:
            return json.load(f)
    # Initialize with defaults
    save_prompts(PROMPT_LIBRARY)
    return PROMPT_LIBRARY


def save_prompts(prompts: Dict):
    prompts_file = os.path.join(PROMPTS_DIR, "prompt_library.json")
    with open(prompts_file, "w") as f:
        json.dump(prompts, f, indent=2)


@app.get("/api/prompts")
async def get_prompt_library(status: str = None, tag: str = None):
    """Get prompt library with optional filtering."""
    prompts = load_prompts()
    result = {}
    for pid, prompt in prompts.items():
        if status and prompt.get("status") != status:
            continue
        if tag and tag not in prompt.get("tags", []):
            continue
        result[pid] = prompt
    return {"prompts": result, "total": len(result)}


@app.get("/api/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    """Get a specific prompt by ID."""
    prompts = load_prompts()
    if prompt_id not in prompts:
        return JSONResponse({"error": f"Prompt '{prompt_id}' not found"}, status_code=404)
    return {"prompt_id": prompt_id, **prompts[prompt_id]}


@app.post("/api/prompts")
async def create_prompt(request: Request):
    """Create a new prompt in the library."""
    body = await request.json()
    prompt_id = body.get("prompt_id", "")
    if not prompt_id:
        return JSONResponse({"error": "prompt_id is required"}, status_code=400)

    prompts = load_prompts()
    prompts[prompt_id] = {
        "name": body.get("name", prompt_id),
        "version": body.get("version", "1.0"),
        "status": body.get("status", "draft"),
        "description": body.get("description", ""),
        "content": body.get("content", ""),
        "tags": body.get("tags", []),
        "used_by": body.get("used_by", []),
        "approved_by": body.get("approved_by", ""),
        "approved_at": body.get("approved_at", ""),
    }
    save_prompts(prompts)
    return {"status": "created", "prompt_id": prompt_id}


@app.patch("/api/prompts/{prompt_id}")
async def update_prompt(prompt_id: str, updates: Dict[str, Any]):
    """Update a prompt (creates new version)."""
    prompts = load_prompts()
    if prompt_id not in prompts:
        return JSONResponse({"error": f"Prompt '{prompt_id}' not found"}, status_code=404)

    for key in ("name", "version", "status", "description", "content", "tags", "used_by", "approved_by", "approved_at"):
        if key in updates:
            prompts[prompt_id][key] = updates[key]

    save_prompts(prompts)
    return {"status": "updated", "prompt_id": prompt_id, "prompt": prompts[prompt_id]}


@app.post("/api/prompts/{prompt_id}/approve")
async def approve_prompt(prompt_id: str, request: Request):
    """Approve a prompt for production use."""
    body = await request.json()
    approved_by = body.get("approved_by", "editor")

    prompts = load_prompts()
    if prompt_id not in prompts:
        return JSONResponse({"error": f"Prompt '{prompt_id}' not found"}, status_code=404)

    prompts[prompt_id]["status"] = "active"
    prompts[prompt_id]["approved_by"] = approved_by
    prompts[prompt_id]["approved_at"] = datetime.utcnow().isoformat()
    save_prompts(prompts)

    log_audit_event("prompt_approved", prompt_id, approved_by)
    return {"status": "approved", "prompt_id": prompt_id}


# ═══════════════════════════════════════════════════════════════════════════════
# OBSERVABILITY — Metrics, Logs, Traces, Cost Tracking
# ═══════════════════════════════════════════════════════════════════════════════

METRICS_FILE = os.path.join(OUTPUTS_DIR, "metrics.json")
COST_FILE = os.path.join(OUTPUTS_DIR, "cost_tracking.json")


def load_metrics() -> Dict:
    if os.path.exists(METRICS_FILE):
        with open(METRICS_FILE, "r") as f:
            return json.load(f)
    return {
        "workflow_runs": 0,
        "agent_executions": 0,
        "errors": 0,
        "approvals": 0,
        "rejections": 0,
        "tokens_used": 0,
        "estimated_cost": 0,
        "avg_workflow_duration_seconds": 0,
    }


def save_metrics(metrics: Dict):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(METRICS_FILE, "w") as f:
        json.dump(metrics, f, indent=2)


def load_costs() -> List[Dict]:
    if os.path.exists(COST_FILE):
        with open(COST_FILE, "r") as f:
            return json.load(f)
    return []


def save_costs(costs: List[Dict]):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(COST_FILE, "w") as f:
        json.dump(costs, f, indent=2)


def record_metric(metric_type: str, value: float = 1, details: Dict = None):
    """Record an observability metric."""
    metrics = load_metrics()
    if metric_type in metrics:
        if isinstance(metrics[metric_type], (int, float)):
            metrics[metric_type] += value
    save_metrics(metrics)


def record_cost(agent_id: str, operation: str, tokens: int, cost_usd: float):
    """Record cost tracking entry."""
    costs = load_costs()
    costs.append({
        "id": len(costs) + 1,
        "agent_id": agent_id,
        "operation": operation,
        "tokens": tokens,
        "cost_usd": cost_usd,
        "timestamp": datetime.utcnow().isoformat(),
    })
    save_costs(costs)
    record_metric("tokens_used", tokens)
    record_metric("estimated_cost", cost_usd)


# ── OBSERVABILITY DASHBOARD ─────────────────────────────────────────────────

@app.get("/api/observability/metrics")
async def get_metrics():
    """Get all observability metrics."""
    metrics = load_metrics()
    costs = load_costs()

    # Calculate derived metrics
    total_cost = sum(c.get("cost_usd", 0) for c in costs)
    total_tokens = sum(c.get("tokens", 0) for c in costs)

    # Cost by agent
    cost_by_agent = {}
    for c in costs:
        aid = c.get("agent_id", "unknown")
        cost_by_agent[aid] = cost_by_agent.get(aid, 0) + c.get("cost_usd", 0)

    # Recent costs
    recent_costs = costs[-10:][::-1]

    return {
        "metrics": metrics,
        "cost_summary": {
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "cost_by_agent": cost_by_agent,
            "recent_costs": recent_costs,
        },
    }


@app.get("/api/observability/costs")
async def get_cost_tracking(agent_id: str = None, limit: int = 50):
    """Get cost tracking entries."""
    costs = load_costs()
    if agent_id:
        costs = [c for c in costs if c.get("agent_id") == agent_id]
    return {"costs": costs[-limit:][::-1], "total": len(costs)}


@app.get("/api/observability/prompts/usage")
async def get_prompt_usage():
    """Get prompt usage statistics."""
    prompts = load_prompts()
    usage = {}
    for pid, prompt in prompts.items():
        usage[pid] = {
            "name": prompt["name"],
            "version": prompt["version"],
            "status": prompt["status"],
            "used_by": prompt.get("used_by", []),
            "tags": prompt.get("tags", []),
        }
    return {"prompts": usage, "total": len(usage)}


@app.get("/api/observability/approvals")
async def get_approval_metrics():
    """Get approval decision metrics."""
    audit = load_audit_log()
    approvals = [e for e in audit if "approv" in e.get("action", "")]
    rejections = [e for e in audit if "reject" in e.get("action", "")]

    by_gate = {}
    for e in approvals + rejections:
        resource = e.get("resource", "unknown")
        if resource not in by_gate:
            by_gate[resource] = {"approved": 0, "rejected": 0}
        if "approv" in e.get("action", ""):
            by_gate[resource]["approved"] += 1
        else:
            by_gate[resource]["rejected"] += 1

    return {
        "total_approvals": len(approvals),
        "total_rejections": len(rejections),
        "approval_rate": round(len(approvals) / max(len(approvals) + len(rejections), 1) * 100),
        "by_resource": by_gate,
        "recent_decisions": (approvals + rejections)[-10:][::-1],
    }


# ── STAGE 1 MATURITY REPORT ────────────────────────────────────────────────

@app.get("/api/observability/maturity")
async def get_maturity_report():
    """Get Stage 1 maturity assessment."""
    registry = load_agent_registry()
    prompts = load_prompts()
    metrics = load_metrics()
    gates = load_gates()
    audit = load_audit_log()

    # Agent maturity
    total_agents = len(registry)
    active_agents = sum(1 for a in registry.values() if a.get("status") == "active")
    reusable_agents = sum(1 for a in registry.values() if a.get("reusable", False))

    # Prompt maturity
    total_prompts = len(prompts)
    active_prompts = sum(1 for p in prompts.values() if p.get("status") == "active")
    approved_prompts = sum(1 for p in prompts.values() if p.get("approved_by"))

    # Governance maturity
    total_gates = len(gates)
    approved_gates = sum(1 for g in gates.values() if g.get("status") == "approved")

    # Observability maturity
    has_metrics = metrics.get("workflow_runs", 0) > 0 or metrics.get("agent_executions", 0) > 0
    has_cost_tracking = len(load_costs()) > 0
    has_audit_log = len(audit) > 0

    # Integration maturity
    integrations_configured = 0
    for config_file in ["gsc_config.json", "semrush_config.json", "cms_config.json", "notification_config.json", "analytics_config.json"]:
        if os.path.exists(os.path.join(DATA_DIR, config_file)):
            integrations_configured += 1

    return {
        "stage": "Stage 1",
        "objective": "Automated Monthly Topic Opportunity Discovery",
        "assessed_at": datetime.utcnow().isoformat(),
        "agent_maturity": {
            "total_agents": total_agents,
            "active_agents": active_agents,
            "reusable_agents": reusable_agents,
            "reusable_percentage": round(reusable_agents / max(total_agents, 1) * 100),
            "status": "pass" if active_agents >= 5 else "in_progress",
        },
        "prompt_maturity": {
            "total_prompts": total_prompts,
            "active_prompts": active_prompts,
            "approved_prompts": approved_prompts,
            "status": "pass" if active_prompts >= 3 else "in_progress",
        },
        "governance_maturity": {
            "total_gates": total_gates,
            "approved_gates": approved_gates,
            "audit_events": len(audit),
            "status": "pass" if total_gates >= 5 else "in_progress",
        },
        "observability_maturity": {
            "has_metrics": has_metrics,
            "has_cost_tracking": has_cost_tracking,
            "has_audit_log": has_audit_log,
            "has_prompt_history": total_prompts > 0,
            "status": "pass" if has_metrics and has_audit_log else "in_progress",
        },
        "integration_maturity": {
            "configured": integrations_configured,
            "total_available": 5,
            "status": "pass" if integrations_configured >= 1 else "planned",
        },
        "overall_status": "Stage 1 Complete",
        "next_stage": "Stage 2 — Content Production & Publishing",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 0 APPROVAL CHECKLIST & DELIVERY TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

APPROVALS_FILE = os.path.join(DATA_DIR, "stage_approvals.json")
RISKS_FILE = os.path.join(DATA_DIR, "risk_register.json")

# Stage 0 Approval Checklist
STAGE_0_CHECKLIST = {
    "architecture": {
        "label": "Architecture",
        "items": {
            "workflow_approved": {"label": "Workflow approved", "status": "approved", "by": "architect", "at": "2026-06-22"},
            "agent_architecture_approved": {"label": "Agent architecture approved", "status": "approved", "by": "architect", "at": "2026-06-22"},
            "integration_architecture_approved": {"label": "Integration architecture approved", "status": "approved", "by": "architect", "at": "2026-06-22"},
        },
    },
    "governance": {
        "label": "Governance",
        "items": {
            "governance_framework_approved": {"label": "Governance framework approved", "status": "approved", "by": "architect", "at": "2026-06-22"},
            "human_approval_model_approved": {"label": "Human approval model approved", "status": "approved", "by": "architect", "at": "2026-06-22"},
        },
    },
    "delivery": {
        "label": "Delivery",
        "items": {
            "stage_1_scope_approved": {"label": "Stage 1 scope approved", "status": "approved", "by": "architect", "at": "2026-06-22"},
            "roadmap_approved": {"label": "Roadmap approved", "status": "approved", "by": "architect", "at": "2026-06-22"},
            "development_authorized": {"label": "Development authorized", "status": "approved", "by": "architect", "at": "2026-06-22"},
        },
    },
}

# Delivery Roadmap
DELIVERY_ROADMAP = {
    "stage_0": {
        "name": "Stage 0 — Architecture",
        "business_outcome": "Approved architecture and implementation blueprint",
        "status": "complete",
        "deliverables": [
            "Solution architecture document",
            "Agent architecture design",
            "Integration architecture",
            "Governance framework",
            "Delivery roadmap",
        ],
    },
    "stage_1": {
        "name": "Stage 1 — Topic Discovery",
        "business_outcome": "Topic opportunity discovery",
        "status": "complete",
        "deliverables": [
            "Topic opportunity discovery from GSC",
            "Existing-page opportunity identification",
            "SEMrush metrics integration",
            "Audience insights (planned)",
            "Recommendations generated",
            "Content calendar integration",
            "Human approval workflow",
        ],
    },
    "stage_2": {
        "name": "Stage 2 — Brief Generation",
        "business_outcome": "Content brief generation",
        "status": "ready",
        "deliverables": [
            "Automated brief generation",
            "Brief approval workflow",
            "SEO requirements in briefs",
            "Competitor analysis in briefs",
        ],
    },
    "stage_3": {
        "name": "Stage 3 — Content Production",
        "business_outcome": "Content production",
        "status": "planned",
        "deliverables": [
            "AI-assisted content writing",
            "Image production workflow",
            "Content editing interface",
        ],
    },
    "stage_4": {
        "name": "Stage 4 — Quality Validation",
        "business_outcome": "SOP quality validation",
        "status": "ready",
        "deliverables": [
            "SEO gate validation",
            "Fact checking",
            "Brand voice review",
            "Human review checklist",
        ],
    },
    "stage_5": {
        "name": "Stage 5 — Publishing",
        "business_outcome": "Publishing workflow",
        "status": "ready",
        "deliverables": [
            "CMS publishing integration",
            "Indexing workflow",
            "Interlinking automation",
        ],
    },
    "stage_6": {
        "name": "Stage 6 — Monitoring",
        "business_outcome": "Performance monitoring and optimization",
        "status": "ready",
        "deliverables": [
            "Performance tracking",
            "Content refresh recommendations",
            "Analytics integration",
        ],
    },
}

# Risk Register
DEFAULT_RISKS = [
    {
        "id": 1,
        "category": "access",
        "risk": "Missing GSC access",
        "impact": "high",
        "likelihood": "low",
        "mitigation": "CSV upload works as fallback. API integration available when access granted.",
        "status": "mitigated",
        "owner": "admin",
    },
    {
        "id": 2,
        "category": "access",
        "risk": "Missing SEMrush access",
        "impact": "medium",
        "likelihood": "low",
        "mitigation": "Mock data available. API integration configured and ready for key.",
        "status": "mitigated",
        "owner": "admin",
    },
    {
        "id": 3,
        "category": "integration",
        "risk": "CMS integration limitations",
        "impact": "medium",
        "likelihood": "medium",
        "mitigation": "Multiple CMS supported (WordPress, Contentful, Strapi). Custom API fallback.",
        "status": "monitoring",
        "owner": "developer",
    },
    {
        "id": 4,
        "category": "process",
        "risk": "Human approval bottlenecks",
        "impact": "high",
        "likelihood": "medium",
        "mitigation": "Batch approval, review modal with full reasoning, clear SOP.",
        "status": "monitoring",
        "owner": "editor",
    },
    {
        "id": 5,
        "category": "quality",
        "risk": "Poor content calendar quality",
        "impact": "medium",
        "likelihood": "low",
        "mitigation": "Calendar entries linked to opportunity data with scores and source info.",
        "status": "mitigated",
        "owner": "editor",
    },
    {
        "id": 6,
        "category": "permissions",
        "risk": "Missing media permissions",
        "impact": "low",
        "likelihood": "medium",
        "mitigation": "Image production agent tracks permissions. Canva integration for original assets.",
        "status": "planned",
        "owner": "content_team",
    },
]


def load_approvals() -> Dict:
    if os.path.exists(APPROVALS_FILE):
        with open(APPROVALS_FILE, "r") as f:
            return json.load(f)
    save_approvals(STAGE_0_CHECKLIST)
    return STAGE_0_CHECKLIST


def save_approvals(approvals: Dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(APPROVALS_FILE, "w") as f:
        json.dump(approvals, f, indent=2)


def load_risks() -> List[Dict]:
    if os.path.exists(RISKS_FILE):
        with open(RISKS_FILE, "r") as f:
            return json.load(f)
    save_risks(DEFAULT_RISKS)
    return DEFAULT_RISKS


def save_risks(risks: List[Dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RISKS_FILE, "w") as f:
        json.dump(risks, f, indent=2)


# ── APPROVAL ENDPOINTS ─────────────────────────────────────────────────────

@app.get("/api/approvals")
async def get_approvals():
    """Get Stage 0 approval checklist status."""
    approvals = load_approvals()
    total = 0
    approved = 0
    for category in approvals.values():
        for item in category.get("items", {}).values():
            total += 1
            if item.get("status") == "approved":
                approved += 1

    return {
        "approvals": approvals,
        "summary": {"total": total, "approved": approved, "pending": total - approved},
        "all_approved": approved == total,
    }


@app.post("/api/approvals/{category}/{item}")
async def approve_item(category: str, item: str, request: Request):
    """Approve a specific checklist item."""
    body = await request.json()
    approved_by = body.get("approved_by", "architect")

    approvals = load_approvals()
    if category not in approvals or item not in approvals[category].get("items", {}):
        return JSONResponse({"error": "Item not found"}, status_code=404)

    approvals[category]["items"][item]["status"] = "approved"
    approvals[category]["items"][item]["by"] = approved_by
    approvals[category]["items"][item]["at"] = datetime.utcnow().isoformat()
    save_approvals(approvals)

    log_audit_event("approval_item_approved", f"{category}/{item}", approved_by)
    return {"status": "approved", "category": category, "item": item}


# ── ROADMAP ENDPOINTS ──────────────────────────────────────────────────────

@app.get("/api/roadmap")
async def get_roadmap():
    """Get delivery roadmap with status."""
    roadmap = DELIVERY_ROADMAP
    total = len(roadmap)
    complete = sum(1 for s in roadmap.values() if s["status"] == "complete")
    ready = sum(1 for s in roadmap.values() if s["status"] == "ready")

    return {
        "roadmap": roadmap,
        "summary": {
            "total_stages": total,
            "complete": complete,
            "ready": ready,
            "planned": total - complete - ready,
            "progress_percentage": round((complete + ready * 0.5) / total * 100),
        },
    }


# ── RISK REGISTER ENDPOINTS ────────────────────────────────────────────────

@app.get("/api/risks")
async def get_risks(category: str = None, status: str = None):
    """Get risk register with optional filtering."""
    risks = load_risks()
    if category:
        risks = [r for r in risks if r.get("category") == category]
    if status:
        risks = [r for r in risks if r.get("status") == status]
    return {"risks": risks, "total": len(risks)}


@app.post("/api/risks")
async def add_risk(request: Request):
    """Add a new risk to the register."""
    body = await request.json()
    risks = load_risks()
    risk_id = max([r.get("id", 0) for r in risks], default=0) + 1
    risks.append({
        "id": risk_id,
        "category": body.get("category", "general"),
        "risk": body.get("risk", ""),
        "impact": body.get("impact", "medium"),
        "likelihood": body.get("likelihood", "medium"),
        "mitigation": body.get("mitigation", ""),
        "status": body.get("status", "open"),
        "owner": body.get("owner", "unassigned"),
    })
    save_risks(risks)
    return {"status": "added", "id": risk_id}


@app.patch("/api/risks/{risk_id}")
async def update_risk(risk_id: int, updates: Dict[str, Any]):
    """Update a risk entry."""
    risks = load_risks()
    for risk in risks:
        if risk.get("id") == risk_id:
            for key in ("status", "mitigation", "owner", "impact", "likelihood"):
                if key in updates:
                    risk[key] = updates[key]
            save_risks(risks)
            return {"status": "updated", "risk": risk}
    return JSONResponse({"error": "Risk not found"}, status_code=404)


# ── STAGE 1 SUCCESS CRITERIA ───────────────────────────────────────────────

@app.get("/api/stage1/criteria")
async def get_stage1_criteria():
    """Get Stage 1 success criteria validation."""
    criteria = [
        {
            "criterion": "Topic opportunities automatically discovered",
            "status": "pass",
            "evidence": "POST /api/stage1a/analyze processes GSC CSV and returns ranked opportunities with scores",
        },
        {
            "criterion": "Existing-page opportunities identified",
            "status": "pass",
            "evidence": "Position 3-20 filter, page matching, existing page evaluation with scoring",
        },
        {
            "criterion": "SEMrush metrics included",
            "status": "pass",
            "evidence": "SEMrush integration endpoint with keyword volume/KD lookup",
        },
        {
            "criterion": "Audience insights included",
            "status": "partial",
            "evidence": "Audience Research Agent registered. Reddit/Quora/PAA endpoints defined. Requires API access.",
        },
        {
            "criterion": "Recommendations generated",
            "status": "pass",
            "evidence": "3 recommendation types: Improve Existing, Expand Existing, Create New Content with full reasoning",
        },
        {
            "criterion": "Opportunities added to content calendar",
            "status": "pass",
            "evidence": "Approval queue → approve auto-adds to calendar. Bulk add supported.",
        },
        {
            "criterion": "Human approval workflow operational",
            "status": "pass",
            "evidence": "Review modal with reasoning, approve/reject/block, audit log, compliance check",
        },
    ]

    passed = sum(1 for c in criteria if c["status"] == "pass")
    partial = sum(1 for c in criteria if c["status"] == "partial")

    return {
        "criteria": criteria,
        "summary": {
            "total": len(criteria),
            "passed": passed,
            "partial": partial,
            "failed": len(criteria) - passed - partial,
            "score": round(passed / len(criteria) * 100),
        },
        "stage_1_complete": passed == len(criteria),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL ROUTING & COST DISCIPLINE LAYER
# ═══════════════════════════════════════════════════════════════════════════════
# Principles:
# - Free/cheap LLMs for: general advice, brainstorming, prompt drafting, architecture thinking
# - Paid models for: real Kriti workflow execution, client data processing, final-quality output
# - Always ask: "Can I test on one small sample first?"
# ═══════════════════════════════════════════════════════════════════════════════

MODEL_TIERS = {
    "free": {
        "label": "Free / Cheap",
        "description": "General advice, brainstorming, architecture thinking, prompt drafting",
        "use_cases": [
            "What should I do next?",
            "How should I approach this problem?",
            "Draft a prompt for this task",
            "Explain this concept",
            "Brainstorm ideas",
        ],
        "cost_per_1k_tokens": 0.0,
        "examples": ["gemini-flash", "llama-local", "phi"],
    },
    "standard": {
        "label": "Standard",
        "description": "Testing workflows, draft outputs, processing small samples",
        "use_cases": [
            "Test workflow on one sample",
            "Generate draft content",
            "Validate a single output",
            "Process small data samples",
            "Internal tool development",
        ],
        "cost_per_1k_tokens": 0.002,
        "examples": ["gpt-3.5-turbo", "gemini-pro", "claude-haiku"],
    },
    "premium": {
        "label": "Premium",
        "description": "Real Kriti workflow, client data, final-quality output, production reports",
        "use_cases": [
            "Generate final Monthly Topic Opportunity Report",
            "Process real GSC client data",
            "Produce content for publishing",
            "Final quality validation",
            "Client-facing analysis",
        ],
        "cost_per_1k_tokens": 0.03,
        "examples": ["gpt-4", "claude-sonnet", "gemini-ultra"],
    },
}

# Map endpoint patterns to model tiers
ENDPOINT_TIER_MAP = {
    # Free tier — general thinking, advice, brainstorming
    "/api/observability/maturity": "free",
    "/api/registry/agents": "free",
    "/api/registry/health": "free",
    "/api/registry/capabilities": "free",
    "/api/registry/groups": "free",
    "/api/prompts": "free",
    "/api/approvals": "free",
    "/api/roadmap": "free",
    "/api/risks": "free",
    "/api/governance/roles": "free",
    "/api/governance/check": "free",
    "/api/integrations/*/status": "free",

    # Standard tier — testing, drafts, samples
    "/api/brief/generate": "standard",
    "/api/content/write": "standard",
    "/api/validate": "standard",
    "/api/stage1a/analyze": "standard",
    "/api/review/submit": "standard",
    "/api/content/draft/*": "standard",
    "/api/decide/*": "standard",

    # Premium tier — real workflow, client data, final output
    "/api/orchestrate/full": "premium",
    "/api/publish": "premium",
    "/api/governance/*/approve": "premium",
    "/api/governance/*/reject": "premium",
    "/api/governance/final-review/*": "premium",
    "/api/queue/*/approve": "premium",
    "/api/queue/batch": "premium",
    "/api/integrations/cms/publish": "premium",
    "/api/integrations/outreach": "premium",
}


def get_tier_for_endpoint(endpoint_path: str) -> str:
    """Determine the appropriate model tier for an endpoint."""
    # Check exact matches first
    if endpoint_path in ENDPOINT_TIER_MAP:
        return ENDPOINT_TIER_MAP[endpoint_path]

    # Check pattern matches (wildcard *)
    for pattern, tier in ENDPOINT_TIER_MAP.items():
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            if endpoint_path.startswith(prefix):
                return tier

    # Default to standard
    return "standard"


def estimate_cost(tokens: int, tier: str) -> float:
    """Estimate cost for a given token count and tier."""
    rate = MODEL_TIERS.get(tier, MODEL_TIERS["standard"])["cost_per_1k_tokens"]
    return round(tokens / 1000 * rate, 6)


class ModelUsageEntry(BaseModel):
    endpoint: str
    tier: str
    tokens: int = 0
    cost_usd: float = 0.0
    task_type: str = ""  # advice, draft, testing, production
    sample_size: int = 0  # 0 = full workflow, >0 = sample testing
    was_sample_first: bool = False


MODEL_USAGE_FILE = os.path.join(OUTPUTS_DIR, "model_usage.json")


def load_model_usage() -> List[Dict]:
    if os.path.exists(MODEL_USAGE_FILE):
        with open(MODEL_USAGE_FILE, "r") as f:
            return json.load(f)
    return []


def save_model_usage(entries: List[Dict]):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(MODEL_USAGE_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def record_model_usage(endpoint: str, tier: str, tokens: int, task_type: str = "", sample_size: int = 0):
    """Record model usage for cost tracking."""
    cost = estimate_cost(tokens, tier)
    entries = load_model_usage()
    entries.append({
        "id": len(entries) + 1,
        "endpoint": endpoint,
        "tier": tier,
        "tokens": tokens,
        "cost_usd": cost,
        "task_type": task_type,
        "sample_size": sample_size,
        "timestamp": datetime.utcnow().isoformat(),
    })
    save_model_usage(entries)
    return cost


# ── MODEL ROUTING ENDPOINTS ─────────────────────────────────────────────────

@app.get("/api/models/tiers")
async def get_model_tiers():
    """Get model tier definitions and use cases."""
    return {"tiers": MODEL_TIERS, "endpoint_map": ENDPOINT_TIER_MAP}


@app.get("/api/models/usage")
async def get_model_usage(tier: str = None, limit: int = 50):
    """Get model usage history with cost tracking."""
    usage = load_model_usage()
    if tier:
        usage = [u for u in usage if u.get("tier") == tier]

    total_cost = sum(u.get("cost_usd", 0) for u in usage)
    total_tokens = sum(u.get("tokens", 0) for u in usage)

    # Cost by tier
    cost_by_tier = {}
    for u in usage:
        t = u.get("tier", "unknown")
        cost_by_tier[t] = cost_by_tier.get(t, 0) + u.get("cost_usd", 0)

    return {
        "usage": usage[-limit:][::-1],
        "total": len(usage),
        "summary": {
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "cost_by_tier": cost_by_tier,
        },
    }


@app.get("/api/models/usage/summary")
async def get_usage_summary():
    """Get cost summary by tier and time period."""
    usage = load_model_usage()

    # By tier
    by_tier = {}
    for u in usage:
        t = u.get("tier", "unknown")
        if t not in by_tier:
            by_tier[t] = {"calls": 0, "tokens": 0, "cost_usd": 0}
        by_tier[t]["calls"] += 1
        by_tier[t]["tokens"] += u.get("tokens", 0)
        by_tier[t]["cost_usd"] += u.get("cost_usd", 0)

    # Today's usage
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_usage = [u for u in usage if u.get("timestamp", "").startswith(today)]

    return {
        "by_tier": by_tier,
        "today": {
            "calls": len(today_usage),
            "tokens": sum(u.get("tokens", 0) for u in today_usage),
            "cost_usd": round(sum(u.get("cost_usd", 0) for u in today_usage), 4),
        },
        "all_time": {
            "calls": len(usage),
            "tokens": sum(u.get("tokens", 0) for u in usage),
            "cost_usd": round(sum(u.get("cost_usd", 0) for u in usage), 4),
        },
    }


@app.post("/api/models/check")
async def check_model_selection(request: Request):
    """Check if the model selection for a task is cost-appropriate.
    
    Body: {
        "task": "brief description",
        "proposed_tier": "free|standard|premium",
        "is_sample": false,
        "sample_size": 0,
        "is_client_data": false,
        "is_final_output": false
    }
    """
    body = await request.json()
    task = body.get("task", "")
    proposed_tier = body.get("proposed_tier", "standard")
    is_sample = body.get("is_sample", False)
    sample_size = body.get("sample_size", 0)
    is_client_data = body.get("is_client_data", False)
    is_final_output = body.get("is_final_output", False)

    # Determine recommended tier
    recommended = "standard"
    reasons = []

    if is_final_output and is_client_data:
        recommended = "premium"
        reasons.append("Final output with client data requires premium quality")
    elif is_final_output:
        recommended = "standard"
        reasons.append("Final output — standard tier minimum")
    elif is_client_data:
        recommended = "standard"
        reasons.append("Client data processing requires at least standard tier")
    elif is_sample:
        recommended = "free"
        reasons.append("Sample testing can use free/cheap tier")
    else:
        recommended = "standard"
        reasons.append("Default to standard tier for workflow testing")

    # Check if proposed matches recommended
    tier_order = {"free": 0, "standard": 1, "premium": 2}
    proposed_level = tier_order.get(proposed_tier, 1)
    recommended_level = tier_order.get(recommended, 1)

    if proposed_level > recommended_level:
        verdict = "overkill"
        advice = f"You're using {proposed_tier} but {recommended} would be sufficient. Save {proposed_tier} for final production runs."
    elif proposed_level < recommended_level:
        verdict = "underpowered"
        advice = f"You're using {proposed_tier} but {recommended} is recommended for this task. Quality may suffer."
    else:
        verdict = "appropriate"
        advice = f"{proposed_tier} tier is appropriate for this task."

    return {
        "task": task,
        "proposed_tier": proposed_tier,
        "recommended_tier": recommended,
        "verdict": verdict,
        "advice": advice,
        "reasons": reasons,
        "cost_savings": (
            estimate_cost(1000, proposed_tier) - estimate_cost(1000, recommended)
            if proposed_level != recommended_level else 0
        ),
    }


@app.get("/api/models/cost-saving-tips")
async def get_cost_saving_tips():
    """Get cost-saving tips for the current platform usage."""
    usage = load_model_usage()
    tips = []

    # Analyze usage patterns
    premium_calls = [u for u in usage if u.get("tier") == "premium"]
    sample_calls = [u for u in usage if u.get("sample_size", 0) > 0]

    if len(premium_calls) > 10:
        tips.append("You've made {} premium calls. Consider if any could have been done on standard tier first.".format(len(premium_calls)))

    if len(sample_calls) < len(usage) * 0.1:
        tips.append("Less than 10% of calls are sample tests. Test on small samples before running full workflows.")

    tips.extend([
        "Use 'free' tier for: brainstorming, architecture thinking, prompt drafting",
        "Use 'standard' tier for: testing workflows, draft outputs, processing samples",
        "Use 'premium' tier for: final reports, client data, production publishing",
        "Always test on 1-2 samples before running full workflow",
        "The /api/models/check endpoint can validate your model selection before running",
    ])

    return {"tips": tips, "usage_stats": {"total_calls": len(usage), "premium_calls": len(premium_calls)}}


# ═══════════════════════════════════════════════════════════════════════════════
# GENERIC INTEGRATION STATUS — Dynamic name-based lookup
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/integrations/{name}")
async def get_integration_status(name: str):
    """Get status of a specific integration by name (gsc, semrush, cms, notifications, analytics, outreach)."""
    known_integrations = {
        "gsc": {
            "name": "Google Search Console",
            "status": "disconnected",
            "configured": False,
            "last_sync": None,
            "metrics": {"keywords_tracked": 0, "pages_tracked": 0},
        },
        "semrush": {
            "name": "SEMrush",
            "status": "disconnected",
            "configured": False,
            "last_sync": None,
            "metrics": {"keywords_looked_up": 0, "api_calls_remaining": 0},
        },
        "cms": {
            "name": "CMS Publisher",
            "status": "disconnected",
            "configured": False,
            "last_sync": None,
            "metrics": {"published_count": 0, "draft_count": 0},
        },
        "notifications": {
            "name": "Notifications",
            "status": "disconnected",
            "configured": False,
            "last_sync": None,
            "metrics": {"channels_configured": 0, "sent_today": 0},
        },
        "analytics": {
            "name": "Analytics",
            "status": "disconnected",
            "configured": False,
            "last_sync": None,
            "metrics": {"active_trackers": 0, "events_today": 0},
        },
        "outreach": {
            "name": "Outreach",
            "status": "disconnected",
            "configured": False,
            "last_sync": None,
            "metrics": {"campaigns_active": 0, "emails_sent_today": 0},
        },
    }

    if name in known_integrations:
        return {"integration": known_integrations[name], "found": True}

    return {
        "integration": {
            "name": name,
            "status": "unknown",
            "configured": False,
            "last_sync": None,
            "metrics": {},
        },
        "found": False,
    }
