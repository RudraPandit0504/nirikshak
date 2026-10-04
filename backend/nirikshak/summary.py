"""The audit brief shown at the top of a report, in the PDF, and read aloud.

To keep it accurate, the LLM writes only the headline and the overview (what
the video is about, which needs the transcript). The concerns, registration
status and advice are assembled from verified findings and the registry check,
so the summary can never state something the audit didn't find.
"""
from __future__ import annotations

from .analyse import _chat, translate_hi
from .categories import CATEGORIES
from .models import Claim, Concern, RegistryCheck, Segment, Source, Summary


def _fmt(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def _excerpt(segments: list[Segment], budget: int = 3500) -> str:
    """Evenly spaced transcript lines that fit in `budget` characters, so the LLM
    sees the whole arc of the video rather than just its opening."""
    lines = [f"({_fmt(s.start)}) {s.text}" for s in segments]
    total = sum(len(l) + 1 for l in lines)
    if total <= budget:
        return "\n".join(lines)
    step = total / budget
    out, i = [], 0.0
    while int(i) < len(lines):
        out.append(lines[int(i)])
        i += step
    return "\n".join(out)


def top_concerns(claims: list[Claim], n: int = 5) -> list[Claim]:
    """The strongest findings, one per category first so the list covers different
    kinds of problem, then filled by weight."""
    strong = sorted((c for c in claims if c.confidence >= 0.5),
                    key=lambda c: -(c.severity * c.confidence))
    picked, seen = [], set()
    for c in strong:
        if c.category not in seen:
            picked.append(c)
            seen.add(c.category)
    for c in strong:
        if len(picked) >= n:
            break
        if c not in picked:
            picked.append(c)
    return sorted(picked[:n], key=lambda c: (c.where != "transcript", c.start))


REGISTRATION = {
    "en": {
        "verified": "The creator's SEBI registration ({entity}, {reg}) was found in SEBI's official registry{typo}.",
        "number_not_found": "The registration number quoted ({nums}) does NOT exist in SEBI's registry of research analysts and investment advisers.",
        "claimed_unverified": "The creator claims to be SEBI-registered but gives no registration number that can be checked.",
        "possible_match": "A similarly named SEBI-registered entity exists ({entity}), but it could not be confirmed that it is this creator.",
        "not_registered": "No SEBI registration as a research analyst or investment adviser was found for '{channel}'.",
        "unknown": "SEBI's registry was not available, so registration was not checked.",
        "typo": " (the number written in the video has a small typo)",
        "disc_yes": " A risk disclaimer is present.",
        "disc_no": " No risk disclaimer was found in the video or its description.",
        "no_advice": " Registration only matters for creators who give buy/sell calls or promise returns, and this video does not.",
    },
    "hi": {
        "verified": "क्रिएटर का SEBI रजिस्ट्रेशन ({entity}, {reg}) SEBI की आधिकारिक सूची में मिला{typo}।",
        "number_not_found": "बताया गया रजिस्ट्रेशन नंबर ({nums}) SEBI की रिसर्च एनालिस्ट और निवेश सलाहकार सूची में मौजूद नहीं है।",
        "claimed_unverified": "क्रिएटर SEBI-रजिस्टर्ड होने का दावा करता है, लेकिन जाँचने लायक कोई रजिस्ट्रेशन नंबर नहीं देता।",
        "possible_match": "मिलते-जुलते नाम की एक SEBI-रजिस्टर्ड संस्था ({entity}) है, लेकिन यह पक्का नहीं हो सका कि यह यही क्रिएटर है।",
        "not_registered": "'{channel}' के लिए रिसर्च एनालिस्ट या निवेश सलाहकार के रूप में कोई SEBI रजिस्ट्रेशन नहीं मिला।",
        "unknown": "SEBI की सूची उपलब्ध नहीं थी, इसलिए रजिस्ट्रेशन नहीं जाँचा गया।",
        "typo": " (वीडियो में लिखे नंबर में छोटा सा टाइपो है)",
        "disc_yes": " जोखिम से जुड़ा डिस्क्लेमर मौजूद है।",
        "disc_no": " वीडियो या उसके डिस्क्रिप्शन में कोई जोखिम डिस्क्लेमर नहीं मिला।",
        "no_advice": " रजिस्ट्रेशन तभी मायने रखता है जब क्रिएटर खरीद/बिक्री की सलाह दे या रिटर्न का वादा करे, और यह वीडियो ऐसा नहीं करता।",
    },
}


def gives_advice(claims: list[Claim]) -> bool:
    return any(c.category in ("stock_tip", "guaranteed_returns", "registration_claim") and c.confidence >= 0.5
               for c in claims)


def registration_text(reg: RegistryCheck, channel: str, lang: str, advises: bool = True) -> str:
    t = REGISTRATION[lang]
    hits = [h for h in reg.number_results.values() if h] or reg.name_matches
    entity = hits[0].name if hits else ""
    reg_no = hits[0].reg_no if hits else ""
    typo = t["typo"] if any(h and h.score < 100 for h in reg.number_results.values()) else ""
    text = t[reg.verdict].format(entity=entity, reg=reg_no, typo=typo,
                                 nums=", ".join(reg.numbers_found), channel=channel or "this channel")
    if reg.verdict == "not_registered" and not advises:
        return text + t["no_advice"]
    return text + (t["disc_yes"] if reg.disclaimer_found else t["disc_no"])


ADVICE = {
    "unregistered_tips": {
        "en": "Do not trade on the buy/sell calls in this video. Only SEBI-registered research analysts or investment advisers may give them.",
        "hi": "इस वीडियो की खरीद/बिक्री की सलाह पर ट्रेड न करें। ऐसी सलाह केवल SEBI-रजिस्टर्ड रिसर्च एनालिस्ट या निवेश सलाहकार ही दे सकते हैं।",
    },
    "registered_tips": {
        "en": "The creator is registered, but a call made to a general audience is not personal advice. Check whether it suits your own goals and risk.",
        "hi": "क्रिएटर रजिस्टर्ड है, लेकिन सबके लिए दी गई सलाह आपकी निजी सलाह नहीं है। देखें कि यह आपके लक्ष्य और जोखिम के हिसाब से ठीक है या नहीं।",
    },
    "guaranteed_returns": {
        "en": "No market investment can guarantee returns. Treat any promise of fixed or 'sure' profit as a red flag.",
        "hi": "बाज़ार का कोई भी निवेश रिटर्न की गारंटी नहीं दे सकता। पक्के या 'श्योर' मुनाफे के हर वादे को खतरे का संकेत मानें।",
    },
    "price_prediction": {
        "en": "Ignore confident price targets and 'multibagger' predictions. Nobody can reliably predict prices.",
        "hi": "पक्के प्राइस टारगेट और 'मल्टीबैगर' भविष्यवाणियों को नज़रअंदाज़ करें। कीमतों का भरोसेमंद अनुमान कोई नहीं लगा सकता।",
    },
    "paid_group": {
        "en": "Think twice before paying for any group, course or membership promoted here. Many tip scams start in paid Telegram or WhatsApp groups.",
        "hi": "यहाँ प्रचारित किसी भी ग्रुप, कोर्स या मेंबरशिप के लिए पैसे देने से पहले सोचें। कई टिप-ठगी पेड टेलीग्राम या व्हाट्सऐप ग्रुप से शुरू होती हैं।",
    },
    "paid_promotion": {
        "en": "The creator may earn from the links or apps promoted here, so their recommendation may not be neutral.",
        "hi": "क्रिएटर को यहाँ प्रचारित लिंक या ऐप से कमाई हो सकती है, इसलिए उनकी सलाह निष्पक्ष न भी हो।",
    },
    "urgency_fomo": {
        "en": "Take your time. Pressure to act 'now' is a manipulation tactic; a genuine opportunity will still be there tomorrow.",
        "hi": "जल्दबाज़ी न करें। 'अभी' कदम उठाने का दबाव एक चाल है; असली मौका कल भी रहेगा।",
    },
    "fake_number": {
        "en": "A registration number that does not exist is a serious warning sign. Consider reporting the channel at cybercrime.gov.in or by calling 1930.",
        "hi": "जो रजिस्ट्रेशन नंबर मौजूद ही नहीं, वह गंभीर खतरे का संकेत है। चैनल की शिकायत cybercrime.gov.in पर या 1930 पर कॉल करके करें।",
    },
    "clean": {
        "en": "No major warning signs were found. Still, verify anyone who gives investment advice on SEBI's website before acting on it.",
        "hi": "कोई बड़ा खतरे का संकेत नहीं मिला। फिर भी, निवेश सलाह देने वाले किसी भी व्यक्ति को अमल से पहले SEBI वेबसाइट पर जाँचें।",
    },
}


def advice(claims: list[Claim], reg: RegistryCheck, lang: str) -> list[str]:
    cats = {c.category for c in claims if c.confidence >= 0.5}
    keys = []
    if reg.verdict == "number_not_found":
        keys.append("fake_number")
    if "stock_tip" in cats:
        keys.append("registered_tips" if reg.verdict == "verified" else "unregistered_tips")
    for k in ("guaranteed_returns", "price_prediction", "paid_group", "paid_promotion", "urgency_fomo"):
        if k in cats:
            keys.append(k)
    return [ADVICE[k][lang] for k in (keys or ["clean"])][:4]


HEADLINE_SCHEMA = {
    "type": "object",
    "properties": {"headline": {"type": "string"}, "overview": {"type": "string"}},
    "required": ["headline", "overview"],
}


def _write_overview(source: Source, segments: list[Segment], claims: list[Claim],
                    level: str, score: int, reg_line: str) -> tuple[str, str]:
    concerns = top_concerns(claims)
    findings = "\n".join(f"- ({_fmt(c.start)}) {CATEGORIES[c.category]['en']}: \"{c.quote[:160]}\"" for c in concerns) \
        or "- none"
    data = _chat([
        {"role": "system", "content": (
            "You write the top of an audit report about a finance video, for a first-time Indian investor.\n"
            "Return JSON with:\n"
            "- headline: ONE sentence (max 25 words) stating the risk level and the main reason, e.g. "
            "'High risk: promises guaranteed 100x crypto returns and pushes a paid Telegram group.' "
            "For low risk, say what the video is and that no major red flags were found.\n"
            "- overview: 3-4 plain sentences describing what the video is about, what the creator is "
            "pitching or teaching, and how (tone, tactics). Base it on the transcript excerpt. "
            "Be specific (topics, products, claims) and neutral.\n"
            "Rules: do not give investment advice; do not judge whether any stock or coin is good; do not "
            "invent claims that are not in the transcript or findings; no severity numbers or category codes."
        )},
        {"role": "user", "content": (
            f"Title: {source.title}\nChannel: {source.channel or 'unknown'}\n"
            f"Description (start): {source.description[:600]}\n"
            f"Audit result: {level} risk, score {score}/100. {reg_line}\n"
            f"Key findings:\n{findings}\n\nTranscript excerpt (timestamps in brackets):\n{_excerpt(segments)}"
        )},
    ], HEADLINE_SCHEMA, num_predict=500)
    return data.get("headline", "").strip(), data.get("overview", "").strip()


def build(source: Source, segments: list[Segment], claims: list[Claim], reg: RegistryCheck,
          score: int, level: str) -> dict[str, Summary]:
    advises = gives_advice(claims)
    reg_en = registration_text(reg, source.channel, "en", advises)
    headline, overview = _write_overview(source, segments, claims, level, score, reg_en)
    hi = translate_hi([headline, overview])
    concerns = top_concerns(claims)

    out = {}
    for lang, (h, o) in (("en", (headline, overview)), ("hi", (hi[0] or headline, hi[1] or overview))):
        out[lang] = Summary(
            headline=h, overview=o,
            concerns=[Concern(start=c.start, where=c.where, category=c.category, severity=c.severity,
                              quote=c.quote, why=(c.why_hi or c.why_en) if lang == "hi" else c.why_en)
                      for c in concerns],
            registration=registration_text(reg, source.channel, lang, advises),
            advice=advice(claims, reg, lang),
        )
    return out


def flat(s: Summary) -> str:
    """Single-paragraph form, used for the legacy summary_en/summary_hi fields."""
    return f"{s.headline} {s.overview} {s.registration}".strip()

