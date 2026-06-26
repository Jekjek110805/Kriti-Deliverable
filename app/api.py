"""
Kriti — GSC Opportunity Finder
FastAPI backend. Entry point for Cloud Run.
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
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from datetime import datetime

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Kriti — GSC Opportunity Finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── GSC file parsing ──────────────────────────────────────────────────────────

GSC_HEADER_ALIASES: Dict[str, str] = {
    "query": "query", "queries": "query", "top queries": "query",
    "search query": "query", "keyword": "query", "term": "query",
    "page": "page", "pages": "page", "top pages": "page",
    "url": "page", "landing page": "page", "address": "page",
    "click": "clicks", "clicks": "clicks",
    "impression": "impressions", "impressions": "impressions", "imps": "impressions",
    "ctr": "ctr", "click-through rate": "ctr", "click through rate": "ctr",
    "position": "position", "pos": "position",
    "avg position": "position", "average position": "position",
}

XLSX_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
XLSX_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
XLSX_DOC_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _norm_header(h: Any) -> str:
    clean = str(h or "").replace("﻿", "").strip().lower()
    clean = re.sub(r"\s+", " ", clean)
    return GSC_HEADER_ALIASES.get(clean, clean)


def _norm_row(row: Dict) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in row.items():
        h = _norm_header(k)
        if h:
            out[h] = "" if v is None else str(v).strip()
    return out


def _headers_ok(headers: List[str]) -> bool:
    s = {_norm_header(h) for h in headers if h}
    return "query" in s and bool(s & {"clicks", "impressions", "position"})


def _parse_csv(content: bytes) -> List[Dict[str, str]]:
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Could not decode CSV. Upload UTF-8 CSV or .xlsx.")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    rows: List[Dict[str, str]] = []
    for section in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in section.split("\n") if l.strip()]
        if not lines:
            continue
        delim = "\t" if "\t" in lines[0] and lines[0].count("\t") >= lines[0].count(",") else ","
        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delim)
        if not reader.fieldnames or not _headers_ok(reader.fieldnames):
            continue
        for row in reader:
            n = _norm_row(row)
            if n.get("query") and any(v for v in n.values()):
                rows.append(n)
    return rows


def _xlsx_col(ref: str) -> int:
    m = re.match(r"([A-Z]+)", ref.upper())
    if not m:
        return 0
    i = 0
    for c in m.group(1):
        i = i * 26 + (ord(c) - ord("A") + 1)
    return i - 1


def _shared_strings(wb: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in wb.namelist():
        return []
    root = ET.fromstring(wb.read("xl/sharedStrings.xml"))
    return ["".join(n.text or "" for n in si.findall(f".//{XLSX_MAIN_NS}t"))
            for si in root.findall(f"{XLSX_MAIN_NS}si")]


def _read_cell(cell: ET.Element, shared: List[str]) -> str:
    t = cell.attrib.get("t")
    if t == "inlineStr":
        return "".join(n.text or "" for n in cell.findall(f".//{XLSX_MAIN_NS}t")).strip()
    v = cell.find(f"{XLSX_MAIN_NS}v")
    raw = v.text if v is not None and v.text else ""
    if t == "s" and raw:
        try:
            return shared[int(raw)].strip()
        except (IndexError, ValueError):
            return ""
    return raw.strip()


def _sheet_paths(wb: zipfile.ZipFile) -> List[Dict[str, str]]:
    wb_root = ET.fromstring(wb.read("xl/workbook.xml"))
    rels_root = ET.fromstring(wb.read("xl/_rels/workbook.xml.rels"))
    rels: Dict[str, str] = {}
    for rel in rels_root.findall(f"{XLSX_REL_NS}Relationship"):
        t = rel.attrib.get("Target", "")
        path = t.lstrip("/") if t.startswith("/") else posixpath.normpath(posixpath.join("xl", t))
        rels[rel.attrib.get("Id", "")] = path
    sheets = []
    for sheet in wb_root.findall(f".//{XLSX_MAIN_NS}sheet"):
        rid = sheet.attrib.get(f"{XLSX_DOC_REL_NS}id")
        if rid in rels:
            sheets.append({"name": sheet.attrib.get("name", ""), "path": rels[rid]})
    return sheets


def _read_grid(wb: zipfile.ZipFile, path: str, shared: List[str]) -> List[List[str]]:
    root = ET.fromstring(wb.read(path))
    grid: List[List[str]] = []
    for row in root.findall(f".//{XLSX_MAIN_NS}row"):
        vals: List[str] = []
        for cell in row.findall(f"{XLSX_MAIN_NS}c"):
            idx = _xlsx_col(cell.attrib.get("r", "A1"))
            while len(vals) <= idx:
                vals.append("")
            vals[idx] = _read_cell(cell, shared)
        if any(vals):
            grid.append(vals)
    return grid


def _rows_from_grid(grid: List[List[str]]) -> List[Dict[str, str]]:
    for hi, header_row in enumerate(grid[:20]):
        headers = [_norm_header(v) for v in header_row]
        if not _headers_ok(headers):
            continue
        rows: List[Dict[str, str]] = []
        for data_row in grid[hi + 1:]:
            raw = {headers[i]: data_row[i] if i < len(data_row) else ""
                   for i, h in enumerate(headers) if h}
            n = _norm_row(raw)
            if n.get("query") and any(v for v in n.values()):
                rows.append(n)
        return rows
    return []


def _parse_xlsx(content: bytes) -> List[Dict[str, str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as wb:
            shared = _shared_strings(wb)
            sheets = _sheet_paths(wb)
            sheets.sort(key=lambda s: (
                0 if s["name"].lower() == "queries" else
                1 if "query" in s["name"].lower() else 2
            ))
            for sheet in sheets:
                grid = _read_grid(wb, sheet["path"], shared)
                rows = _rows_from_grid(grid)
                if rows:
                    return rows
    except zipfile.BadZipFile as e:
        raise ValueError("Not a valid .xlsx file. Upload CSV or .xlsx.") from e
    except KeyError as e:
        raise ValueError("XLSX is missing worksheet data. Re-export from GSC.") from e
    return []


def parse_upload(content: bytes, filename: str = "") -> List[Dict[str, str]]:
    fn = (filename or "").lower()
    if fn.endswith(".xls") and not fn.endswith(".xlsx"):
        raise ValueError("Old .xls not supported. Save as .xlsx or CSV.")
    if fn.endswith(".xlsx") or content.startswith(b"PK\x03\x04"):
        return _parse_xlsx(content)
    return _parse_csv(content)


# ── Job queue ─────────────────────────────────────────────────────────────────

from jobs import create_job, run_job_analysis, get_job, list_recent_jobs

# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def root():
    idx = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(idx):
        with open(idx, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Kriti — GSC Opportunity Finder</h1><p>Backend is running.</p>")


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/stage1a/analyze")
async def analyze(file: UploadFile = File(...)):
    """Upload a GSC CSV or XLSX → run analysis → return job ID to poll."""
    try:
        content = await file.read()
        rows = parse_upload(content, file.filename or "")
        if not rows:
            return JSONResponse({
                "error": "No GSC data found. Upload a CSV or XLSX with query/clicks/impressions/position columns."
            }, status_code=400)
        job_id = create_job(rows)
        asyncio.create_task(run_job_analysis(job_id))
        return {
            "status": "queued",
            "job_id": job_id,
            "rows_received": len(rows),
            "message": f"Analysis queued. Poll GET /api/jobs/{job_id} for results.",
        }
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Poll analysis job status and results."""
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return job


@app.get("/api/jobs")
async def list_jobs():
    """List recent analysis jobs."""
    return {"jobs": list_recent_jobs()}
