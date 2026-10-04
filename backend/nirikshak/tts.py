"""Read-aloud with Kokoro-82M (ONNX, CPU).

Browsers on Linux fall back to espeak, which is barely intelligible. Kokoro was
picked by benchmark (Whisper character-error-rate for intelligibility, UTMOS for
naturalness): af_heart scores 4.5/5 UTMOS in English vs espeak's 1.6, and
hf_alpha 4.1 vs 1.4 in Hindi. Hindi text is converted to Devanagari before
synthesis, because Latin words like "SEBI" make the phonemizer switch language
mid-sentence; that alone cut the Hindi character error rate from 14% to 4%.
"""
from __future__ import annotations

import re
import subprocess
import threading
from pathlib import Path

import httpx
import numpy as np

from .categories import CATEGORIES
from .config import MODELS_DIR, SPEECH_DIR, TTS_VOICE_EN, TTS_VOICE_HI
from .models import Report, Summary

RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
VOICES = {"en": (TTS_VOICE_EN, "en-us"), "hi": (TTS_VOICE_HI, "hi")}

_lock = threading.Lock()
_engine = None


class TTSError(RuntimeError):
    pass


def _ensure_models() -> None:
    for name in FILES:
        dest = MODELS_DIR / name
        if dest.exists():
            continue
        tmp = dest.with_suffix(".part")
        try:
            with httpx.stream("GET", RELEASE + name, follow_redirects=True, timeout=600) as r:
                r.raise_for_status()
                with tmp.open("wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
        except httpx.HTTPError as e:
            tmp.unlink(missing_ok=True)
            raise TTSError(f"Could not download the voice model ({name}): {e}") from e
        tmp.rename(dest)


def _kokoro():
    global _engine
    if _engine is None:
        _ensure_models()
        from kokoro_onnx import Kokoro

        _engine = Kokoro(str(MODELS_DIR / FILES[0]), str(MODELS_DIR / FILES[1]))
    return _engine


# --- text normalisation -------------------------------------------------------

HI_TERMS = {
    "sebi": "सेबी", "telegram": "टेलीग्राम", "whatsapp": "व्हाट्सऐप", "youtube": "यूट्यूब",
    "demat": "डीमैट", "stock": "स्टॉक", "stocks": "स्टॉक्स", "crypto": "क्रिप्टो", "bitcoin": "बिटकॉइन",
    "intraday": "इंट्राडे", "trading": "ट्रेडिंग", "option": "ऑप्शन", "options": "ऑप्शंस", "app": "ऐप",
    "link": "लिंक", "vip": "वी आई पी", "fomo": "फोमो", "ipo": "आई पी ओ", "ra": "आर ए", "ia": "आई ए",
    "token": "टोकन", "tokens": "टोकन", "coin": "कॉइन", "coins": "कॉइन", "premium": "प्रीमियम",
    "membership": "मेंबरशिप", "channel": "चैनल", "group": "ग्रुप", "market": "मार्केट",
}
HI_LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                      "ए बी सी डी ई एफ जी एच आई जे के एल एम एन ओ पी क्यू आर एस टी यू वी डब्ल्यू एक्स वाई ज़ेड".split()))


def _hi_word(m: re.Match) -> str:
    w = m.group(0)
    if w.lower() in HI_TERMS:
        return HI_TERMS[w.lower()]
    if w.isupper() and len(w) <= 5:
        return " ".join(HI_LETTERS[c] for c in w)
    return w


