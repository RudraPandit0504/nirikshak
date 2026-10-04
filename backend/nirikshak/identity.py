"""Who is behind a video, and are they SEBI-registered?

The channel name is often not the registered name (a channel called "Evening
Investors" features guest analysts; "CA Rachana Phadke Ranade" may be registered
under a company name), so we collect several identities and look each one up:

1. registration numbers quoted anywhere (strongest evidence);
2. the channel name;
3. people/companies the LLM finds presenting, owning the channel or appearing as
   guest experts (each must be found verbatim in the text, or it is dropped);
4. the creator's own website / e-mail domain, matched against the domains SEBI
   lists for each registered entity. Only domains that look like the creator's own
   (e.g. iamrakeshbansal.com for "Rakesh Bansal") are used, so an affiliate link
   to a broker doesn't make the creator "a broker".
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from . import rules, sebi
from .analyse import _chat
from .models import IdentityCheck, RegistryHit, Segment, Source

PLATFORMS = {
    "youtube.com", "youtu.be", "instagram.com", "facebook.com", "fb.com", "twitter.com", "x.com", "t.me",
    "telegram.me", "telegram.org", "whatsapp.com", "wa.me", "linkedin.com", "google.com", "goo.gl", "bit.ly",
    "tinyurl.com", "amzn.to", "amazon.in", "amazon.com", "flipkart.com", "spotify.com", "apple.com", "play.google.com",
    "threads.net", "discord.gg", "discord.com", "medium.com", "substack.com", "linktr.ee", "forms.gle", "paypal.com",
    "razorpay.com", "rzp.io", "cutt.ly", "rb.gy", "pfrda.org.in", "sebi.gov.in", "nseindia.com", "bseindia.com",
}

URL_OR_MAIL = re.compile(r"(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?|[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)


def own_domains(description: str, names: list[str]) -> list[str]:
    """Domains in the description that look like the creator's own site."""
    keys = {t for n in names for t in sebi._norm(n).split() if len(t) >= 5}
    keys |= {sebi._norm(n).replace(" ", "") for n in names if len(sebi._norm(n).replace(" ", "")) >= 5}
    out = []
    for m in URL_OR_MAIL.finditer(description):
        d = sebi.domain_of(m.group(0))
        if not d or "." not in d or d in PLATFORMS or d in sebi.FREE_MAIL or d in out:
            continue
        label = d.split(".")[0]
        if any(k in label or (len(label) >= 5 and label in k) for k in keys):
            out.append(d)
    return out


PEOPLE_SCHEMA = {
    "type": "object",
    "properties": {"people": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "as_written": {"type": "string"},
            "role": {"type": "string", "enum": ["owner", "speaker", "guest", "company"]},
        },
        "required": ["name", "as_written", "role"],
    }}},
    "required": ["people"],
}

INTRO = re.compile(r"(my name|i am|i'm|this is|welcome|joining us|guest|expert|analyst|मेरा नाम|मैं हूँ|मैं हूं|"
                   r"स्वागत|हमारे साथ|एक्सपर्ट|एनालिस्ट)", re.I)


def _context(source: Source, segments: list[Segment]) -> str:
    opening = [s.text for s in segments if s.start < 120]
    intros = [s.text for s in segments if s.start >= 120 and INTRO.search(s.text)][:15]
    return " ".join(opening + intros)[:3000]


def extract_people(source: Source, segments: list[Segment]) -> list[dict]:
    transcript = _context(source, segments)
    data = _chat([
        {"role": "system", "content": (
            "From a finance video's or message's details, list the people or companies who OWN or RUN the channel "
            "or SENT the message, who are "
            "SPEAKING/presenting, or who appear as GUEST experts giving views. Do NOT list companies or stocks "
            "being discussed, brokers or apps merely promoted, or famous people only mentioned in passing.\n"
            "For each: name = the name in English letters (transliterate Hindi names, e.g. राकेश बंसल → Rakesh Bansal); "
            "as_written = the name exactly as it appears in the text; role = owner | speaker | guest | company. "
            "At most 6. If none are identifiable, return an empty list."
        )},
        {"role": "user", "content": (
            f"Channel: {source.channel}\nTitle: {source.title}\n"
            f"Description:\n{source.description[:2000]}\n\nTranscript (opening and introductions):\n{transcript}"
        )},
    ], PEOPLE_SCHEMA, num_predict=400)
    text = f"{source.channel}\n{source.title}\n{source.description}\n{transcript}".lower()
    out, seen = [], set()
    for p in data.get("people", []):
        name, written = (p.get("name") or "").strip(), (p.get("as_written") or "").strip()
        role = p.get("role", "speaker")
        if len(sebi._norm(name)) < 4 or sebi._norm(name) in seen or re.search(r"\d", name):
            continue
        if role in ("speaker", "guest") and len(sebi._norm(name).split()) < 2:
            continue  # a person needs at least first + last name to be looked up safely
        # Grounding: the name must really be in the video's text.
        if fuzz.partial_ratio(written.lower(), text) < 90 and fuzz.partial_ratio(name.lower(), text) < 90:
            continue
        seen.add(sebi._norm(name))
        where = "description" if written.lower() in source.description.lower() else \
            "title" if written.lower() in source.title.lower() else "transcript"
        out.append({"name": name, "role": role, "source": where})
    return out


