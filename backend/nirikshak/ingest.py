"""Fetch a video's metadata and transcript.

Captions are the fast path. When a video has none, or the input is an uploaded
file, the audio goes to Whisper instead.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import httpx
import yt_dlp

from .config import MAX_DURATION
from .models import Segment, Source

YDL_BASE = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "js_runtimes": {"node": {}, "deno": {}},
}

YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})")


class IngestError(RuntimeError):
    pass


def youtube_id(url: str) -> str | None:
    m = YT_ID.search(url)
    return m.group(1) if m else None


def _pick_caption_track(info: dict) -> tuple[str, str] | None:
    """Return (lang, json3 url), preferring captions in the spoken language."""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    spoken = (info.get("language") or "").split("-")[0]

    def json3(tracks):
        for t in tracks:
            if t.get("ext") == "json3":
                return t["url"]
        return None

    order: list[tuple[dict, str]] = []
    for lang in (spoken, "hi", "en"):
        if lang:
            order.append((manual, lang))
    # "<lang>-orig" is the auto caption in the language actually spoken;
    # plain "<lang>" in automatic_captions is usually a machine translation.
    for key in auto:
        if key.endswith("-orig"):
            order.append((auto, key))
    for lang in (spoken, "hi", "en"):
        if lang:
            order.append((auto, lang))

    for tracks, lang in order:
        if lang in tracks and (u := json3(tracks[lang])):
            return lang.removesuffix("-orig"), u
    return None


def _parse_json3(data: dict) -> list[Segment]:
    segs = []
    for ev in data.get("events", []):
        if "segs" not in ev:
            continue
        text = "".join(s.get("utf8", "") for s in ev["segs"]).replace("\n", " ").strip()
        if not text:
            continue
        start = ev.get("tStartMs", 0) / 1000
        segs.append(Segment(start=start, end=start + ev.get("dDurationMs", 0) / 1000, text=text))
    return _merge_short(segs)


def _merge_short(segs: list[Segment], target: float = 6.0) -> list[Segment]:
    """Auto captions arrive as 1-2 word fragments; join them into ~sentence-sized lines."""
    out: list[Segment] = []
    for s in segs:
        if out and (s.start - out[-1].start) < target and not out[-1].text.endswith((".", "?", "!", "।")):
            last = out[-1]
            out[-1] = Segment(start=last.start, end=max(last.end, s.end), text=f"{last.text} {s.text}")
        else:
            out.append(s)
    return out


def fetch_youtube(url: str, workdir: Path, want_audio: bool = False) -> tuple[Source, list[Segment] | None, Path | None]:
    vid = youtube_id(url)
    if not vid:
        raise IngestError("That does not look like a YouTube link.")
    try:
        with yt_dlp.YoutubeDL(YDL_BASE) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    except yt_dlp.utils.DownloadError as e:
        raise IngestError(f"Could not read the video: {e}") from e

    duration = float(info.get("duration") or 0)
    if duration > MAX_DURATION:
        raise IngestError(f"Video is {duration / 60:.0f} min long; the limit is {MAX_DURATION // 60} min.")

    source = Source(
        kind="youtube",
        url=f"https://www.youtube.com/watch?v={vid}",
        video_id=vid,
        title=info.get("title") or "",
        channel=info.get("channel") or info.get("uploader") or "",
        description=info.get("description") or "",
        duration=duration,
        language=info.get("language"),
    )

    segments = None
    if not want_audio and (track := _pick_caption_track(info)):
        lang, cap_url = track
        r = httpx.get(cap_url, timeout=30, follow_redirects=True)
        if r.status_code == 200:
            segments = _parse_json3(r.json())
            source.language = lang
            source.transcript_source = "captions"

    audio = None
    if not segments:
        audio = download_audio(source.url, workdir)
    return source, segments or None, audio


def download_audio(url: str, workdir: Path) -> Path:
    opts = {
        **YDL_BASE,
        "skip_download": False,
        "format": "bestaudio/best",
        "outtmpl": str(workdir / "audio.%(ext)s"),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        raw = Path(ydl.prepare_filename(info))
    return to_wav(raw, workdir)


def to_wav(path: Path, workdir: Path) -> Path:
    if not shutil.which("ffmpeg"):
        raise IngestError("ffmpeg is required for audio input.")
    out = workdir / "audio.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000", str(out)],
        check=True,
    )
    return out


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def ocr_image(path: Path) -> str:
    """Read the text in a screenshot with the local vision model (gemma3, via Ollama)."""
    import base64

    from .config import HI_MODEL, OLLAMA_URL

    img = base64.b64encode(path.read_bytes()).decode()
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/chat", json={
            "model": HI_MODEL,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1500},
            "messages": [{
                "role": "user",
                "content": ("You are an OCR engine. Copy ALL the text in this screenshot of a chat or message, "
                            "line by line, exactly as written. Hindi in Devanagari script must stay in Devanagari "
                            "(for example पक्का मुनाफा, never 'pakka munafa'); English or Hinglish in Latin letters "
                            "stays in Latin letters. Never transliterate or translate. Keep links, numbers, UPI IDs "
                            "and names exactly. Output only the text, nothing else."),
                "images": [img],
            }],
        }, timeout=300)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise IngestError(f"Could not read the screenshot: {e}") from e
    return r.json().get("message", {}).get("content", "").strip()
