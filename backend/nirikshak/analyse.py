"""LLM claim extraction, grounding against the transcript, and merging with rule hits."""
from __future__ import annotations

import json
import re
from typing import Callable

import httpx
from rapidfuzz import fuzz

from . import hindi, llm
from .categories import CATEGORIES
from .config import HI_MODEL, LLM_MODEL, OLLAMA_URL, WINDOW_SECONDS
from .models import Claim, Segment
from .rules import RuleHit

# Videos are judged on the original 8 categories (what the eval measures); forwarded
# messages additionally get the scam-specific ones.
MESSAGE_ONLY = ("credential_request", "suspicious_link", "upfront_payment", "impersonation")
VIDEO_CATS = [c for c in CATEGORIES if c not in MESSAGE_ONLY]
MESSAGE_CATS = list(CATEGORIES)


def _claim_schema(cats: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "line": {"type": "integer"},
                        "quote": {"type": "string"},
                        "category": {"type": "string", "enum": cats},
                        "severity": {"type": "integer", "minimum": 1, "maximum": 3},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "why_en": {"type": "string"},
                    },
                    "required": ["line", "quote", "category", "severity", "confidence", "why_en"],
                },
            }
        },
        "required": ["claims"],
    }


CLAIM_SCHEMA = _claim_schema(VIDEO_CATS)
MESSAGE_SCHEMA = _claim_schema(MESSAGE_CATS)

TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {"hindi": {"type": "array", "items": {"type": "string"}}},
    "required": ["hindi"],
}

SYSTEM = f"""You are Nirikshak, a compliance auditor that protects Indian retail investors.
You read transcripts of finance videos by social-media "finfluencers" (Hindi, English or Hinglish)
and flag statements that could mislead or harm investors.

Flag ONLY statements that fit one of these categories:
{chr(10).join(f"- {k}: {CATEGORIES[k]['prompt']}" for k in VIDEO_CATS)}

Rules:
- Neutral education is NOT a claim. Explaining what a stop-loss is, describing risk, history, or how markets work must not be flagged.
- Warnings ABOUT scams are NOT claims (e.g. "if someone promises guaranteed returns, that is a red flag"). Only flag what the speaker themselves promises, recommends or pushes.
- One line can contain several claims of different categories (e.g. a paid group AND urgency); list each separately.
- Do not flag a hypothetical example unless it is presented as an expected outcome for the viewer.
- "quote" must be copied verbatim from the given line (a short span, max ~25 words). Never invent text.
- "line" is the number in square brackets of the line containing the quote.
- severity: 3 = direct harm (guarantees, explicit buy/sell call), 2 = strong pressure or hype, 1 = mild.
- confidence: how sure you are this really is a problematic claim in context (0-1).
- why_en: one plain-English sentence explaining to a first-time investor why this is a warning sign.
- Never judge whether a stock or product is good or bad, and never give investment advice yourself.
- Captions may be auto-generated and contain recognition errors; interpret charitably.
- If nothing qualifies, return {{"claims": []}}."""


LLMError = llm.LLMError


def _chat(messages: list[dict], schema: dict, num_predict: int = 1500, model: str = LLM_MODEL) -> dict:
    """All structured model calls go through the provider layer (Ollama locally, Gemini when hosted)."""
    return llm.chat_json(messages, schema, num_predict, model)


def unload_models() -> None:
    llm.unload_local_models()


def windows(segments: list[Segment], seconds: int = WINDOW_SECONDS) -> list[list[int]]:
    """Group segment indices into consecutive windows of about `seconds` length."""
    out: list[list[int]] = []
    for i, s in enumerate(segments):
        if not out or s.start - segments[out[-1][0]].start >= seconds:
            out.append([])
        out[-1].append(i)
    return out


def _fmt(t: float) -> str:
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def _ground(quote: str, text: str) -> float:
    return fuzz.partial_ratio(quote.lower(), text.lower()) if quote else 0.0


REG_WORDS = re.compile(r"sebi|regist|सेबी|रजिस्ट|\bIN[AH]\s*-?\d", re.I)


# The model sometimes flags a speaker who is *warning* viewers, and says so in its own
# explanation ("the speaker warns against schemes promising high returns").
SELF_CONTRADICTION = re.compile(r"\b(warns?|warning|cautions?|cautioning|advises? against)\b.{0,40}\b(against|about|viewers|investors|not to)\b", re.I)


