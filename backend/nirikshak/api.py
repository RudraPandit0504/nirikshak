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

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import llm, qa, sebi, tts
from .analyse import LLMError
from .categories import CATEGORIES
from .config import DATA_DIR, LLM_MODEL, REPORTS_DIR, WORK_DIR
from .ingest import IngestError
from .models import Report
from .pipeline import STAGES, run_audit, run_message_audit

app = FastAPI(title="Nirikshak", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

executor = ThreadPoolExecutor(max_workers=1)

# When hosted with a shared API key, each visitor gets a small budget so the key can't be drained.
HOSTED = llm.PROVIDER != "ollama"
LIMITS = {"audit": (20, 3600), "message": (40, 3600), "profile": (6, 3600), "ask": (80, 3600)}
_hits: dict[tuple[str, str], list[float]] = {}


def _limit(request: Request, kind: str) -> None:
    if not HOSTED:
        return
    import time as _t

    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    n, window = LIMITS[kind]
    now = _t.time()
    with LOCK:
        recent = [x for x in _hits.get((ip, kind), []) if now - x < window]
        if len(recent) >= n:
            raise HTTPException(429, "This public demo has a small hourly limit per visitor so the shared AI key "
                                     "isn't used up. Please try again later, or run Nirikshak locally (see GitHub).")
        _hits[(ip, kind)] = recent + [now]
# job id -> list of events (dicts). Kept in memory; finished reports are on disk.
JOBS: dict[str, list[dict]] = {}
LOCK = threading.Lock()
MAX_UPLOAD = 200 * 1024 * 1024


def _emit(job: str, event: dict) -> None:
    with LOCK:
        JOBS[job].append(event)


def _run(job: str, target, runner=None) -> None:
    def progress(stage, frac, msg, msg_hi="", **extra):
        _emit(job, {"type": "progress", "stage": stage, "frac": round(frac, 3), "msg": msg, "msg_hi": msg_hi or msg, **extra})

    try:
        result = runner(progress, job) if runner else run_audit(target, progress, job_id=job)
        if isinstance(result, Report):
            _emit(job, {"type": "done", "id": result.id, "kind": "report"})
            tts.prewarm(result)
        else:
            _emit(job, {"type": "done", "id": result.id, "kind": "profile"})
    except (IngestError, LLMError) as e:
        _emit(job, {"type": "error", "msg": str(e)})
    except Exception as e:  # noqa: BLE001 - surface anything to the UI
        _emit(job, {"type": "error", "msg": f"Unexpected error: {e}"})
    finally:
        if isinstance(target, Path) and target.exists():
            shutil.rmtree(target.parent, ignore_errors=True)


def _start(target, runner=None) -> dict:
    job = uuid.uuid4().hex[:12]
    with LOCK:
        JOBS[job] = [{"type": "queued", "position": executor._work_queue.qsize()}]
    executor.submit(_run, job, target, runner)
    return {"job": job}


@app.get("/api/meta")
def meta():
    return {"model": llm.model_label(), "provider": llm.PROVIDER, "stages": STAGES, "categories": CATEGORIES, "registry_size": sebi.registry_size()}


@app.post("/api/audit")
def audit_url(request: Request, url: str = Form(...)):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Please paste a full YouTube link.")
    _limit(request, "audit")
    return _start(url)


@app.post("/api/audit/upload")
async def audit_upload(request: Request, file: UploadFile = File(...)):
    _limit(request, "audit")
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


@app.post("/api/check-message")
async def check_message(request: Request, text: str = Form(""), save: bool = Form(True), image: UploadFile | None = File(None)):
    """Check a forwarded WhatsApp/Telegram/SMS tip: pasted text, or a screenshot read by the vision model."""
    _limit(request, "message")
    path = None
    if image is not None and image.filename:
        up = WORK_DIR / f"msg-{uuid.uuid4().hex[:8]}"
        up.mkdir(parents=True)
        path = up / Path(image.filename).name
        data = await image.read()
        if len(data) > 15 * 1024 * 1024:
            shutil.rmtree(up, ignore_errors=True)
            raise HTTPException(413, "Image too large (max 15 MB).")
        path.write_bytes(data)
    elif not text.strip():
        raise HTTPException(400, "Paste a message or attach a screenshot.")
    return _start(None, lambda progress, job: run_message_audit(
        text=text if path is None else None, image=path, progress=progress, job_id=job, private=not save))


@app.post("/api/profile")
def profile_start(request: Request, url: str = Form(...), n: int = Form(8)):
    """Audit a channel's recent videos (reusing existing reports) and build a trust profile."""
    from .profile import run_profile

    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Paste a YouTube channel link or any video link from that channel.")
    n = max(3, min(5 if HOSTED else 15, n))
    _limit(request, "profile")
    return _start(None, lambda progress, job: run_profile(url, n, progress))


@app.get("/api/profiles")
def profiles_list():
    from .profile import list_profiles

    return list_profiles()


@app.get("/api/profiles/{pid}")
def profile_get(pid: str):
    from .profile import PROFILES_DIR

    if not all(ch.isalnum() or ch in "-_" for ch in pid):
        raise HTTPException(400, "Bad id")
    p = PROFILES_DIR / f"{pid}.json"
    if not p.exists():
        raise HTTPException(404, "Profile not found")
    return FileResponse(p, media_type="application/json")


@app.delete("/api/reports/{rid}")
def delete_report(rid: str):
    p = _report_path(rid)
    p.unlink()
    for f in (DATA_DIR / "speech").glob(f"{rid}-*"):
        f.unlink(missing_ok=True)
    return {"deleted": rid}


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


@app.get("/api/reports/{rid}/speech")
def speech(rid: str, lang: str = "en"):
    """The summary read aloud (WAV), generated with Kokoro on first request and cached."""
    report = Report.model_validate_json(_report_path(rid).read_text(encoding="utf-8"))
    try:
        path = tts.speech_path(report, lang)
    except tts.TTSError as e:
        raise HTTPException(503, str(e)) from e
    media = "audio/mp4" if path.suffix == ".m4a" else "audio/wav"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "no-cache"})