def collect_checks(source: Source, segments: list[Segment], transcript: str,
                   people: list[dict] | None = None) -> list[IdentityCheck]:
    checks: list[IdentityCheck] = []

    # 1. Numbers
    numbers = rules.find_reg_numbers(source.description, transcript, source.title)
    owner_names = [source.channel] + [p["name"] for p in (people or []) if p["role"] in ("owner", "speaker", "company")]
    owner_regs = {h.reg_no for n in owner_names if n for h in sebi.match_name(n)}
    for n in numbers:
        hit = sebi.lookup_number(n)
        hits = [hit] if hit else []
        if not hits:
            near = sebi.near_numbers(n)
            own = [h for h in near if h.reg_no in owner_regs]
            # A near match counts only if it is the creator's own registration, or unambiguous.
            hits = own[:1] or (near if len(near) == 1 else [])
        src = "description" if n[3:] in re.sub(r"\D", "", source.description) or n in source.description.upper() else "transcript"
        checks.append(IdentityCheck(query=n, kind="number", role="number", source=src, hits=hits))

    # 2. Channel name
    if source.channel:
        checks.append(IdentityCheck(query=source.channel, kind="name", role="channel", source="channel",
                                    hits=sebi.match_name(source.channel)))

    # 3. People and companies found by the LLM
    for p in people or []:
        if sebi._norm(p["name"]) == sebi._norm(source.channel):
            continue
        checks.append(IdentityCheck(query=p["name"], kind="name", role=p["role"], source=p["source"],
                                    hits=sebi.match_name(p["name"])))

    # 4. The creator's own website / e-mail domain
    for d in own_domains(source.description, [n for n in owner_names if n]):
        checks.append(IdentityCheck(query=d, kind="domain", role="website", source="description",
                                    hits=sebi.match_domain(d)))
    return checks


CREATOR_ROLES = {"number", "channel", "owner", "speaker", "company", "website"}


def verdict(checks: list[IdentityCheck], claims_registration: bool) -> tuple[str, RegistryHit | None]:
    """Decide what the registry says about the creator. Returns (verdict, entity)."""
    advice = sebi.ADVICE_CATEGORIES
    nums = [c for c in checks if c.kind == "number"]
    creator = [c for c in checks if c.role in CREATOR_ROLES and c.kind != "number"]
    guests = [c for c in checks if c.role == "guest"]

    # Quoted numbers are the strongest evidence.
    for c in nums:
        for h in c.hits:
            if h.category in advice and (h.how == "number" or
                                         any(h.reg_no == x.reg_no for cc in creator for x in cc.hits)):
                return "verified", h
    num_hits = [h for c in nums for h in c.hits]
    if nums and not num_hits:
        return "number_not_found", None

    def strong(h: RegistryHit) -> bool:
        return h.how == "domain" or h.score >= 100 or (h.how in ("name", "contact_person") and h.score >= 94)

    creator_hits = sorted((h for c in creator for h in c.hits), key=sebi.rank)
    adviser = [h for h in creator_hits if h.category in advice and strong(h)]
    if adviser:
        return "matched", adviser[0]
    other = [h for h in creator_hits + num_hits if h.category not in advice and strong(h)]
    if other:
        return "registered_other", other[0]
    guest_adv = sorted((h for c in guests for h in c.hits if h.category in advice and strong(h)), key=sebi.rank)
    if guest_adv:
        return "guests_registered", guest_adv[0]
    weak = [h for h in creator_hits + num_hits]
    if weak:
        return "possible_match", weak[0]
    if claims_registration:
        return "claimed_unverified", None
    return ("not_registered", None) if sebi.registry_size() else ("unknown", None)



# Official web domains of entities scammers most often impersonate. A message that uses one of
# these names but links elsewhere is a strong impersonation signal.
OFFICIAL_DOMAINS = {
    "zerodha": {"zerodha.com", "kite.trade"}, "groww": {"groww.in"}, "upstox": {"upstox.com"},
    "angel one": {"angelone.in", "angelbroking.com"}, "icici direct": {"icicidirect.com"},
    "hdfc securities": {"hdfcsec.com"}, "kotak securities": {"kotaksecurities.com"},
    "paytm money": {"paytmmoney.com"}, "5paisa": {"5paisa.com"}, "motilal oswal": {"motilaloswal.com"},
    "sharekhan": {"sharekhan.com"}, "dhan": {"dhan.co"},
    "sebi": {"sebi.gov.in"}, "nse": {"nseindia.com"}, "bse": {"bseindia.com"},
    "nsdl": {"nsdl.co.in", "nsdl.com"}, "cdsl": {"cdslindia.com"}, "rbi": {"rbi.org.in"},
}


def impersonation_findings(segments: list[Segment]) -> list:
    """Message names a well-known broker/regulator but links to a domain that isn't theirs."""
    from .models import Claim

    text = " ".join(s.text for s in segments).lower()
    brands = [b for b in OFFICIAL_DOMAINS if re.search(rf"\b{re.escape(b)}\b", text)]
    if not brands:
        return []
    official = set().union(*(OFFICIAL_DOMAINS[b] for b in brands))
    out = []
    for seg in segments:
        for m in URL_OR_MAIL.finditer(seg.text):
            # Skip e-mail addresses and UPI handles (kyc.help@ybl): the part before "@" is not a website.
            if "@" in m.group(0) or seg.text[m.end():m.end() + 1] == "@":
                continue
            d = sebi.domain_of(m.group(0))
            if not d or "." not in d or d in official:
                continue
            names = ", ".join(b.upper() if len(b) <= 4 else b.title() for b in brands)
            out.append(Claim(
                start=seg.start, end=seg.end, quote=m.group(0)[:120], category="impersonation", severity=3,
                confidence=0.85, origin="rules", where="transcript",
                why_en=(f"The message uses the name {names} but links to {d}, which is not their official website "
                        f"({', '.join(sorted(official))}). This is a common impersonation trick."),
                why_hi=(f"मैसेज में {names} का नाम है, लेकिन लिंक {d} का है, जो उनकी आधिकारिक वेबसाइट "
                        f"({', '.join(sorted(official))}) नहीं है। नकली पहचान से ठगी का यह आम तरीका है।"),
            ))
    return out
