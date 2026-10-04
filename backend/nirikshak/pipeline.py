"""End-to-end audit: ingest → transcript → rules → LLM → registry check → score → summary."""
from __future__ import annotations

import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import analyse, rules, sebi
from .config import HI_MODEL, LLM_MODEL, MAX_DURATION, REPORTS_DIR, WORK_DIR
from .ingest import IngestError, fetch_youtube, probe_duration, to_wav
from .models import Claim, RegistryCheck, Report, Source

# Progress callback: (stage, fraction 0-1, message)
Progress = Callable[[str, float, str], None]

STAGES = ["fetch", "transcribe", "scan", "analyse", "registry", "summary"]


def _noop(stage: str, frac: float, msg: str) -> None:
    pass


def check_registry(source: Source, claims: list[Claim], transcript: str) -> RegistryCheck:
    numbers = rules.find_reg_numbers(source.description, transcript, source.title)
    names = sebi.match_names(source.channel) if source.channel else []
    name_regs = {h.reg_no for h in names}
    results = {}
    for n in numbers:
        hit = sebi.lookup_number(n)
        if hit is None:
            near = sebi.near_numbers(n)
            # Accept a near match only if it is the channel's own registration,
            # or the single unambiguous candidate (then shown as 'possible match').
            own = [h for h in near if h.reg_no in name_regs]
            hit = own[0] if own else (near[0] if len(near) == 1 else None)
        results[n] = hit
    claims_reg = bool(numbers) or any(c.category == "registration_claim" for c in claims)
    disclaimers = rules.find_disclaimers(source.description, transcript)

    exact = [h for h in results.values() if h and h.score == 100]
    near = [h for h in results.values() if h and h.score < 100]
    if exact or any(h.reg_no in name_regs for h in near):
        # A near-miss number still counts when the entity it resolves to is also
        # the channel's own name: that's a typo, not a fake.
        verdict = "verified"
    elif near:
        verdict = "possible_match"
    elif numbers:
        verdict = "number_not_found"
    elif claims_reg:
        verdict = "possible_match" if names else "claimed_unverified"
    elif names:
        verdict = "possible_match"
    elif sebi.registry_size():
        verdict = "not_registered"
    else:
        verdict = "unknown"
    return RegistryCheck(
        claims_registration=claims_reg, numbers_found=numbers, number_results=results,
        name_matches=names, disclaimer_found=bool(disclaimers), disclaimer_quotes=disclaimers[:3],
        verdict=verdict,
    )