def _plausible(c: dict) -> bool:
    """Category-specific sanity checks on LLM output."""
    if c.get("category") == "registration_claim":
        return bool(REG_WORDS.search(c.get("quote", "")))
    if SELF_CONTRADICTION.search(c.get("why_en", "")):
        return False
    return True


MESSAGE_SYSTEM = f"""You are Nirikshak, a fraud-awareness assistant that protects Indian retail investors.
You read a message someone received on WhatsApp, Telegram or SMS (Hindi, English or Hinglish), often a
forwarded "stock tip" or an alert claiming to be from a broker or regulator, and flag what could harm them.

Flag ONLY text that fits one of these categories:
{chr(10).join(f"- {k}: {CATEGORIES[k]['prompt']}" for k in MESSAGE_CATS)}

Rules:
- An ordinary personal or family message, or genuine market news without a push to act, is NOT a claim.
- Merely MENTIONING SEBI, RBI, NSE or a broker (e.g. in news) is not impersonation. Impersonation is when the
  sender claims to BE or to speak for them ("NSE Compliance Department", "assistant of a famous investor"),
  or threatens action on the reader's account.
- A bank's or app's own notification that contains an OTP and says not to share it is NOT a credential request.
- "quote" must be copied verbatim from the given line (short span). Never invent text.
- "line" is the number in square brackets of the line containing the quote.
- severity: 3 = direct risk of losing money or account access (OTP/PIN request, payment demand, guarantees,
  fake regulator), 2 = strong pressure, hype or a suspicious link, 1 = mild.
- confidence: how sure you are this really is a warning sign in context (0-1).
- why_en: one plain-English sentence explaining to the reader why this is a warning sign.
- Never judge whether a stock is good or bad, and never give investment advice.
- If nothing qualifies, return {{"claims": []}}."""


def analyse_window(segments: list[Segment], idx: list[int], hints: list[RuleHit], context: str,
                   message: bool = False) -> list[Claim]:
    fmt = (lambda t: f"line {int(t) + 1}") if message else _fmt
    lines = "\n".join(f"[{i}] ({fmt(segments[i].start)}) {segments[i].text}" for i in idx)
    hint_txt = ""
    if hints:
        hint_txt = "\n\nKeyword scanner hints (may be false positives; confirm or ignore):\n" + "\n".join(
            f"- {fmt(h.start)}: '{h.match}' -> {h.category}" for h in hints
        )
    if message:
        user = f"Message lines:\n{lines}{hint_txt}"
        data = _chat([{"role": "system", "content": MESSAGE_SYSTEM}, {"role": "user", "content": user}], MESSAGE_SCHEMA)
    else:
        user = f"Video context: {context}\n\nTranscript lines:\n{lines}{hint_txt}"
        data = _chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], CLAIM_SCHEMA)

    claims = []
    for c in data.get("claims", []):
        line = c.get("line")
        if line not in idx:
            # Model gave a bad line number: find the line that best contains the quote.
            line = max(idx, key=lambda i: _ground(c.get("quote", ""), segments[i].text))
        seg = segments[line]
        score = _ground(c.get("quote", ""), seg.text)
        if score < 70:
            # Try neighbouring lines; quotes often span a caption boundary.
            near = [j for j in (line - 1, line + 1) if j in idx]
            best = max(near, key=lambda j: _ground(c["quote"], segments[j].text), default=None)
            if best is None or _ground(c["quote"], segments[best].text) < 70:
                continue  # ungrounded: likely hallucinated
            seg = segments[best]
        if not _plausible(c):
            continue
        try:
            claims.append(Claim(
                start=seg.start, end=seg.end, quote=c["quote"].strip(), category=c["category"],
                severity=int(c["severity"]), confidence=round(float(c["confidence"]), 2),
                why_en=c["why_en"].strip(),
            ))
        except (KeyError, ValueError):
            continue
    return claims


