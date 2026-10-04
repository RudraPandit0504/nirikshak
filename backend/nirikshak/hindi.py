"""Hindi style guide shared by the translation prompt and the hand-written UI text.

Target reader: a first-time investor in a Tier-2/3 city. Use everyday spoken Hindi
(the Hindi of news channels and fintech apps), not textbook or government Hindi.
Common English finance words stay English, written in Devanagari, because that is
how people actually say them ("रिटर्न", not "प्रतिफल"; "ग्रुप", not "समूह").
"""

# English term → the Hindi to use. Keep in sync with frontend/src/i18n.ts.
GLOSSARY = {
    "guaranteed returns": "गारंटीड रिटर्न",
    "returns / profit": "रिटर्न / मुनाफा",
    "high returns": "बड़ा रिटर्न / भारी मुनाफा",
    "creator / speaker / presenter": "क्रिएटर",
    "viewers": "दर्शक",
    "paid group": "पेड ग्रुप",
    "group / community": "ग्रुप",
    "membership / subscription": "मेंबरशिप / सब्सक्रिप्शन",
    "course": "कोर्स",
    "mentorship": "मेंटरशिप",
    "penny stock": "पेनी स्टॉक",
    "watchlist": "वॉचलिस्ट",
    "paid promotion / sponsored": "पेड प्रमोशन / स्पॉन्सर्ड",
    "affiliate / referral link": "रेफ़रल लिंक",
    "commission": "कमीशन",
    "buy/sell call / stock tip": "खरीदने-बेचने की टिप",
    "recommend": "सलाह देना / सुझाना",
    "price target": "टारगेट प्राइस",
    "stop-loss": "स्टॉप-लॉस",
    "price prediction": "भाव का अनुमान",
    "urgency / FOMO": "जल्दबाज़ी का दबाव",
    "misleading": "गुमराह करने वाला",
    "registered / registration": "रजिस्टर्ड / रजिस्ट्रेशन",
    "research analyst": "रिसर्च एनालिस्ट",
    "investment adviser": "इन्वेस्टमेंट एडवाइज़र",
    "disclaimer": "डिस्क्लेमर",
    "risk": "जोखिम",
    "investor": "निवेशक",
    "investment": "निवेश",
    "account / demat account": "खाता / डीमैट खाता",
    "red flag / warning sign": "खतरे का संकेत",
    "fraud / scam": "धोखाधड़ी / ठगी",
    "description (of a video)": "डिस्क्रिप्शन",
    "fees": "फ़ीस",
}

def tidy(text: str) -> str:
    """Fix small spacing slips in model output, e.g. 'केPenny' → 'के Penny'."""
    import re

    text = re.sub(r"([\u0900-\u097F])([A-Za-z])", r"\1 \2", text)
    return re.sub(r"\s{2,}", " ", text).strip()


# Words that mark stiff, word-for-word translation. Used by the translation
# benchmark (eval/translate_eval.py), and listed in the prompt as things to avoid.
STIFF = [
    "भुगतान किए गए", "भुगतान किया", "भुगतान वाले", "समूह", "गारंटीकृत", "वक्ता", "निर्माता", "प्रस्तुतकर्ता",
    "उच्च लाभ", "उच्च रिटर्न", "प्रदान कर", "संबद्ध", "पंजीकृत", "अस्वीकरण", "तात्कालिकता", "मार्गदर्शन",
    "सदस्यता", "प्रतिफल", "अनुशंसा", "सिफारिश", "हेतु", "एवं", "द्वारा प्रदान",
]

STYLE = f"""You translate short English notes from an investor-protection app into Hindi for first-time
investors in small Indian towns.

Style:
- Everyday spoken Hindi, like a trusted friend explaining things, or a Hindi news channel. NOT textbook or
  government Hindi.
- Translate the meaning, not word by word. Short, simple sentences. Address the reader as "आप".
- Common finance words stay English, written in Devanagari (रिटर्न, स्टॉक, ग्रुप, लिंक, टिप, कोर्स).
- Keep these in English letters exactly: SEBI, IPO, NPS, AUM, URLs, numbers, ₹ amounts, coin/stock/company names.
- Use these terms:
{chr(10).join(f"  {en} → {hi}" for en, hi in GLOSSARY.items())}
- Avoid stiff words like: {", ".join(STIFF[:14])}.

Example (input is numbered; output has one translation per number, same order):
Input:
1. Inviting viewers to a paid Telegram group can lead to hidden fees and risky tips.
2. The speaker guarantees high returns from intraday trading, which is misleading because no one can guarantee market returns.
3. Promoting a demat account link suggests the creator may earn a commission from referrals.
4. High risk: promises guaranteed 100x returns and pushes a paid Telegram group.
Output:
{{"hindi": [
"दर्शकों को पेड Telegram ग्रुप में बुलाने से छिपी फ़ीस और जोखिम भरी टिप्स का खतरा रहता है।",
"क्रिएटर इंट्राडे ट्रेडिंग से बड़े मुनाफे की गारंटी दे रहा है। यह गुमराह करने वाली बात है, क्योंकि बाज़ार में रिटर्न की गारंटी कोई नहीं दे सकता।",
"डीमैट खाते का लिंक प्रमोट करने का मतलब है कि क्रिएटर को रेफ़रल से कमीशन मिल सकता है।",
"ज़्यादा जोखिम: 100 गुना गारंटीड रिटर्न का वादा और पेड Telegram ग्रुप में जुड़ने का दबाव।"
]}}"""