def _clean(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\bIN[AH]\d{6,}\b", "", text)  # registration numbers are unreadable aloud
    text = text.replace("₹", " rupees ").replace("&", " and ").replace("/", " or ")
    text = re.sub(r"(\d+)\s*[xX]\b", r"\1 times", text)
    text = re.sub(r"[\"“”'‘’()\[\]*_#•→]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# How Indian speakers say these; the phonemizer gets them wrong as written (checked with Whisper).
EN_RESPELL = {
    "Nirikshak": "Nee-rick-shuck", "SEBI": "see-bee", "SEBI's": "see-bee's", "OTP": "O.T.P.", "OTPs": "O.T.P.s",
    "UPI": "U.P.I.", "KYC": "K.Y.C.", "NSDL": "N.S.D.L.", "NSE": "N.S.E.", "BSE": "B.S.E.", "IPO": "I.P.O.",
    "Zerodha": "Zeh-roe-dha", "demat": "dee-mat", "DEMAT": "dee-mat", "finfluencer": "fin-fluencer",
    "finfluencers": "fin-fluencers", "APK": "A.P.K.", "RBI": "R.B.I.",
}


def normalise(text: str, lang: str) -> str:
    text = _clean(text)
    if lang == "en":
        for k, v in EN_RESPELL.items():
            text = re.sub(rf"\b{re.escape(k)}\b", v, text)
    if lang == "hi":
        text = text.replace("rupees", "रुपये").replace(" times", " गुना").replace(" or ", " या ")
        text = re.sub(r"[A-Za-z]+", _hi_word, text)
    return text


def _when(t: float, lang: str) -> str:
    m, s = int(t // 60), int(t % 60)
    if lang == "hi":
        return f"{m} मिनट {s} सेकंड पर" if m else f"{s} सेकंड पर"
    return f"At {m} minute{'s' if m != 1 else ''} {s} seconds" if m else f"At {s} seconds"


def speech_script(s: Summary, lang: str, message: bool = False) -> list[str]:
    """What gets read aloud: the full brief, as sentences."""
    intro = {"en": ("Main concerns.", "In the description"), "hi": ("मुख्य चिंताएँ।", "डिस्क्रिप्शन में")}[lang]
    parts = [s.headline, s.overview]
    if s.concerns:
        parts.append(intro[0])
        for c in s.concerns:
            if message:
                where = f"लाइन {int(c.start) + 1} में" if lang == "hi" else f"In line {int(c.start) + 1}"
            else:
                where = _when(c.start, lang) if c.where == "transcript" else intro[1]
            parts.append(f"{where}, {CATEGORIES[c.category][lang]}. {c.why}")
    parts.append(s.registration)
    parts.extend(s.advice)
    sentences = []
    for p in parts:
        sentences += [x for x in re.split(r"(?<=[.!?।])\s+", normalise(p, lang)) if x.strip()]
    return sentences


def _synth(sentences: list[str], lang: str) -> tuple[np.ndarray, int]:
    voice, code = VOICES[lang]
    k = _kokoro()
    pieces, sr = [], 24000
    for sent in sentences:
        audio, sr = k.create(sent, voice=voice, speed=1.0, lang=code)
        pieces += [audio, np.zeros(int(sr * 0.25), dtype=np.float32)]  # short pause between sentences
    return np.concatenate(pieces) if pieces else np.zeros(1, dtype=np.float32), sr


def speech_path(report: Report, lang: str) -> Path:
    if lang not in VOICES:
        raise TTSError("Unsupported language")
    if not report.summary:
        raise TTSError("This report has no summary yet. Run: nirikshak resummarize")
    voice = VOICES[lang][0]
    out = SPEECH_DIR / f"{report.id}-{lang}-{voice}.m4a"
    if out.exists():
        return out
    import soundfile as sf

    with _lock:  # one synthesis at a time; also guards lazy model loading
        if not out.exists():
            audio, sr = _synth(speech_script(report.summary[lang], lang, report.source.kind == "message"), lang)
            wav = out.with_suffix(".wav")
            sf.write(wav, audio, sr, subtype="PCM_16")
            # AAC is ~10x smaller than WAV and plays in every browser.
            tmp = out.with_suffix(".part.m4a")
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "64k",
                                "-movflags", "+faststart", str(tmp)], capture_output=True)
            if r.returncode == 0:
                tmp.rename(out)
                wav.unlink()
            else:  # no ffmpeg/aac: serve the WAV instead
                tmp.unlink(missing_ok=True)
                return wav
    return out


def prewarm(report: Report) -> None:
    """Generate both languages in the background right after an audit, so the
    Listen button plays instantly. Failures are ignored; the API retries on demand."""
    def run():
        for lang in ("en", "hi"):
            try:
                speech_path(report, lang)
            except Exception:
                pass

    threading.Thread(target=run, daemon=True).start()
