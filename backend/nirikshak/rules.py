"""Fast lexical pre-flagging.

These rules do two jobs. They give the LLM hints about where to look, and they
act as a safety net when the LLM misses an obvious phrase. Patterns cover
English, Hinglish, and Devanagari (including English words as YouTube's Hindi
auto-captions transliterate them, e.g. "टारगेट", "गारंटी").
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Segment


@dataclass(frozen=True)
class Rule:
    category: str
    severity: int
    pattern: re.Pattern


def _r(category: str, severity: int, *patterns: str) -> list[Rule]:
    return [Rule(category, severity, re.compile(p, re.IGNORECASE)) for p in patterns]


RULES: list[Rule] = [
    *_r("guaranteed_returns", 3,
        r"guarante+d?\s*(return|profit|income|payout)s?",
        r"(fixed|assured|sure)\s*(return|profit)s?|(assured|sure|guaranteed)\s*income",
        r"risk[\s-]*free\s*(return|profit|trading|income)",
        r"\bno\s*risk\b",
        r"(100|सौ)\s*(%|percent|प्रतिशत|परसेंट)\s*(safe|profit|guarantee|sure|सेफ|प्रॉफिट|गारंटी)",
        r"pac?kk?a\s*(munafa|profit|return)",
        r"(गारंटी|गारंटीड|गारंटेड)\s*(\S+\s*){0,2}(रिटर्न|प्रॉफिट|मुनाफा|कमाई|इनकम)",
        r"(पक्का|पक्की)\s*(मुनाफा|प्रॉफिट|रिटर्न|कमाई)",
        r"(पैसा|पैसे)\s*डबल|double\s*(your)?\s*(money|capital)|paisa\s*double",
        r"\b\d+\s*(%|percent)\s*(daily|per\s*day|every\s*day|weekly|monthly|a\s*month)\b",
        r"(रोज़?|डेली|हर\s*दिन|हर\s*महीने)\s*\d+\s*(%|परसेंट|प्रतिशत)",
        r"(कोई\s*नहीं\s*रोक\s*सकता|loss\s*(ho\s*hi\s*nahi|नहीं\s*होगा)|लॉस\s*(हो\s*ही\s*नहीं|नहीं\s*होगा))",
    ),
    *_r("stock_tip", 3,
        r"\b(buy|sell|accumulate|exit)\s+(\w+\s+){0,3}(at|above|below|around|near)\s*(₹|rs\.?|inr)?\s*\d",
        r"\b(target|tgt)\s*(price|of|is|:)?\s*(₹|rs\.?)?\s*\d",
        r"\bstop\s*-?\s*loss\s*(at|of|is|:)?\s*(₹|rs\.?)?\s*\d",
        r"\bentry\s*(at|price|:|around)\s*(₹|rs\.?)?\s*\d",
        r"(टारगेट|टार्गेट)\s*(\S+\s*){0,2}\d",
        r"(स्टॉप\s*लॉस|स्टॉपलॉस|एसएल)\s*(\S+\s*){0,2}\d",
        r"(खरीद\s*लो|खरीद\s*लें|बेच\s*दो|बाय\s*कर\s*(लो|लें|लीजिए)|सेल\s*कर\s*(दो|दें))",
        r"\b(must|should)\s*buy\b|\bbuy\s*(now|today|this\s*stock)\b",
    ),
    *_r("price_prediction", 2,
        r"\b(multibagger|multi-bagger|jackpot\s*stock|rocket)\b",
        r"(मल्टीबैगर|मल्टी\s*बैगर|जैकपॉट|रॉकेट)",
        r"\b(will|going\s*to|set\s*to)\s*(double|triple|10x|5x|2x|go\s*to\s*\d|hit\s*\d|reach\s*\d|cross\s*\d)",
        r"\bupper\s*circuit\b|अपर\s*सर्किट",
        r"\b\d+\s*x\s*(return|gain|stock)s?\b",
        r"(डबल|ट्रिपल|दस\s*गुना|\d+\s*गुना)\s*(हो\s*जाएगा|होगा|हो\s*जाएगी|देगा)",
    ),
    *_r("urgency_fomo", 2,
        r"\b(last\s*chance|only\s*today|today\s*only|hurry|don'?t\s*miss|before\s*it'?s\s*too\s*late|limited\s*(seats?|slots?|time|period))\b",
        r"\b(act|buy|join|invest)\s*(now|fast|immediately|right\s*now)\b",
        r"(जल्दी\s*(करो|करें|कीजिए)|आखिरी\s*मौका|सिर्फ\s*आज|मौका\s*मत\s*(छोड़ो|गंवाओ)|देर\s*मत\s*करो|छूट\s*न\s*जाए)",
        r"(abhi|अभी)\s*(invest|join|buy|इन्वेस्ट|जॉइन|ज्वाइन|बाय)",
        r"\bjaldi\s*(karo|karein|kijiye)\b|\bsirf\s*aaj\b|\bseats?\s*(are\s*)?limited\b",
    ),
    *_r("paid_promotion", 2,
        r"\b(sponsored|paid\s*partnership|in\s*collaboration\s*with|this\s*video\s*is\s*brought\s*to\s*you)\b",
        r"\b(referral|refer|affiliate|promo|coupon|discount)\s*(link|code)\b",
        r"\b(open|create)\s*(your|a|free)?\s*(demat|trading)\s*account\b.{0,60}(link|description|below)",
        r"(link|लिंक)\s*(in|डिस्क्रिप्शन|description|नीचे).{0,40}(account|अकाउंट|डीमैट)",
        r"(डीमैट|डिमैट)\s*(अकाउंट|अकाउंट्स)\s*(खोल|ओपन)",
        r"(स्पॉन्सर|स्पॉन्सर्ड|प्रमोशन|रेफरल|एफिलिएट)",
    ),
    *_r("paid_group", 2,
        r"(t\.me/|telegram\.me/|chat\.whatsapp\.com/)",
        r"\b(join|joining)\s*(my|our|the)?\s*(telegram|whatsapp|premium|vip|paid|private)\s*(group|channel|community)?",
        r"\b(premium|vip|paid)\s*(group|channel|calls?|tips?|membership|course)\b",
        r"(टेलीग्राम|व्हाट्सएप|व्हाट्सऐप|प्रीमियम|वीआईपी)\s*(ग्रुप|चैनल)",
        r"\b(mentorship|course|webinar|masterclass)\s*(fee|price|₹|rs|link|join)",
    ),
    *_r("misleading_claim", 2,
        r"(पी\s*एंड\s*एल|पीएनएल|प्रॉफिट)\s*(का\s*)?स्क्रीनशॉट",
        r"कभी\s*फेल\s*नहीं",
    ),
    *_r("registration_claim", 1,
        r"(?<!not\s)(?<!not\sa\s)(?<!non-)(?<!non\s)\bsebi[\s-]*(registered|certified|approved|authori[sz]ed)\b",
        r"(?<!not\s)(?<!not\sa\s)(?<!non-)\b(registered|certified)\s*(research\s*analyst|investment\s*advis[eo]r|ra|ria)\b",
        r"\bIN[AHZP]\s*[-:.]?\s*(?:\d[\s-]?){7,10}\d\b",
        r"(सेबी|सीबी)\s*(रजिस्टर्ड|रजिस्टर|सर्टिफाइड|अप्रूव्ड)",
    ),
]

# Message-scam patterns (forwarded WhatsApp/Telegram/SMS tips), ported from Kavach.
MESSAGE_RULES: list[Rule] = [
    # Mentioning an OTP is not asking for one ("123456 is your OTP. Do not share it."), so these
    # need an ask-verb next to the secret and no "do not / never / मत" in front of it.
    *_r("credential_request", 3,
        r"(?<!not )(?<!never )(?<!n't )\b(share|send|tell|give|forward|enter|provide|type|confirm)\s+(\w+\s+){0,3}(otp|upi\s*pin|m?pin|cvv|password)\b",
        r"\b(otp|upi\s*pin|m?pin|cvv|password)\s+(\w+\s+){0,2}(share|send|bhej|batao|bataiye|bata\s*do|de\s*do|dijiye|enter)\b",
        r"\b(anydesk|teamviewer|quick\s*support|rustdesk|airdroid)\b",
        r"\bscreen\s*shar(e|ing)\b",
        r"(ओटीपी|पिन|पासवर्ड)\s*(\S+\s*){0,2}(बताइए|बताएं|बताओ|बता\s*दें|भेजें|भेजो|शेयर\s*करें|दीजिए)",
    ),
    *_r("suspicious_link", 2,
        r"\.apk\b",
        r"\b(bit\.ly|tinyurl\.com|cutt\.ly|rb\.gy|shorturl\.at|is\.gd|t\.ly|tiny\.cc|ow\.ly)/",
        r"\b(download|install)\s+(this|our|the|my)?\s*(app|application|apk)\b",
        r"(ऐप|एप)\s*(डाउनलोड|इंस्टॉल)\s*(करें|करो|कीजिए)",
        r"\bclick\s*(here|this\s*link|the\s*link|below)\b",
    ),
    *_r("upfront_payment", 3,
        r"\b(registration|joining|membership|activation|processing|withdrawal|unlock|gst|tax)\s*(fee|fees|charge|charges|amount)\b",
        r"\b(pay|send|transfer|deposit)\s*(₹|rs\.?|inr)?\s*\d[\d,]*\s*(to|on|via|first|now)?",
        r"\b(upi\s*id|qr\s*code|scan\s*(the|this)?\s*qr)\b",
        r"[\w.-]+@(ybl|okaxis|okhdfcbank|oksbi|okicici|paytm|ibl|axl|upi|apl)\b",
        r"(फ़ीस|फीस|शुल्क)\s*(जमा|भरें|भेजें|दें)|(पैसे|रुपये)\s*(भेजें|भेजो|जमा\s*करें)",
    ),
    *_r("impersonation", 2,
        r"\b(from|by|on behalf of)\s+(sebi|nse|bse|nsdl|cdsl|rbi)\b",
        r"\b(sebi|nse|bse|nsdl|cdsl)\s*(official|officer|department|team|notice|helpdesk|support)\b",
        r"\b(kyc)\s*(update|expired?|pending|verification|suspended)\b|\bupdate\s*(your)?\s*kyc\b",
        r"\b(demat|trading|bank)?\s*account\s*(will\s*be\s*)?(blocked|suspended|frozen|closed|deactivated)\b",
        r"(खाता|अकाउंट)\s*(बंद|ब्लॉक|सस्पेंड)\s*(हो\s*जाएगा|कर\s*दिया\s*जाएगा)|केवाईसी\s*(अपडेट|एक्सपायर)",
        r"\b(institutional|fpi|qib)\s*(account|quota|trading)\b",
    ),
]

DISCLAIMER_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"\bnot\s*(a\s*)?sebi\s*registered\b",
    r"\b(for\s*)?educational\s*purposes?\s*only\b",
    r"\bnot\s*(a\s*)?(financial|investment)\s*advice\b",
    r"\b(do\s*your\s*own\s*research|dyor)\b",
    r"\bconsult\s*(your|a)\s*(financial\s*)?(advisor|adviser)\b",
    r"\binvestments?\s*(in\s*(the\s*)?securities\s*market\s*)?(are|is)\s*subject\s*to\s*market\s*risks?\b",
    r"(शैक्षिक|एजुकेशनल)\s*(उद्देश्य|पर्पस)",
    r"(सलाह|एडवाइस)\s*नहीं\s*है",
    r"(अपनी\s*रिसर्च|खुद\s*रिसर्च)",
    r"(बाजार|मार्केट)\s*(जोखिम|रिस्क)\s*के\s*(अधीन|सब्जेक्ट)",
)]

# Real numbers have 9 digits, but creators often mistype them, so accept 8-10 and let
# the registry lookup decide (exact match or near match).
# SEBI prefixes: INA adviser, INH research analyst, INZ/INB/INF broker, INP portfolio manager,
# INM merchant banker. Digits are sometimes written in groups ("INH 000 012 345").
REG_NO = re.compile(r"\b(IN[AHZPMBF])\s*[-:.]?\s*((?:\d[\s-]?){7,10}\d)\b", re.IGNORECASE)


@dataclass
class RuleHit:
    category: str
    severity: int
    start: float
    end: float
    text: str
    match: str
    where: str = "transcript"


def scan_segments(segments: list[Segment], message: bool = False) -> list[RuleHit]:
    rules = RULES + MESSAGE_RULES if message else RULES
    hits: list[RuleHit] = []
    for seg in segments:
        seen = set()
        for rule in rules:
            if rule.category in seen:
                continue
            if m := rule.pattern.search(seg.text):
                seen.add(rule.category)
                hits.append(RuleHit(rule.category, rule.severity, seg.start, seg.end, seg.text, m.group(0)))
    return hits


def scan_text(text: str, where: str = "description") -> list[RuleHit]:
    hits: list[RuleHit] = []
    for line in text.splitlines():
        seen = set()
        for rule in RULES:
            if rule.category in seen:
                continue
            if m := rule.pattern.search(line):
                seen.add(rule.category)
                hits.append(RuleHit(rule.category, rule.severity, 0, 0, line.strip(), m.group(0), where))
    return hits


def find_disclaimers(*texts: str) -> list[str]:
    found = []
    for text in texts:
        for p in DISCLAIMER_PATTERNS:
            if m := p.search(text):
                lo = max(0, m.start() - 40)
                found.append(text[lo:m.end() + 40].strip())
    return found


def find_reg_numbers(*texts: str) -> list[str]:
    out = []
    for text in texts:
        for m in REG_NO.finditer(text):
            digits = re.sub(r"\D", "", m.group(2))
            if not 8 <= len(digits) <= 10:
                continue
            reg = f"{m.group(1).upper()}{digits}"
            if reg not in out:
                out.append(reg)
    return out
