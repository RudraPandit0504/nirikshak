"""End-to-end audit: ingest → transcript → rules → LLM → registry check → score → summary."""
from __future__ import annotations

import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import analyse, identity, llm, rules, sebi, summary
from .categories import CATEGORIES
from .config import HI_MODEL, LLM_MODEL, MAX_DURATION, REPORTS_DIR, WORK_DIR
from .ingest import IngestError, fetch_youtube, ocr_image, probe_duration, to_wav
from .models import Claim, RegistryCheck, Report, Segment, Source

# Progress callback: (stage, fraction 0-1, English message, Hindi message)
Progress = Callable[..., None]

STAGES = ["fetch", "transcribe", "scan", "analyse", "registry", "summary"]


def _noop(stage: str, frac: float, msg: str, msg_hi: str = "") -> None:
    pass


def check_registry(source: Source, claims: list[Claim], segments: list[Segment]) -> RegistryCheck:
    transcript = " ".join(s.text for s in segments)
    try:
        people = identity.extract_people(source, segments)
    except analyse.LLMError:
        people = []
    checks = identity.collect_checks(source, segments, transcript, people)
    numbers = [c.query for c in checks if c.kind == "number"]
    claims_reg = bool(numbers) or any(c.category == "registration_claim" and c.confidence >= 0.5 for c in claims)
    verdict, entity = identity.verdict(checks, claims_reg)
    disclaimers = rules.find_disclaimers(source.description, transcript)
    return RegistryCheck(
        claims_registration=claims_reg,
        numbers_found=numbers,
        number_results={c.query: (c.hits[0] if c.hits else None) for c in checks if c.kind == "number"},
        name_matches=[h for c in checks if c.kind != "number" for h in c.hits][:5],
        disclaimer_found=bool(disclaimers), disclaimer_quotes=disclaimers[:3],
        verdict=verdict, checks=checks, entity=entity,
    )


ADVISER_OK = {"verified", "matched", "guests_registered"}  # a registered adviser/analyst is behind the advice
NOT_ALLOWED = {"not_registered", "claimed_unverified", "number_not_found", "registered_other"}

REG_EXPLAIN = {
    "matched": "Checked against SEBI's registry: the creator is registered as {entity_cat} ({entity}). Still check that the advice suits you.",
    "registered_other": "Checked against SEBI's registry: the creator is registered only as {entity_cat} ({entity}), which does not permit giving investment advice or tips.",
    "guests_registered": "Checked against SEBI's registry: the guest expert is registered as {entity_cat} ({entity}).",
    "verified": "Checked against SEBI's registry: this registration is real{typo}. A registered analyst may publish research, but still check that the advice suits you.",
    "number_not_found": "Checked against SEBI's registry: the number quoted does not exist there. A fake registration number is a serious warning sign.",
    "claimed_unverified": "The creator claims SEBI registration but gives no number that can be checked. Ask for it and verify it on SEBI's website.",
    "possible_match": "A similar registered entity exists, but the registration could not be confirmed. Verify the exact number on SEBI's website.",
    "not_registered": "No matching SEBI registration was found for this creator. Verify on SEBI's website before trusting the claim.",
    "unknown": "SEBI's registry was not available to check this claim.",
}


def _explain_registration_claims(claims: list[Claim], reg: RegistryCheck) -> None:
    """The LLM can't know the registry outcome, so explanations for registration claims are
    written from the check itself (and re-translated later)."""
    typo = any(h and h.score < 100 for h in reg.number_results.values())
    e = reg.entity
    text = REG_EXPLAIN[reg.verdict].format(typo=" (the number in the video has a small typo)" if typo else "",
                                           entity=e.name if e else "", entity_cat=(e.category.lower() if e else ""))
    for c in claims:
        if c.category == "registration_claim":
            c.why_en, c.why_hi = text, ""


def score(claims: list[Claim], reg: RegistryCheck) -> tuple[int, str]:
    """0-100. Each category contributes its top-3 claims (severity × confidence), so one
    repeated phrase cannot dominate, and several different kinds of red flag add up."""
    by_cat: dict[str, list[float]] = {}
    for c in claims:
        w = c.severity * c.confidence * 9
        if c.category == "stock_tip" and reg.verdict in ADVISER_OK:
            w *= 0.5  # registered analysts may legally publish research
        if c.category == "registration_claim":
            w = 0 if reg.verdict in ("verified", "matched") else (12 if reg.verdict == "number_not_found" else 3)
        by_cat.setdefault(c.category, []).append(w)
    total = sum(sum(sorted(ws, reverse=True)[:3]) for ws in by_cat.values())
    gives_tips = any(c.category in ("stock_tip", "guaranteed_returns") and c.confidence >= 0.5 for c in claims)
    if gives_tips and reg.verdict in NOT_ALLOWED:
        total += 15
    if gives_tips and not reg.disclaimer_found:
        total += 5
    s = int(min(100, round(total)))
    return s, "high" if s >= 55 else "medium" if s >= 25 else "low"


