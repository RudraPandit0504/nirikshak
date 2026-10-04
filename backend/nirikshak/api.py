"""HTTP API. Audits run one at a time on a worker thread (they share the GPU);
progress is pushed to the browser over Server-Sent Events."""
from __future__ import annotations

import asyncio
import json
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import sebi
from .analyse import LLMError
from .categories import CATEGORIES
from .config import LLM_MODEL, REPORTS_DIR, WORK_DIR
from .ingest import IngestError
from .pipeline import STAGES, run_audit

app = FastAPI(title="Nirikshak", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

executor = ThreadPoolExecutor(max_workers=1)
# job id -> list of events (dicts). Kept in memory; finished reports are on disk.
JOBS: dict[str, list[dict]] = {}
LOCK = threading.Lock()
MAX_UPLOAD = 200 * 1024 * 1024


def _emit(job: str, event: dict) -> None:
    with LOCK:
        JOBS[job].append(event)


def _run(job: str, target) -> None:
    def progress(stage, frac, msg):
        _emit(job, {"type": "progress", "stage": stage, "frac": round(frac, 3), "msg": msg})

    try:
        report = run_audit(target, progress, job_id=job)
        _emit(job, {"type": "done", "id": report.id})
    except (IngestError, LLMError) as e:
        _emit(job, {"type": "error", "msg": str(e)})
    except Exception as e:  # noqa: BLE001 - surface anything to the UI
        _emit(job, {"type": "error", "msg": f"Unexpected error: {e}"})
    finally:
        if isinstance(target, Path):
            shutil.rmtree(target.parent, ignore_errors=True)


def _start(target) -> dict:
    job = uuid.uuid4().hex[:12]
    with LOCK:
        JOBS[job] = [{"type": "queued", "position": executor._work_queue.qsize()}]
    executor.submit(_run, job, target)
    return {"job": job}


@app.get("/api/meta")
def meta():
    return {"model": LLM_MODEL, "stages": STAGES, "categories": CATEGORIES, "registry_size": sebi.registry_size()}


@app.post("/api/audit")
def audit_url(url: str = Form(...)):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Please paste a full YouTube link.")
    return _start(url)


@app.post("/api/audit/upload")
async def audit_upload(file: UploadFile = File(...)):
    up = WORK_DIR / f"upload-{uuid.uuid4().hex[:8]}"
    up.mkdir(parents=True)
    dest = up / Path(file.filename or "upload").name
    size = 0
    with dest.open("wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD:
                shutil.rmtree(up, ignore_errors=True)
                raise HTTPException(413, "File too large (max 200 MB).")
            f.write(chunk)
    return _start(dest)


@app.get("/api/audit/{job}/events")
async def events(job: str):
    if job not in JOBS:
        raise HTTPException(404, "Unknown job")

    async def stream():
        sent = 0
        while True:
            with LOCK:
                batch = JOBS[job][sent:]
            for ev in batch:
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if ev["type"] in ("done", "error"):
                    return
            sent += len(batch)
            await asyncio.sleep(0.3)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def _report_path(rid: str) -> Path:
    if not rid.isalnum():
        raise HTTPException(400, "Bad id")
    p = REPORTS_DIR / f"{rid}.json"
    if not p.exists():
        raise HTTPException(404, "Report not found")
    return p


@app.get("/api/reports/{rid}")
def get_report(rid: str):
    return FileResponse(_report_path(rid), media_type="application/json")


@app.get("/api/reports")
def list_reports(limit: int = 20):
    out = []
    for p in sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out.append({
            "id": r["id"], "title": r["source"]["title"], "channel": r["source"]["channel"],
            "video_id": r["source"].get("video_id"), "risk_score": r["risk_score"],
            "risk_level": r["risk_level"], "created_at": r["created_at"],
        })
    return out


@app.get("/api/sebi/{reg_no}")
def sebi_lookup(reg_no: str):
    hit = sebi.lookup_number(reg_no)
    return {"reg_no": reg_no.upper(), "found": hit is not None, "entity": hit}


# Serve the built frontend if present (single-process deployment).
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