class AskBody(BaseModel):
    question: str
    lang: str = "en"
    history: list[dict] = []


@app.post("/api/reports/{rid}/ask")
async def ask(request: Request, rid: str, body: AskBody):
    """Answer a question about one report. Not queued behind audits: Ollama serialises
    requests itself, and a question shouldn't wait minutes for an audit to finish."""
    if not body.question.strip():
        raise HTTPException(400, "Empty question")
    _limit(request, "ask")
    report = Report.model_validate_json(_report_path(rid).read_text(encoding="utf-8"))
    try:
        ans = await asyncio.get_running_loop().run_in_executor(
            None, lambda: qa.ask(report, body.question, body.lang, body.history))
    except LLMError as e:
        raise HTTPException(503, str(e)) from e
    return ans


@app.post("/api/transcribe")
async def transcribe_question(file: UploadFile = File(...)):
    """Turn a short spoken question into text with the local Whisper model."""
    from .analyse import unload_models
    from .ingest import to_wav
    from .transcribe import transcribe

    work = WORK_DIR / f"voice-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True)
    try:
        raw = work / "question.webm"
        data = await file.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(413, "Recording too long")
        raw.write_bytes(data)

        def run():
            unload_models()  # free VRAM for Whisper
            segs, lang = transcribe(to_wav(raw, work))
            return {"text": " ".join(s.text for s in segs).strip(), "language": lang}

        return await asyncio.get_running_loop().run_in_executor(executor, run)
    finally:
        shutil.rmtree(work, ignore_errors=True)


@app.get("/api/reports")
def list_reports(limit: int = 20):
    out = []
    for p in sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if r.get("private"):
            continue
        out.append({
            "id": r["id"], "kind": r["source"]["kind"], "title": r["source"]["title"], "channel": r["source"]["channel"],
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