def registry_note(reg: RegistryCheck, channel: str) -> str:
    return {
        "verified": "The creator's SEBI registration was found in SEBI's registry"
                    + (" (the number in the video has a small typo)." if any(h and h.score < 100 for h in reg.number_results.values()) else "."),
        "matched": f"{reg.entity.name if reg.entity else channel} is registered with SEBI as {reg.entity.category if reg.entity else 'an adviser'}.",
        "registered_other": f"{reg.entity.name if reg.entity else channel} is registered with SEBI only as {reg.entity.category if reg.entity else 'an intermediary'}, not as an adviser.",
        "guests_registered": f"Guest expert {reg.entity.name if reg.entity else ''} is SEBI-registered.",
        "number_not_found": f"Quoted number(s) {', '.join(reg.numbers_found)} were NOT found in SEBI's registry.",
        "claimed_unverified": "The creator claims SEBI registration but gives no number that could be verified.",
        "possible_match": f"'{channel}' resembles a SEBI-registered entity name; this is not proof, verify the number.",
        "not_registered": f"No SEBI RA/IA registration found for '{channel}'.",
        "unknown": "SEBI registry not available offline; registration not checked.",
    }[reg.verdict]


def finalize(report: Report, progress: Callable[..., None] = lambda f, m, h="": None,
             retranslate: bool = False, recheck: bool = False) -> Report:
    """Score the report, fill in Hindi explanations and write the structured summary.
    Used at the end of an audit, and by `nirikshak resummarize` to upgrade saved reports."""
    if recheck:
        report.registry = check_registry(report.source, report.claims, report.segments)
    reg = report.registry
    # Re-apply current sanity checks (matters when upgrading reports made by older versions).
    report.claims = [c for c in report.claims if c.origin == "rules" or analyse._plausible(c.model_dump())]
    if retranslate:
        for c in report.claims:
            if c.origin == "rules":  # keyword findings use the hand-written category text
                c.why_en, c.why_hi = CATEGORIES[c.category]["about_en"], CATEGORIES[c.category]["about_hi"]
            else:
                c.why_hi = ""
    _explain_registration_claims(report.claims, reg)
    report.risk_score, report.risk_level = score(report.claims, reg)
    progress(0.2, "Translating findings to Hindi", "नतीजों का हिंदी अनुवाद हो रहा है")
    need = [c for c in report.claims if not c.why_hi]
    for c, h in zip(need, analyse.translate_hi([c.why_en for c in need])):
        c.why_hi = h
    progress(0.6, "Writing summary", "सारांश लिखा जा रहा है")
    report.summary = summary.build(report.source, report.segments, report.claims, reg,
                                   report.risk_score, report.risk_level)
    report.summary_en = summary.flat(report.summary["en"])
    report.summary_hi = summary.flat(report.summary["hi"])
    return report


def save(report: Report) -> None:
    (REPORTS_DIR / f"{report.id}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")


def run_audit(target: str | Path, progress: Progress = _noop, job_id: str | None = None,
              force_whisper: bool = False) -> Report:
    job_id = job_id or uuid.uuid4().hex[:12]
    work = WORK_DIR / job_id
    work.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    def lap(name: str):
        nonlocal t0
        now = time.perf_counter()
        timings[name] = round(now - t0, 2)
        t0 = now

    try:
        # 1. Ingest
        progress("fetch", 0, "Fetching video details", "वीडियो की जानकारी ली जा रही है")
        if isinstance(target, Path) or Path(str(target)).exists():
            path = Path(target)
            dur = probe_duration(path)
            if dur > MAX_DURATION:
                raise IngestError(f"File is {dur / 60:.0f} min long; the limit is {MAX_DURATION // 60} min.")
            source = Source(kind="upload", title=path.name, duration=dur)
            segments, audio = None, to_wav(path, work)
        else:
            source, segments, audio = fetch_youtube(str(target), work, want_audio=force_whisper)
        progress("fetch", 1, source.title or "Fetched", source.title or "जानकारी मिल गई")
        lap("fetch")

        # 2. Transcript
        if segments is None:
            from .transcribe import transcribe  # heavy import, only when needed

            progress("transcribe", 0, "Transcribing audio with Whisper", "Whisper से आवाज़ को टेक्स्ट में बदला जा रहा है")
            analyse.unload_models()
            segments, lang = transcribe(audio, lambda f: progress("transcribe", f, f"Transcribing… {int(f * 100)}%",
                                                                  f"टेक्स्ट बन रहा है… {int(f * 100)}%"))
            source.language, source.transcript_source = lang, "whisper"
            if not source.duration and segments:
                source.duration = segments[-1].end
        src_hi = "Whisper" if source.transcript_source == "whisper" else "YouTube कैप्शन"
        progress("transcribe", 1, f"{len(segments)} transcript lines ({source.transcript_source})",
                 f"ट्रांसक्रिप्ट की {len(segments)} लाइनें ({src_hi})")
        lap("transcribe")
        if not segments:
            raise IngestError("No speech found in this video.")

        # 3. Rules
        hits = rules.scan_segments(segments) + rules.scan_text(source.description)
        progress("scan", 1, f"{len(hits)} keyword hints", f"{len(hits)} कीवर्ड संकेत मिले")
        lap("scan")

        # 4. LLM
        context = f'"{source.title}" by {source.channel or "unknown"}'
        claims = analyse.run(
            segments, hits, source.description, context,
            on_progress=lambda n, total: progress("analyse", n / total, f"Analysing part {n}/{total}",
                                                  f"हिस्सा {n}/{total} जाँचा जा रहा है"),
        )
        lap("analyse")

        # 5. Registry
        progress("registry", 0, "Checking SEBI registry", "SEBI की सूची में जाँच हो रही है")
        reg = check_registry(source, claims, segments)
        progress("registry", 1, registry_note(reg, source.channel), summary.registration_text(reg, source.channel, "hi"))
        lap("registry")

        # 6. Score + summary
        progress("summary", 0, "Writing summary", "सारांश लिखा जा रहा है")
        report = Report(
            id=job_id, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            source=source, segments=segments, claims=claims, registry=reg,
            risk_score=0, risk_level="low", summary_en="", summary_hi="",
            model=llm.model_label(), timings=timings,
        )
        finalize(report, lambda f, m, h="": progress("summary", f, m, h))
        progress("summary", 1, "Done", "पूरा हुआ")
        lap("summary")

        save(report)
        return report
    finally:
        shutil.rmtree(work, ignore_errors=True)


