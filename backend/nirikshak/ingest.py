"""Fetch a video's metadata and transcript.

Captions are the fast path. When a video has none, or the input is an uploaded
file, the audio goes to Whisper instead.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import httpx
import yt_dlp

from .config import DATA_DIR, MAX_DURATION
from .models import Segment, Source

YDL_BASE = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "js_runtimes": {"node": {}, "deno": {}},
}

# YouTube asks cloud servers (AWS, GCP, …) to "sign in to confirm you're not a bot". A hosted demo can
# drop a Netscape-format cookies file from a logged-in browser here; it is picked up on the next request.
COOKIES = Path(os.environ.get("NIRIKSHAK_YT_COOKIES", DATA_DIR / "youtube_cookies.txt"))


def _ydl(extra: dict | None = None) -> dict:
    opts = {**YDL_BASE, **(extra or {})}
    if COOKIES.is_file():
        opts["cookiefile"] = str(COOKIES)
    return opts


def _download_error(e: Exception, what: str) -> IngestError:
    msg = str(e)
    if "not a bot" in msg or "Sign in to confirm" in msg:
        return IngestError("YouTube is blocking this server (it asks cloud servers to sign in). Try one of the "
                           "audited videos below, upload the video file instead, or run Nirikshak on your own "
                           "computer, where YouTube links work normally.")
    return IngestError(f"Could not read the {what}: {msg}")


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
    # "<lang>-orig" is the auto caption in the language actually spoken; plain "<lang>" is usually
    # a machine translation. Auto-dubbed videos have several "-orig" tracks (one per dubbed audio),
    # so prefer the video's declared spoken language, then Hindi/English, then anything else.
    origs = [k for k in auto if k.endswith("-orig")]
    for pref in (spoken, "en", "hi"):
        for key in origs:
            if pref and key.split("-")[0] == pref:
                order.append((auto, key))
    for key in origs:
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
        with yt_dlp.YoutubeDL(_ydl()) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    except yt_dlp.utils.DownloadError as e:
        raise _download_error(e, "video") from e

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
        channel_id=info.get("channel_id"),
        upload_date=info.get("upload_date"),
    )

    segments = None
    if not want_audio and (track := _pick_caption_track(info)):
        lang, cap_url = track
        jar = None
        if COOKIES.is_file():
            from http.cookiejar import MozillaCookieJar
            jar = MozillaCookieJar(str(COOKIES))
            jar.load(ignore_discard=True, ignore_expires=True)
        r = httpx.get(cap_url, timeout=30, follow_redirects=True, cookies=jar)
        if r.status_code == 200:
            segments = _parse_json3(r.json())
            source.language = lang
            source.transcript_source = "captions"

    audio = None
    if not segments:
        audio = download_audio(source.url, workdir)
    return source, segments or None, audio


def download_audio(url: str, workdir: Path) -> Path:
    opts = _ydl({
        "skip_download": False,
        "format": "bestaudio/best",
        "outtmpl": str(workdir / "audio.%(ext)s"),
    })
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
    """Read the text in a screenshot with a vision model (local gemma3, or Gemini when hosted)."""
    import base64

    from .llm import LLMError, vision_text

    prompt = ("You are an OCR engine. Copy ALL the text in this screenshot of a chat or message, "
              "line by line, exactly as written. Hindi in Devanagari script must stay in Devanagari "
              "(for example पक्का मुनाफा, never 'pakka munafa'); English or Hinglish in Latin letters "
              "stays in Latin letters. Never transliterate or translate. Keep links, numbers, UPI IDs "
              "and names exactly. Output only the text, nothing else.")
    try:
        return vision_text(base64.b64encode(path.read_bytes()).decode(), prompt)
    except LLMError as e:
        raise IngestError(str(e)) from e


CHANNEL_URL = re.compile(r"youtube\.com/(@[\w.\-]+|channel/[\w-]+|c/[\w.\-]+|user/[\w.\-]+)", re.I)


def is_channel_url(url: str) -> bool:
    return bool(CHANNEL_URL.search(url)) and not youtube_id(url)


def list_channel_videos(url: str, n: int) -> tuple[dict, list[dict]]:
    """A channel's n most recent normal videos (newest first), from a channel URL or any of its video URLs."""
    with yt_dlp.YoutubeDL(_ydl({"extract_flat": "in_playlist"})) as ydl:
        if not is_channel_url(url):
            vid = youtube_id(url)
            if not vid:
                raise IngestError("Paste a YouTube channel link (youtube.com/@name) or any video link from that channel.")
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False, process=False)
            url = info.get("channel_url") or info.get("uploader_url")
            if not url:
                raise IngestError("Could not find the channel of that video.")
        m = CHANNEL_URL.search(url)
        base = f"https://www.youtube.com/{m.group(1)}" if m else url.rstrip("/")
        try:
            info = ydl.extract_info(f"{base}/videos", download=False)
        except yt_dlp.utils.DownloadError as e:
            raise _download_error(e, "channel") from e
    videos = []
    for e in info.get("entries") or []:
        if len(videos) >= n:
            break
        dur = e.get("duration")
        if not e.get("id") or dur is None or dur > MAX_DURATION or dur < 60 or e.get("live_status") in ("is_live", "is_upcoming"):
            continue  # live streams, premieres, Shorts-length clips and very long videos are skipped
        videos.append({"id": e["id"], "title": e.get("title") or "", "duration": dur})
    if not videos:
        raise IngestError("No suitable videos found on this channel.")
    channel = {"name": info.get("channel") or info.get("uploader") or "", "id": info.get("channel_id") or base.rsplit("/", 1)[-1],
               "url": base}
    return channel, videos
