"""Creator trust profile: audit a channel's recent videos and summarise the pattern.

One video can be an outlier; a profile answers "should I follow this creator?" by
showing how often they give buy/sell calls, promise returns or push paid groups,
across their latest uploads, plus their registration status. Existing reports for
the same video are reused, so profiling a channel you've partly audited is fast.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from typing import Callable

from . import ingest
from .config import DATA_DIR, REPORTS_DIR
from .models import Profile, ProfileVideo, Report, WorstMoment
from .pipeline import run_audit

PROFILES_DIR = DATA_DIR / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

# Which registry verdict best describes a channel, when its videos disagree.
VERDICT_ORDER = ["verified", "matched", "number_not_found", "registered_other", "guests_registered",
                 "claimed_unverified", "possible_match", "not_registered", "unknown"]

# Categories worth naming in the headline, most serious first.
HEADLINE_CATS = ["guaranteed_returns", "stock_tip", "paid_group", "price_prediction", "paid_promotion",
                 "urgency_fomo", "misleading_claim"]
PHRASES = {
    "en": {
        "guaranteed_returns": "promises guaranteed or unrealistic returns", "stock_tip": "gives buy/sell calls",
        "paid_group": "pushes paid or Telegram groups", "price_prediction": "makes price predictions",
        "paid_promotion": "promotes paid or affiliate products", "urgency_fomo": "pressures viewers to act fast",
        "misleading_claim": "makes misleading claims",
    },
    "hi": {
        "guaranteed_returns": "गारंटीड या बहुत ज़्यादा रिटर्न का वादा करता है", "stock_tip": "खरीदने-बेचने की टिप देता है",
        "paid_group": "पेड या टेलीग्राम ग्रुप में बुलाता है", "price_prediction": "भाव का अनुमान बताता है",
        "paid_promotion": "पेड या रेफ़रल प्रोडक्ट का प्रचार करता है", "urgency_fomo": "जल्दबाज़ी का दबाव बनाता है",
        "misleading_claim": "गुमराह करने वाले दावे करता है",
    },
}
REG_PHRASE = {
    "en": {"verified": "SEBI-registered adviser/analyst", "matched": "SEBI-registered adviser/analyst",
           "registered_other": "SEBI-registered, but not as an adviser", "guests_registered": "guest experts are SEBI-registered",
           "number_not_found": "quotes a registration number that doesn't exist",
           "claimed_unverified": "claims registration without a number", "possible_match": "registration unclear",
           "not_registered": "not SEBI-registered as an adviser", "unknown": "registration not checked"},
    "hi": {"verified": "SEBI-रजिस्टर्ड सलाहकार/एनालिस्ट", "matched": "SEBI-रजिस्टर्ड सलाहकार/एनालिस्ट",
           "registered_other": "SEBI में रजिस्टर्ड, पर सलाहकार के तौर पर नहीं", "guests_registered": "गेस्ट एक्सपर्ट SEBI-रजिस्टर्ड हैं",
           "number_not_found": "ऐसा रजिस्ट्रेशन नंबर बताता है जो है ही नहीं",
           "claimed_unverified": "बिना नंबर के रजिस्ट्रेशन का दावा", "possible_match": "रजिस्ट्रेशन साफ़ नहीं",
           "not_registered": "सलाहकार के तौर पर SEBI-रजिस्टर्ड नहीं", "unknown": "रजिस्ट्रेशन जाँचा नहीं गया"},
}


def _existing_reports() -> dict[str, str]:
    """video_id -> report id, for saved public reports."""
    out = {}
    for p in sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        vid = r.get("source", {}).get("video_id")
        if vid and not r.get("private"):
            out[vid] = r["id"]
    return out


def strong_categories(report: Report) -> list[str]:
    return sorted({c.category for c in report.claims if c.confidence >= 0.5})


def headline(category_videos: dict[str, int], n: int, verdict: str, lang: str) -> str:
    named = [(c, category_videos[c]) for c in HEADLINE_CATS if category_videos.get(c)][:2]
    reg = REG_PHRASE[lang][verdict]
    if lang == "hi":
        if not named:
            return f"पिछले {n} वीडियो में कोई बड़ा खतरे का संकेत नहीं मिला; {reg}।"
        parts = " और ".join(f"{n} में से {k} वीडियो में {PHRASES['hi'][c]}" for c, k in named)
        return f"{parts}; {reg}।"
    if not named:
        return f"No major red flags across the last {n} videos; {reg}."
    parts = " and ".join(f"{PHRASES['en'][c]} in {k} of {n} videos" for c, k in named)
    return f"{parts[0].upper()}{parts[1:]}; {reg}."


def level_for(risks: list[int]) -> str:
    high_share = sum(r >= 55 for r in risks) / len(risks)
    med = statistics.median(risks)
    if med >= 55 or high_share >= 0.4:
        return "high"
    if med >= 25 or high_share > 0:
        return "medium"
    return "low"


def aggregate(channel: dict, reports: list[Report]) -> Profile:
    n = len(reports)
    videos, cat_videos = [], {}
    for pos, r in enumerate(reports):
        cats = strong_categories(r)
        for c in cats:
            cat_videos[c] = cat_videos.get(c, 0) + 1
        videos.append(ProfileVideo(
            report_id=r.id, video_id=r.source.video_id or "", title=r.source.title, position=pos,
            upload_date=r.source.upload_date, risk_score=r.risk_score, risk_level=r.risk_level,
            categories=cats, verdict=r.registry.verdict, disclaimer=r.registry.disclaimer_found,
        ))
    risks = [r.risk_score for r in reports]
    best = min(reports, key=lambda r: VERDICT_ORDER.index(r.registry.verdict))
    worst = sorted(
        ((r, c) for r in reports for c in r.claims if c.where == "transcript" and c.confidence >= 0.5),
        key=lambda rc: -(rc[1].severity * rc[1].confidence),
    )[:5]
    return Profile(
        id=channel["id"], channel=channel["name"], channel_url=channel["url"],
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        videos=videos, category_videos=cat_videos,
        avg_risk=round(sum(risks) / n, 1), median_risk=float(statistics.median(risks)), max_risk=max(risks),
        level=level_for(risks), disclaimer_rate=round(sum(v.disclaimer for v in videos) / n, 2),
        registry=best.registry,
        worst=[WorstMoment(report_id=r.id, video_title=r.source.title, start=c.start, category=c.category,
                           severity=c.severity, quote=c.quote, why_en=c.why_en, why_hi=c.why_hi) for r, c in worst],
        headline={lang: headline(cat_videos, n, best.registry.verdict, lang) for lang in ("en", "hi")},
    )


def run_profile(url: str, n: int = 8, progress: Callable[..., None] = lambda *a, **k: None) -> Profile:
    progress("fetch", 0, "Finding the channel's recent videos", "चैनल के हाल के वीडियो ढूँढे जा रहे हैं", video=0, videos=n)
    channel, items = ingest.list_channel_videos(url, n)
    have = _existing_reports()
    reports: list[Report] = []
    for i, item in enumerate(items, 1):
        def sub(stage, frac, msg, msg_hi="", _i=i, _t=item["title"]):
            progress(stage, frac, msg, msg_hi, video=_i, videos=len(items), title=_t)

        rid = have.get(item["id"])
        if rid and (REPORTS_DIR / f"{rid}.json").exists():
            sub("summary", 1, "Already audited, reusing report", "पहले से जाँचा हुआ, वही रिपोर्ट")
            reports.append(Report.model_validate_json((REPORTS_DIR / f"{rid}.json").read_text(encoding="utf-8")))
            continue
        try:
            reports.append(run_audit(f"https://www.youtube.com/watch?v={item['id']}", sub))
        except ingest.IngestError as e:
            sub("fetch", 1, f"Skipped: {e}", f"छोड़ा गया: {e}")
    if not reports:
        raise ingest.IngestError("None of the channel's recent videos could be audited.")
    profile = aggregate(channel, reports)
    (PROFILES_DIR / f"{profile.id}.json").write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return profile


def list_profiles(limit: int = 20) -> list[dict]:
    out = []
    for p in sorted(PROFILES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            pr = Profile.model_validate_json(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out.append({"id": pr.id, "channel": pr.channel, "videos": len(pr.videos), "level": pr.level,
                    "median_risk": pr.median_risk, "thumbs": [v.video_id for v in pr.videos[:3]],
                    "headline": pr.headline, "created_at": pr.created_at})
    return out