MAX_MESSAGE_CHARS = 6000


def run_message_audit(text: str | None = None, image: Path | None = None, progress: Progress = _noop,
                      job_id: str | None = None, private: bool = False) -> Report:
    """Check a forwarded WhatsApp/Telegram/SMS message (pasted text or a screenshot)."""
    job_id = job_id or uuid.uuid4().hex[:12]
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    def lap(name: str):
        nonlocal t0
        now = time.perf_counter()
        timings[name] = round(now - t0, 2)
        t0 = now

    try:
        progress("fetch", 0, "Reading the message", "मैसेज पढ़ा जा रहा है")
        if image is not None:
            progress("fetch", 0.3, "Reading text from the screenshot", "स्क्रीनशॉट से टेक्स्ट पढ़ा जा रहा है")
            text = ocr_image(image)
        text = (text or "").strip()[:MAX_MESSAGE_CHARS]
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            raise IngestError("No text found in the message." if image is None else "No text could be read from the screenshot.")
        segments = [Segment(start=float(i), end=float(i + 1), text=l) for i, l in enumerate(lines)]
        source = Source(kind="message", title=lines[0][:90], description=text,
                        transcript_source=None, language=None)
        progress("fetch", 1, f"{len(lines)} lines", f"{len(lines)} लाइनें")
        lap("fetch")
        progress("transcribe", 1, "Text ready", "टेक्स्ट तैयार")

        hits = rules.scan_segments(segments, message=True)
        progress("scan", 1, f"{len(hits)} keyword hints", f"{len(hits)} कीवर्ड संकेत मिले")
        lap("scan")

        claims = []
        wins = [list(range(i, min(i + 30, len(segments)))) for i in range(0, len(segments), 30)]
        for n, idx in enumerate(wins):
            progress("analyse", n / len(wins), f"Analysing part {n + 1}/{len(wins)}", f"हिस्सा {n + 1}/{len(wins)} जाँचा जा रहा है")
            claims += analyse.analyse_window(segments, idx, [h for h in hits if h.start in idx], "", message=True)
        claims = analyse.merge(claims, hits, message=True)
        claims += identity.impersonation_findings(segments)
        progress("analyse", 1, f"{len(claims)} findings", f"{len(claims)} नतीजे")
        lap("analyse")

        progress("registry", 0, "Checking SEBI registry", "SEBI की सूची में जाँच हो रही है")
        reg = check_registry(source, claims, segments)
        progress("registry", 1, registry_note(reg, "the sender"), summary.registration_text(reg, "", "hi"))
        lap("registry")

        progress("summary", 0, "Writing summary", "सारांश लिखा जा रहा है")
        report = Report(
            id=job_id, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            source=source, segments=segments, claims=claims, registry=reg,
            risk_score=0, risk_level="low", summary_en="", summary_hi="",
            model=llm.model_label(), timings=timings, private=private,
        )
        finalize(report, lambda f, m, h="": progress("summary", f, m, h))
        progress("summary", 1, "Done", "पूरा हुआ")
        lap("summary")
        save(report)
        return report
    finally:
        if image is not None:
            shutil.rmtree(image.parent, ignore_errors=True)