REG_EXPLAIN = {
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
    text = REG_EXPLAIN[reg.verdict].format(typo=" (the number in the video has a small typo)" if typo else "")
    for c in claims:
        if c.category == "registration_claim":
            c.why_en, c.why_hi = text, ""


def score(claims: list[Claim], reg: RegistryCheck) -> tuple[int, str]:
    """0-100. Each category contributes its top-3 claims (severity × confidence), so one
    repeated phrase cannot dominate, and several different kinds of red flag add up."""
    by_cat: dict[str, list[float]] = {}
    for c in claims:
        w = c.severity * c.confidence * 9
        if c.category == "stock_tip" and reg.verdict == "verified":
            w *= 0.5  # registered analysts may legally publish research
        if c.category == "registration_claim":
            w = 0 if reg.verdict == "verified" else (12 if reg.verdict == "number_not_found" else 3)
        by_cat.setdefault(c.category, []).append(w)
    total = sum(sum(sorted(ws, reverse=True)[:3]) for ws in by_cat.values())
    gives_tips = any(c.category in ("stock_tip", "guaranteed_returns") and c.confidence >= 0.5 for c in claims)
    if gives_tips and reg.verdict in ("not_registered", "claimed_unverified", "number_not_found"):
        total += 15
    if gives_tips and not reg.disclaimer_found:
        total += 5
    s = int(min(100, round(total)))
    return s, "high" if s >= 55 else "medium" if s >= 25 else "low"


def registry_note(reg: RegistryCheck, channel: str) -> str:
    return {
        "verified": "The creator's SEBI registration was found in SEBI's registry"
                    + (" (the number in the video has a small typo)." if any(h and h.score < 100 for h in reg.number_results.values()) else "."),
        "number_not_found": f"Quoted number(s) {', '.join(reg.numbers_found)} were NOT found in SEBI's registry.",
        "claimed_unverified": "The creator claims SEBI registration but gives no number that could be verified.",
        "possible_match": f"'{channel}' resembles a SEBI-registered entity name; this is not proof, verify the number.",
        "not_registered": f"No SEBI RA/IA registration found for '{channel}'.",
        "unknown": "SEBI registry not available offline; registration not checked.",
    }[reg.verdict]


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
        progress("fetch", 0, "Fetching video details")
        if isinstance(target, Path) or Path(str(target)).exists():
            path = Path(target)
            dur = probe_duration(path)
            if dur > MAX_DURATION:
                raise IngestError(f"File is {dur / 60:.0f} min long; the limit is {MAX_DURATION // 60} min.")
            source = Source(kind="upload", title=path.name, duration=dur)
            segments, audio = None, to_wav(path, work)
        else:
            source, segments, audio = fetch_youtube(str(target), work, want_audio=force_whisper)
        progress("fetch", 1, source.title or "Fetched")
        lap("fetch")

        # 2. Transcript
        if segments is None:
            from .transcribe import transcribe  # heavy import, only when needed

            progress("transcribe", 0, "Transcribing audio with Whisper")
            analyse.unload_models()
            segments, lang = transcribe(audio, lambda f: progress("transcribe", f, f"Transcribing… {int(f * 100)}%"))
            source.language, source.transcript_source = lang, "whisper"
            if not source.duration and segments:
                source.duration = segments[-1].end
        progress("transcribe", 1, f"{len(segments)} transcript lines ({source.transcript_source})")
        lap("transcribe")
        if not segments:
            raise IngestError("No speech found in this video.")

        # 3. Rules
        hits = rules.scan_segments(segments) + rules.scan_text(source.description)
        progress("scan", 1, f"{len(hits)} keyword hints")
        lap("scan")

        # 4. LLM
        context = f'"{source.title}" by {source.channel or "unknown"}'
        claims = analyse.run(
            segments, hits, source.description, context,
            on_progress=lambda n, total: progress("analyse", n / total, f"Analysing part {n}/{total}"),
        )
        lap("analyse")

        # 5. Registry
        progress("registry", 0, "Checking SEBI registry")
        transcript = " ".join(s.text for s in segments)
        reg = check_registry(source, claims, transcript)
        _explain_registration_claims(claims, reg)
        progress("registry", 1, registry_note(reg, source.channel))
        lap("registry")

        # 6. Score + summary
        risk, level = score(claims, reg)
        progress("summary", 0, "Writing summary")
        gives_advice = any(c.category in ("stock_tip", "guaranteed_returns", "registration_claim")
                           and c.confidence >= 0.5 for c in claims)
        # Registration status only matters to the summary when the video advises or claims to be registered.
        note = registry_note(reg, source.channel) if gives_advice or reg.verdict != "not_registered" else "not relevant"
        s_en = analyse.summarise(source.title, claims, note)
        progress("summary", 0.5, "Translating to Hindi")
        need = [c for c in claims if not c.why_hi]
        hindi = analyse.translate_hi([s_en] + [c.why_en for c in need])
        s_hi = hindi[0] if hindi else ""
        for c, h in zip(need, hindi[1:]):
            c.why_hi = h
        progress("summary", 1, "Done")
        lap("summary")

        report = Report(
            id=job_id, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            source=source, segments=segments, claims=claims, registry=reg,
            risk_score=risk, risk_level=level, summary_en=s_en, summary_hi=s_hi,
            model=f"{LLM_MODEL} + {HI_MODEL}", timings=timings,
        )
        (REPORTS_DIR / f"{job_id}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return report
    finally:
        shutil.rmtree(work, ignore_errors=True)
