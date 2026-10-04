"""Human-readable descriptions of each claim category (used by prompts and the UI)."""

CATEGORIES = {
    "guaranteed_returns": {
        "en": "Guaranteed or unrealistic returns",
        "hi": "गारंटीड या बहुत ज़्यादा रिटर्न का वादा",
        "about_en": "Promises of fixed, 'sure', risk-free or very high returns. No market investment can guarantee returns.",
        "about_hi": "पक्के, बिना जोखिम वाले या बहुत ज़्यादा रिटर्न का वादा। बाज़ार में कोई भी निवेश रिटर्न की गारंटी नहीं दे सकता।",
        "prompt": "promises fixed/assured/'sure-shot'/risk-free returns, 'money will double', 'you cannot lose', specific % per day/week/month as an expected outcome",
    },
    "stock_tip": {
        "en": "Specific buy/sell call",
        "hi": "खरीदने-बेचने की टिप",
        "about_en": "Telling viewers to buy or sell a specific security, often with entry, target and stop-loss. Only SEBI-registered RAs/IAs may give such advice.",
        "about_hi": "किसी खास शेयर को खरीदने या बेचने को कहना, अक्सर एंट्री, टारगेट और स्टॉप-लॉस के साथ। ऐसी टिप सिर्फ़ SEBI में रजिस्टर्ड रिसर्च एनालिस्ट या इन्वेस्टमेंट एडवाइज़र ही दे सकते हैं।",
        "prompt": "a concrete recommendation to buy/sell/hold a NAMED stock, option, coin or fund, or entry/target/stop-loss levels for one",
    },
    "price_prediction": {
        "en": "Price prediction / hype",
        "hi": "भाव का अनुमान / हाइप",
        "about_en": "Confident predictions that a stock will double, hit a price or become a 'multibagger'. Nobody can reliably predict prices.",
        "about_hi": "पक्के दावे कि शेयर डबल होगा, किसी कीमत तक जाएगा या 'मल्टीबैगर' बनेगा। शेयर का भाव कहाँ जाएगा, यह पक्के तौर पर कोई नहीं बता सकता।",
        "prompt": "confident forecasts of where a specific price/index will go, 'multibagger', 'rocket', 'will 10x'",
    },
    "urgency_fomo": {
        "en": "Urgency / fear of missing out",
        "hi": "जल्दबाज़ी का दबाव",
        "about_en": "Pressure to act immediately ('last chance', 'before it's too late'). Good decisions are rarely urgent.",
        "about_hi": "'आखिरी मौका', 'देर मत करो' जैसी बातों से तुरंत पैसा लगाने का दबाव। सही फैसले जल्दबाज़ी में नहीं होते।",
        "prompt": "pressure to act right now, 'last chance', 'before it's too late', limited seats/time, fear of missing out",
    },
    "paid_promotion": {
        "en": "Paid promotion / affiliate",
        "hi": "पेड प्रमोशन / रेफ़रल लिंक",
        "about_en": "Sponsored content, referral links or 'open a demat account with my link'. The creator may earn from what they recommend.",
        "about_hi": "स्पॉन्सर्ड वीडियो, रेफ़रल लिंक या 'मेरे लिंक से डीमैट खाता खोलें'। जिस चीज़ की सलाह दी जा रही है, उससे क्रिएटर को कमीशन मिल सकता है।",
        "prompt": "sponsorship, affiliate/referral links or codes, 'open demat account using my link', commissions the creator earns",
    },
    "paid_group": {
        "en": "Paid / Telegram / VIP group",
        "hi": "पेड ग्रुप / टेलीग्राम / VIP",
        "about_en": "Pushing viewers into Telegram/WhatsApp/'premium' groups or paid courses. Many tip-scams start this way.",
        "about_hi": "दर्शकों को टेलीग्राम, व्हाट्सऐप या 'प्रीमियम' ग्रुप या पेड कोर्स में जुड़ने को कहना। टिप्स के नाम पर ज़्यादातर ठगी ऐसे ही शुरू होती है।",
        "prompt": "invitations to Telegram/WhatsApp/VIP/premium groups, paid tips, paid mentorship or courses",
    },
    "registration_claim": {
        "en": "Claims SEBI registration",
        "hi": "SEBI रजिस्ट्रेशन का दावा",
        "about_en": "Claims to be SEBI-registered. Nirikshak checks this against SEBI's public registry.",
        "about_hi": "SEBI में रजिस्टर्ड होने का दावा। निरीक्षक इसे SEBI की सार्वजनिक सूची से मिलाकर देखता है।",
        "prompt": "the speaker claims to be SEBI registered / a registered research analyst or investment adviser, or states an INH/INA number",
    },
    "misleading_claim": {
        "en": "Misleading or cherry-picked claim",
        "hi": "गुमराह करने वाला दावा",
        "about_en": "Showing only winning trades, unverifiable profit screenshots, or presenting a strategy as if it cannot fail.",
        "about_hi": "सिर्फ़ मुनाफे वाले ट्रेड दिखाना, प्रॉफिट के ऐसे स्क्रीनशॉट जिन्हें जाँचा न जा सके, या किसी तरीके को ऐसे बताना जैसे उसमें कभी नुकसान नहीं होगा।",
        "prompt": "showcasing only profits, unverifiable P&L screenshots as proof, claims a strategy 'always works', misrepresenting risk",
    },
}