def analyse_description(description: str, hints: list[RuleHit], context: str) -> list[Claim]:
    desc = description.strip()[:3000]
    if not desc:
        return []
    lines = [l for l in desc.splitlines() if l.strip()]
    numbered = "\n".join(f"[{i}] {l}" for i, l in enumerate(lines))
    user = (f"Video context: {context}\n\nThis is the VIDEO DESCRIPTION (not speech). "
            f"Focus on paid_promotion, paid_group, registration_claim and guaranteed_returns.\n\n{numbered}")
    data = _chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], CLAIM_SCHEMA)
    out = []
    for c in data.get("claims", []):
        if not any(_ground(c.get("quote", ""), l) >= 75 for l in lines) or not _plausible(c):
            continue
        try:
            out.append(Claim(
                start=0, end=0, quote=c["quote"].strip(), category=c["category"], severity=int(c["severity"]),
                confidence=round(float(c["confidence"]), 2), why_en=c["why_en"].strip(),
                where="description",
            ))
        except (KeyError, ValueError):
            continue
    return out


# In written messages these patterns (short links, APKs, UPI handles, "share the OTP") are objective,
# unlike paraphrased speech, so unconfirmed rule hits count with more confidence there.
OBJECTIVE_MESSAGE_RULES = {"credential_request", "suspicious_link", "upfront_payment"}


def merge(claims: list[Claim], hits: list[RuleHit], message: bool = False) -> list[Claim]:
    """Dedupe LLM claims and fold in rule hits the LLM did not cover."""
    merged: list[Claim] = []
    for c in sorted(claims, key=lambda c: (c.where, c.start, -c.severity)):
        dup = next((m for m in merged if m.category == c.category and m.where == c.where
                    and abs(m.start - c.start) < 8 and fuzz.partial_ratio(m.quote, c.quote) > 60), None)
        if dup:
            if c.confidence > dup.confidence:
                merged[merged.index(dup)] = c
            continue
        merged.append(c)

    for h in hits:
        same = next((m for m in merged if m.category == h.category and m.where == h.where
                     and (abs(m.start - h.start) < 15 or h.where == "description")), None)
        if same:
            same.origin = "llm+rules"
            # Agreement only strengthens a claim the LLM already believes; it must not
            # lift a claim the LLM judged unlikely over the display threshold.
            if same.confidence >= 0.5:
                same.confidence = round(min(1.0, same.confidence + 0.1), 2)
        elif h.severity >= 2 or h.category == "registration_claim":
            info = CATEGORIES[h.category]
            merged.append(Claim(
                start=h.start, end=h.end, quote=h.match if h.where == "transcript" else h.text[:160],
                category=h.category, severity=h.severity,
                confidence=0.6 if message and h.category in OBJECTIVE_MESSAGE_RULES else 0.4,
                why_en=info["about_en"], why_hi=info["about_hi"], origin="rules", where=h.where,
            ))
    return sorted(merged, key=lambda c: (c.where != "transcript", c.start))


def translate_hi(texts: list[str], batch: int = 6) -> list[str]:
    """Translate English sentences to simple Hindi with the Hindi model.

    Small batches keep the model from merging or dropping items; a batch that comes
    back with the wrong count is retried one sentence at a time."""
    out: list[str] = []
    for i in range(0, len(texts), batch):
        chunk = texts[i:i + batch]
        got = _translate(chunk)
        if len(got) != len(chunk):
            got = [(_translate([t]) or [""])[0] for t in chunk]
        out.extend(got)
    return out


TRANSLATE_RULES = """

Output: a JSON object {"hindi": [...]} with exactly one Hindi translation per numbered input, in the same order.
No numbering, no English, no transliteration in brackets."""


def _translate(texts: list[str]) -> list[str]:
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    data = _chat([
        {"role": "system", "content": hindi.STYLE + TRANSLATE_RULES},
        {"role": "user", "content": numbered},
    ], TRANSLATE_SCHEMA, num_predict=200 + 150 * len(texts), model=HI_MODEL)
    return [hindi.tidy(t) for t in data.get("hindi", [])]


def run(segments: list[Segment], hits: list[RuleHit], description: str, context: str,
        on_progress: Callable[[int, int], None] | None = None) -> list[Claim]:
    wins = windows(segments)
    claims: list[Claim] = []
    for n, idx in enumerate(wins):
        lo, hi = segments[idx[0]].start, segments[idx[-1]].end
        win_hits = [h for h in hits if h.where == "transcript" and lo <= h.start <= hi]
        claims.extend(analyse_window(segments, idx, win_hits, context))
        if on_progress:
            on_progress(n + 1, len(wins) + 1)
    desc_hits = [h for h in hits if h.where == "description"]
    claims.extend(analyse_description(description, desc_hits, context))
    if on_progress:
        on_progress(len(wins) + 1, len(wins) + 1)
    return merge(claims, hits)
