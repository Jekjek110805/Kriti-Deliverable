"""
jobs.py -- Async analysis job queue for Hermes-powered analysis.

In-memory job store. Each job has:
  - job_id: unique ID
  - status: pending | running | complete | error
  - result: Hermes output (when complete)
  - error: error message (when failed)
  - created_at / completed_at: timestamps
"""
import uuid
import time
import asyncio
import json
import os
from typing import Dict, Any, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

JOBS_FILE = os.path.join(DATA_DIR, "analysis_jobs.json")

# In-memory job store
_jobs: Dict[str, Dict[str, Any]] = {}


def _load_jobs():
    """Load persisted jobs from disk."""
    global _jobs
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, "r") as f:
                _jobs = json.load(f)
        except (json.JSONDecodeError, IOError):
            _jobs = {}


def _save_jobs():
    """Persist jobs to disk."""
    try:
        with open(JOBS_FILE, "w") as f:
            json.dump(_jobs, f, indent=2)
    except IOError:
        pass


def create_job(rows: list) -> str:
    """Create a new analysis job and return job_id."""
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "rows_count": len(rows),
        "rows": rows,
        "result": None,
        "error": None,
        "created_at": time.time(),
        "completed_at": None,
    }
    _save_jobs()
    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job by ID (without internal rows data for API response)."""
    job = _jobs.get(job_id)
    if not job:
        return None
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "rows_count": job["rows_count"],
        "result": job.get("result"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at"),
        "elapsed_seconds": round(time.time() - job["created_at"], 1) if not job.get("completed_at") else round(job["completed_at"] - job["created_at"], 1),
    }


def update_job(job_id: str, status: str = None, result: dict = None, error: str = None):
    """Update job status and result."""
    if job_id not in _jobs:
        return
    if status:
        _jobs[job_id]["status"] = status
    if result is not None:
        _jobs[job_id]["result"] = result
    if error:
        _jobs[job_id]["error"] = error
    if status in ("complete", "error"):
        _jobs[job_id]["completed_at"] = time.time()
    _save_jobs()


async def run_job_analysis(job_id: str):
    """Run Hermes analysis for a background job and save output files on completion."""
    from hermes_client import hermes_analyze_stage1a

    job = _jobs.get(job_id)
    if not job:
        return

    update_job(job_id, status="running")
    try:
        rows = job.get("rows", [])
        result = await hermes_analyze_stage1a(rows)
        if "error" in result:
            update_job(job_id, status="error", error=result["error"])
        else:
            # Save output files
            _save_job_outputs(job_id, result)
            update_job(job_id, status="complete", result=result)
    except Exception as e:
        update_job(job_id, status="error", error=str(e))


def _save_job_outputs(job_id: str, result: dict):
    """Save Hermes analysis results to standard output files."""
    import csv as _csv
    import io
    from datetime import datetime

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reports_dir = os.path.join(base, "reports")
    outputs_dir = os.path.join(base, "outputs")
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(outputs_dir, exist_ok=True)

    opportunities = result.get("opportunities", [])
    excluded = result.get("excluded", [])
    excluded_details = []
    for e_item in excluded:
        if isinstance(e_item, dict):
            excluded_details.append({"row": e_item.get("keyword", ""), "reason": e_item.get("reason", "")})
        elif isinstance(e_item, str):
            excluded_details.append({"row": e_item, "reason": "excluded"})

    # Save CSV
    if opportunities:
        csv_path = os.path.join(outputs_dir, "stage_1a_existing_page_opportunities.csv")
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
                "volume": o.get("volume", "not_available"),
                "keyword_difficulty": o.get("keyword_difficulty", "not_available"),
                "score": o.get("score", o.get("total_score", 0)),
                "recommendation": o["recommendation"],
                "reason": o.get("reason", ""),
                "approval_status": o.get("approval_status", "needs_review"),
            }
            if writer is None:
                writer = _csv.DictWriter(output, fieldnames=row.keys())
                writer.writeheader()
            writer.writerow(row)
        with open(csv_path, "w") as f:
            f.write(output.getvalue())


def list_recent_jobs(limit: int = 10) -> list:
    """List recent jobs (newest first)."""
    jobs = sorted(_jobs.values(), key=lambda j: j.get("created_at", 0), reverse=True)
    return [
        {
            "job_id": j["job_id"],
            "status": j["status"],
            "rows_count": j.get("rows_count", 0),
            "created_at": j.get("created_at"),
            "completed_at": j.get("completed_at"),
            "elapsed_seconds": round(time.time() - j["created_at"], 1) if not j.get("completed_at") else round(j["completed_at"] - j["created_at"], 1),
        }
        for j in jobs[:limit]
    ]


# Load jobs on import
_load_jobs()
