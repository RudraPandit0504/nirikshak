"""Ask questions about an audited video (or message), answered from its transcript.

1. One LLM call classifies the question and rewrites it as English + Hindi/Hinglish
   search keywords, so an English question can find Hindi speech and vice versa.
2. BM25 (implemented here; no embedding model needed) picks the most relevant
   transcript windows.
3. The LLM answers from those windows plus the audit's findings and registry check,
   citing line numbers. Citations are checked against the retrieved lines; anything
   that doesn't exist is dropped.

Questions asking for investment advice ("should I buy X?") are refused, and the answer
points to what the video claimed and whether the speaker is registered.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Literal

from pydantic import BaseModel

from .analyse import _chat, translate_hi
from .categories import CATEGORIES
from .models import Report

WINDOW = 45  # seconds of transcript per retrieval unit
TOP_K = 5

TOKEN = re.compile(r"[^\s.,!?।|\"'“”‘’()\[\]{}:;/\\…-]+")
STOP = set("""a an the is are was were be been to of in on for and or but if it this that these those with as at by from
do does did not no yes i you he she they we what which who how why when where can could should would will about
me my your his her their our there here than then so very just also only any some all into out up down over
है हैं था थी थे को का की के में से पर और या भी तो ही यह वह ये वो क्या कैसे क्यों कब कहाँ कौन मैं आप हम नहीं हाँ एक""".split())


class Citation(BaseModel):
    line: int
    start: float
    quote: str


class Answer(BaseModel):
    answer: str
    answer_en: str  # the model's English answer; clients send this back as history
    kind: Literal["video", "general", "refused"]
    citations: list[Citation]


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


def _windows(report: Report) -> list[list[int]]:
    """Group segment indices into ~WINDOW-second windows (messages: 3 lines each)."""
    segs = report.segments
    size = 3 if report.source.kind == "message" else None
    out: list[list[int]] = []
    for i, s in enumerate(segs):
        if not out or (len(out[-1]) >= size if size else s.start - segs[out[-1][0]].start >= WINDOW):
            out.append([])
        out[-1].append(i)
    return out


def bm25(query: list[str], docs: list[list[str]], k1: float = 1.4, b: float = 0.75) -> list[float]:
    n = len(docs)
    if not n or not query:
        return [0.0] * n
    avg = sum(len(d) for d in docs) / n or 1
    df = Counter(t for d in docs for t in set(d))
    scores = []
    for d in docs:
        tf = Counter(d)
        s = 0.0
        for q in set(query):
            if q not in tf:
                continue
            idf = math.log(1 + (n - df[q] + 0.5) / (df[q] + 0.5))
            s += idf * tf[q] * (k1 + 1) / (tf[q] + k1 * (1 - b + b * len(d) / avg))
        scores.append(s)
    return scores


def retrieve(report: Report, query: list[str], k: int = TOP_K) -> list[int]:
    """Segment indices of the best-matching windows, in transcript order."""
    wins = _windows(report)
    docs = [tokens(" ".join(report.segments[i].text for i in w)) for w in wins]
    scores = bm25(query, docs)
    best = sorted(range(len(wins)), key=lambda i: -scores[i])[:k]
    best = [i for i in best if scores[i] > 0] or best[:2]  # always give the model something
    return sorted(i for w in best for i in wins[w])


# Asking what *I* should do, or what a price *will* do, is a request for advice. The LLM's own
# classification over-refused factual questions ("which stock does he recommend?"), so the
# refusal decision is made by these patterns, not by the model.
ADVICE_RE = re.compile(
    r"\b(should|shall|must)\s+(i|we)\s+(\w+\s+){0,2}(buy|sell|invest|hold|trade|exit|book|put|keep|add|accumulate|enter)\b|\b(can|could|would)\s+(i|we)\s+(buy|sell|invest|earn|make money|double)\b|\bis it (good|safe|wise|right|worth)\b|\bworth (buying|investing)\b|"
    r"\b(will|would|is going to|gonna)\b.{0,40}\b(double|triple|rise|go up|fall|crash|reach|hit|give returns?|multibagger)\b|"
    r"\b(good|best|right) (stock|coin|share|time) to (buy|sell|invest)\b|\bshould (one|people|investors) (buy|sell|invest)\b|"
    r"\b(kya|kyaa)\s+(mujhe|main|hum|hame|hamein)\b.{0,40}\b(khareed|kharid|bech|invest|paisa\s*laga)|"
    r"\b(khareed|kharid|bech)(na|u|e|en)?\s+(chahiye|lu|loon|du|doon)\b|"
    r"क्या\s+(मुझे|मैं|हम|हमें).{0,40}(खरीद|बेच|निवेश|इन्वेस्ट|पैसा\s*लगा|पैसे\s*लगा)|"
    r"(खरीद|बेच|निवेश कर)(ना|ूँ|ूं|ें)?\s+(चाहिए|लूँ|लूं|दूँ|दूं)|"
    r"(डबल|ऊपर|बढ़|गिर)\S*\s+(होगा|होगी|जाएगा|जाएगी)",
    re.I,
)

# "General explanation" only for genuine concept questions, not "did *he* say…".
CONCEPT_RE = re.compile(r"^\s*(what\s+(is|are|does)|what's|explain|meaning of|define|how does .{0,30} work)\b|"
                        r"(क्या होता है|क्या होती है|क्या है\s*\??$|का मतलब|समझाइए|समझाओ|kya hota hai|matlab)", re.I)
PERSONAL_RE = re.compile(r"\b(he|she|they|him|his|her|their|creator|video|speaker|channel)\b|(इसने|इन्होंने|उसने|वीडियो|क्रिएटर)", re.I)

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["video", "general"]},
        "keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["kind", "keywords"],
}

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "cited_lines": {"type": "array", "items": {"type": "integer"}},
        "found": {"type": "boolean"},
    },
    "required": ["answer", "cited_lines", "found"],
}


def plan(question: str) -> tuple[str, list[str]]:
    data = _chat([
        {"role": "system", "content": (
            "Classify a user's question about a finance video and produce search keywords.\n"
            "kind: 'video' = about what the video or creator said, recommended or did, who they are, or what the "
            "audit found (including registration); 'general' = asks to explain a finance concept in general "
            "(e.g. 'what is a stop-loss?', 'what does SEBI do?').\n"
            "keywords: 6-12 search words covering the question in English AND in Hindi (Devanagari) AND Hinglish, "
            "including synonyms a speaker might use (e.g. guaranteed, guarantee, पक्का, गारंटी, pakka)."
        )},
        {"role": "user", "content": question},
    ], PLAN_SCHEMA, num_predict=200)
    kind = "general" if (CONCEPT_RE.search(question) and not PERSONAL_RE.search(question)) else "video"
    if ADVICE_RE.search(question):
        kind = "advice"
    return kind, [k for k in data.get("keywords", []) if isinstance(k, str)][:15]


def evidence_lines(report: Report, limit: int = 8) -> list[int]:
    """Segment indices of the strongest findings, so the model can cite them even when
    retrieval misses (auto-captions often garble the exact words)."""
    by_start = {s.start: i for i, s in enumerate(report.segments)}
    strong = sorted((c for c in report.claims if c.where == "transcript" and c.confidence >= 0.5),
                    key=lambda c: -(c.severity * c.confidence))
    return [by_start[c.start] for c in strong if c.start in by_start][:limit]


def _fmt(t: float, message: bool) -> str:
    return f"line {int(t) + 1}" if message else f"{int(t // 60)}:{int(t % 60):02d}"


def _context(report: Report, lines: list[int]) -> str:
    msg = report.source.kind == "message"
    s = report.summary.get("en") if report.summary else None
    findings = "\n".join(
        f"- ({_fmt(c.start, msg) if c.where == 'transcript' else 'description'}) "
        f"{CATEGORIES[c.category]['en']}: \"{c.quote[:140]}\""
        for c in report.claims if c.confidence >= 0.5
    )[:2500] or "- none"
    transcript = "\n".join(f"[L{i}] ({_fmt(report.segments[i].start, msg)}) {report.segments[i].text}" for i in lines)
    head = (f"Forwarded message (WhatsApp/Telegram/SMS), {len(report.segments)} lines\n" if msg else
            f"Video: \"{report.source.title}\" by {report.source.channel or 'unknown'}\n")
    return (
        head +
        f"Audit: risk {report.risk_score}/100 ({report.risk_level}).\n"
        f"Summary: {(s.headline + ' ' + s.overview) if s else report.summary_en}\n"
        f"SEBI registration check: {s.registration if s else report.registry.verdict}\n"
        f"Audit findings:\n{findings}\n\n"
        f"Relevant {'message' if msg else 'transcript'} lines:\n{transcript}"
    )


ANSWER_RULES = {
    "video": ("Answer the question using ONLY the transcript lines and audit facts given. Describing what the "
              "creator recommended or claimed is fine: that is reporting, not advice. Cite the [L#] numbers of the "
              "lines that support your answer in cited_lines. If the material does not answer the question, say so "
              "plainly, set found=false and leave cited_lines empty. 2-3 short sentences."),
    "general": ("The user asks to explain a finance concept. Give a short, neutral, beginner-friendly explanation "
                "(2-3 short sentences, no jargon). If the video mentions it, add one sentence on what the video said and "
                "cite those [L#] lines; otherwise cited_lines is empty. Never give buy/sell advice."),
    "advice": ("The user is asking for investment advice or a prediction. You must NOT give it: do not say whether to "
               "buy, sell, hold or invest, and do not predict prices. Instead, in 2-4 sentences: say you can't advise "
               "on that, state what the video claimed about it (cite [L#] lines) and the SEBI registration result, "
               "and suggest consulting a SEBI-registered investment adviser."),
}


LINE_REF = re.compile(r"\s*\[?\(?\bL\d+(?:\s*[-–,]\s*L?\d+)*\]?\)?")


def clean_answer(text: str) -> str:
    """Drop internal line references ([L12], L1-L4) and any JSON the model leaked into the text."""
    text = re.split(r'[{}]|"?cited_lines"?', text)[0]
    text = LINE_REF.sub("", text)
    text = re.sub(r"\(\s*\)|\[\s*\]", "", text)
    text = re.sub(r"\s+([.,;:।])", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip(" ,")


def ask(report: Report, question: str, lang: str = "en", history: list[dict] | None = None) -> Answer:
    question = question.strip()[:500]
    kind, keywords = plan(question)
    lines = sorted(set(retrieve(report, tokens(question) + tokens(" ".join(keywords)), k=4))
                   | set(evidence_lines(report)))

    messages = [{"role": "system", "content": (
        ("You are Nirikshak's assistant. You help someone understand a WhatsApp/Telegram/SMS message they received, "
         "which has been checked for fraud. The transcript lines are the message's lines. Safety advice is welcome: "
         "e.g. never share OTP/PIN, don't click unknown links or install apps, don't pay fees to UPI IDs, verify via "
         "official websites, call 1930 if money was lost. Be factual, calm and simple. "
         if report.source.kind == "message" else
         "You are Nirikshak's assistant. You help first-time Indian investors understand a finance video that has "
         "been audited for investor-protection risks. Be factual, calm and simple. ") + ANSWER_RULES[kind] +
        " Never mention line numbers like [L5] in the answer text; put them only in cited_lines. You may mention "
        "timestamps like 3:54. Always write the answer in English, even if the question or transcript is in Hindi "
        "(it is translated afterwards)."
    )}, {"role": "user", "content": _context(report, lines)}]
    for h in (history or [])[-6:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("text"), str):
            messages.append({"role": h["role"], "content": h["text"][:800]})
    messages.append({"role": "user", "content": f"Question: {question}"})
    data = _chat(messages, ANSWER_SCHEMA, num_predict=320)
    answer = clean_answer(data.get("answer") or "")
    if not answer and history:  # rare empty reply: retry once without the conversation
        data = _chat(messages[:2] + messages[-1:], ANSWER_SCHEMA, num_predict=320)
        answer = clean_answer(data.get("answer") or "")
    allowed = set(lines)
    cites = []
    for n in data.get("cited_lines", []):
        if isinstance(n, int) and n in allowed and n not in {c.line for c in cites}:
            seg = report.segments[n]
            cites.append(Citation(line=n, start=seg.start, quote=seg.text[:200]))
    out_kind = "refused" if kind == "advice" else kind
    if kind == "video" and (not data.get("found", True) or not answer):
        cites = []  # nothing in the video supports it
    if not answer:
        answer = ("Sorry, I couldn't produce an explanation. Please try asking again." if kind == "general"
                  else "I couldn't find that in this video.")
    answer_en = answer
    if lang == "hi":
        answer = (translate_hi([answer]) or [answer])[0] or answer
    return Answer(answer=answer, answer_en=answer_en, kind=out_kind, citations=cites[:4])
