"""Build presentation/Nirikshak.pptx from screenshots in <shots-dir>.
usage: python make_deck.py <shots-dir> <live-demo-url> <github-url>
"""
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

SH, LIVE, GH = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
OUT = Path(__file__).resolve().parent.parent / "presentation/Nirikshak.pptx"

INK = RGBColor(0x0B, 0x12, 0x20)
INK2 = RGBColor(0x3B, 0x45, 0x59)
INK3 = RGBColor(0x6B, 0x74, 0x86)
ORANGE = RGBColor(0xFF, 0x7A, 0x1A)
RED = RGBColor(0xE5, 0x3E, 0x3E)
GREEN = RGBColor(0x2E, 0xA8, 0x4F)
PURPLE = RGBColor(0x7C, 0x4D, 0xFF)
BG = RGBColor(0xF6, 0xF4, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK = RGBColor(0x0B, 0x0F, 0x1A)
FONT = "Calibri"  # present in every PowerPoint install; Inter was substituted and overflowed

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def bg(s, c=BG):
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = c


def text(s, x, y, w, h, lines, size=18, color=INK, bold=False, bullet=False, align=None, spacing=8):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        runs = line if isinstance(line, list) else [(line, bold, color)]
        if bullet:
            r = p.add_run(); r.text = "•  "; r.font.size = Pt(size); r.font.color.rgb = ORANGE; r.font.bold = True; r.font.name = FONT
        for t, b, c in runs:
            r = p.add_run(); r.text = t; r.font.size = Pt(size); r.font.bold = b; r.font.color.rgb = c; r.font.name = FONT
        p.space_after = Pt(spacing)
        if align:
            p.alignment = align
    return tb


def bar(s):
    b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.09))
    b.fill.gradient(); b.fill.gradient_angle = 0
    b.fill.gradient_stops[0].color.rgb = ORANGE; b.fill.gradient_stops[1].color.rgb = PURPLE
    b.line.fill.background()


def header(s, kicker, title):
    bg(s); bar(s)
    text(s, 0.6, 0.4, 12, 0.4, [kicker.upper()], 13, ORANGE, True)
    text(s, 0.6, 0.72, 12.2, 1.0, [title], 32, INK, True)


def card(s, x, y, w, h, title, body, accent=ORANGE, title_size=17, body_size=13):
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    b.adjustments[0] = 0.08
    b.fill.solid(); b.fill.fore_color.rgb = WHITE; b.line.color.rgb = RGBColor(0xE4, 0xE1, 0xEE)
    b.shadow.inherit = False
    s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + 0.25), Inches(y + 0.25), Inches(0.45), Inches(0.06)).fill.solid()
    deco = s.shapes[-1]; deco.fill.fore_color.rgb = accent; deco.line.fill.background()
    text(s, x + 0.2, y + 0.4, w - 0.4, 0.6, [title], title_size, INK, True)
    text(s, x + 0.2, y + 0.95, w - 0.4, h - 1.0, body, body_size, INK2, spacing=5)


def img(s, name, x, y, w=None, h=None, crop=None):
    p = SH / name
    if crop:
        out = SH / f"crop_{crop[1]}_{crop[3]}_{name}"
        Image.open(p).crop(crop).save(out)
        p = out
    kw = {}
    if w: kw["width"] = Inches(w)
    if h: kw["height"] = Inches(h)
    pic = s.shapes.add_picture(str(p), Inches(x), Inches(y), **kw)
    pic.line.color.rgb = RGBColor(0xDD, 0xDA, 0xE8)
    return pic


# 1 Title
s = prs.slides.add_slide(BLANK); bg(s, DARK)
# The whole home screen, framed, rather than a cropped strip.
pic = img(s, "dark.png", 7.05, 1.55, w=5.75)
pic.line.color.rgb = RGBColor(0x3A, 0x41, 0x55); pic.line.width = Pt(1.25)
text(s, 0.7, 1.2, 6.5, 0.4, ["SANGYAN 2026  ·  TRACK A + TRACK E"], 13, ORANGE, True)
text(s, 0.7, 1.75, 6.2, 1.3, ["Nirikshak  निरीक्षक"], 46, WHITE, True)
text(s, 0.7, 3.05, 6.0, 1.8, ["Check before you trust.",
                              "An investor-protection auditor for forwarded WhatsApp tips, finfluencer videos and the creators behind them, checked against SEBI's registers, in Hindi and English."],
     18, RGBColor(0xD8, 0xDC, 0xE6), spacing=10)
text(s, 0.7, 5.6, 6.4, 1.0, [[("Live demo  ", True, ORANGE), (LIVE, False, WHITE)], [("Code  ", True, ORANGE), (GH, False, WHITE)]], 14, spacing=6)

# 2 Problem
s = prs.slides.add_slide(BLANK); header(s, "The problem", "Market access has outrun trustworthy guidance")
stats = [("16+ crore", "demat accounts in India", ORANGE), ("70%+", "of new retail accounts from Tier-2/3 cities", PURPLE),
         ("9 in 10", "individual F&O traders lose money (SEBI study)", RED)]
for i, (n, l, c) in enumerate(stats):
    x = 0.6 + i * 4.15
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(1.9), Inches(3.9), Inches(1.9))
    b.adjustments[0] = 0.1; b.fill.solid(); b.fill.fore_color.rgb = WHITE; b.line.color.rgb = RGBColor(0xE4, 0xE1, 0xEE)
    text(s, x + 0.3, 2.05, 3.4, 0.9, [n], 40, c, True)
    text(s, x + 0.3, 2.95, 3.4, 0.8, [l], 16, INK2)
text(s, 0.6, 4.3, 12.2, 3.0, [
    "Tips arrive as WhatsApp/Telegram forwards and YouTube videos: \"guaranteed\" returns, buy/sell calls, VIP groups, fake KYC alerts.",
    "Scammers use fake SEBI numbers, cloned broker sites and remote-access apps; victims realise only when money is gone.",
    "Many first-time investors are more comfortable in Hindi, have no one to ask, and can't tell education from promotion.",
], 20, INK2, bullet=True, spacing=14)

# 3 User
s = prs.slides.add_slide(BLANK); header(s, "Who we solve for", "Sunita, 34, Kanpur: first-time investor, Hindi-first")
text(s, 0.6, 2.0, 6.3, 5, [
    "Opened a demat account last year; learns from YouTube and family WhatsApp groups",
    "Receives \"tips\" and \"KYC alerts\" daily and can't verify who is behind them",
    "Reads Hindi comfortably, English with effort; uses a mid-range Android phone",
    "Needs a quick, trustworthy answer at the moment of doubt: before she pays, clicks or invests",
], 20, INK2, bullet=True, spacing=18)
card(s, 7.3, 1.9, 5.4, 2.45, "Also built for", [
    "Senior citizens targeted by impersonation (fake SEBI / broker calls)",
    "Families checking a tip forwarded to a parent",
    "Anyone who just received a suspicious message",
], PURPLE, body_size=15)
card(s, 7.3, 4.6, 5.4, 2.45, "What she needs", [
    "Is this a scam? Which exact part is dangerous?",
    "Is this person SEBI-registered?",
    "What should I do now, in my language?",
], ORANGE, body_size=15)

# 4 Solution overview
s = prs.slides.add_slide(BLANK); header(s, "The solution", "One product, four ways to check before you trust")
cards = [
    ("Check a message", "Paste a forwarded WhatsApp/Telegram/SMS tip or drop a screenshot. Flags OTP requests, fake KYC, payment demands, suspicious links, impersonation.", ORANGE, "Track A"),
    ("Audit a video", "Paste a YouTube link. Every guaranteed-return promise, buy/sell call, hype and hidden promotion, quoted with its timestamp.", RED, "Track E"),
    ("Profile a creator", "Audits a channel's recent uploads: how often they give tips, promise returns or push paid groups.", PURPLE, "Track E"),
    ("Ask in your words", "Chat (typed or spoken, Hindi/English) about any audit. Answers cite the evidence; never gives investment advice.", GREEN, "Tracks C/E"),
]
for i, (t, b, c, tag) in enumerate(cards):
    x = 0.6 + i * 3.1
    card(s, x, 1.9, 2.9, 3.9, t, [b], c, title_size=19, body_size=15)
    text(s, x + 0.2, 5.3, 2.5, 0.4, [tag], 13, c, True)
text(s, 0.6, 6.05, 12.2, 1.2, ["Every name, website and registration number is checked against 6,645 entities from 5 SEBI registers. Every result comes with a plain-language summary, concrete next steps, a PDF report and a natural voice, in English or हिन्दी."], 16, INK2)

# 5 Journey: message
s = prs.slides.add_slide(BLANK); header(s, "Journey 1 · Track A", "A fake Zerodha KYC alert, caught in seconds")
img(s, "msg.png", 0.6, 1.7, w=7.6, crop=(140, 130, 1300, 910))
text(s, 8.5, 1.8, 4.4, 5.5, [
    "Risk 100/100: every warning sign is tied to the exact line",
    "Domain check: uses Zerodha's name but links to zerodha-kyc-update.in, not their official site",
    "Spots the OTP request and the ₹99 fee to a UPI handle; ignores a genuine bank OTP SMS",
    "Gives concrete steps: don't share, don't pay, use the official app, call 1930",
    "Works from a screenshot too (vision OCR keeps Hindi in Devanagari)",
], 17, INK2, bullet=True, spacing=14)

# 6 Journey: video
s = prs.slides.add_slide(BLANK); header(s, "Journey 2 · Track E", "A \"100X guaranteed\" crypto video, audited line by line")
img(s, "video.png", 0.6, 1.7, w=7.6, crop=(140, 130, 1300, 910))
text(s, 8.5, 1.8, 4.4, 5.5, [
    "Full transcript (YouTube captions or local Whisper, Hindi/English/Hinglish)",
    "Findings quote the creator verbatim with a timestamp you can click",
    "Each finding shows severity, confidence and whether AI or keywords found it: uncertainty is visible, never a bare true/false",
    "Separates promotion (paid groups, referral links) from education",
], 17, INK2, bullet=True, spacing=14)

# 7 SEBI check
s = prs.slides.add_slide(BLANK); header(s, "Who is giving the advice?", "Real checks against SEBI's public registers")
img(s, "profile.png", 7.4, 1.7, h=5.4, crop=(900, 520, 1310, 1040))
text(s, 0.6, 1.9, 6.4, 5.5, [
    "Local mirror of 5 SEBI registers: research analysts, investment advisers, portfolio managers, brokers, mutual funds (6,645 entities)",
    "Checks every registration number (typos too), the channel name, presenters and guest experts found by AI, and the creator's own website",
    "Clear verdicts: registered adviser · registered only as a broker (not allowed to give tips) · guest expert registered · not registered",
    "Shows exactly what was checked, so \"not found\" is evidence, not a failure",
], 17, INK2, bullet=True, spacing=14)

# 8 Ask + guardrail
s = prs.slides.add_slide(BLANK); header(s, "Ask the video", "Grounded answers, and a firm line on advice")
img(s, "ask.png", 0.6, 2.2, w=8.2)
text(s, 9.1, 1.9, 3.8, 5.5, [
    "Questions in English or Hindi, typed or spoken (local Whisper)",
    "Answers cite real transcript lines; made-up citations are dropped",
    "\"Should I buy?\" / \"Will it double?\" are refused and redirected to the facts and registration status",
    "Concept questions (\"what is a stop-loss?\") get labelled general explanations",
], 17, INK2, bullet=True, spacing=14)

# 9 Bharat-first
s = prs.slides.add_slide(BLANK); header(s, "Bharat-first · 25% of the evaluation", "Built for Hindi speakers and low-end phones")
img(s, "hindi.png", 0.6, 1.8, w=6.4, crop=(140, 130, 1300, 910))
img(s, "mobile.png", 7.25, 1.7, h=5.5)
text(s, 9.95, 1.8, 3.0, 5.5, [
    "Full Hindi UI, explanations, summaries and PDF, written in everyday Hindi (style guide + glossary)",
    "Natural voice reads the summary aloud (Kokoro TTS, 4.1/5 naturalness in Hindi vs 1.4 for the browser voice)",
    "Works on any phone browser: responsive layout, light effects; the AI runs on a server",
], 15, INK2, bullet=True, spacing=12)

# 10 Profile
s = prs.slides.add_slide(BLANK); header(s, "Creator trust profile", "One video can be an outlier; the pattern is the warning")
img(s, "profile.png", 0.6, 1.7, w=7.6, crop=(140, 120, 1300, 1000))
text(s, 8.5, 1.7, 4.4, 5.5, [
    "Audits a channel's latest uploads (re-using earlier audits)",
    "Example: high risk overall; all 5 recent videos push a paid Telegram group, 2 promise guaranteed returns; not registered",
    "Contrast: a SEBI-registered research analyst is verified and scores low (0/100) across recent videos",
    "Helps users decide whom to follow, not what to buy",
], 17, INK2, bullet=True, spacing=14)

# 11 Technology
s = prs.slides.add_slide(BLANK); header(s, "Technology", "AI used where it matters, guarded by checks")
steps = [("Input", "YouTube captions · Whisper\n(local) · screenshot OCR"), ("Scan", "Multilingual rules\nEN · Hinglish · हिन्दी"),
         ("Understand", "LLM, JSON-schema output\n12 harm categories"), ("Ground", "Quote must match the text,\nelse discarded"),
         ("Verify", "SEBI registers · official\nbroker domains"), ("Explain", "Brief · Hindi · voice ·\nPDF · Q&A")]
for i, (t, d) in enumerate(steps):
    x = 0.6 + i * 2.1
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(2.0), Inches(1.85), Inches(2.1))
    b.adjustments[0] = 0.12; b.fill.solid(); b.fill.fore_color.rgb = DARK if i in (2, 4) else WHITE; b.line.color.rgb = RGBColor(0xE4, 0xE1, 0xEE)
    text(s, x + 0.12, 2.12, 1.65, 0.5, [t], 18, ORANGE if i in (2, 4) else INK, True)
    text(s, x + 0.12, 2.7, 1.65, 1.3, d.split("\n"), 13, RGBColor(0xC9, 0xCE, 0xDA) if i in (2, 4) else INK2, spacing=2)
text(s, 0.6, 4.55, 12.2, 3, [
    "Runs fully local on a 6 GB laptop GPU: Qwen 2.5 7B (analysis) + Gemma 3 4B (Hindi, vision) via Ollama, faster-whisper, Kokoro TTS. No data leaves the device.",
    "Hosted demo on AWS (EC2, Mumbai): same code, AI via Amazon Bedrock with Groq/Gemini fallback, server-side keys, per-visitor limits.",
    "Stack: Python · FastAPI · SQLite · React + TypeScript + Tailwind · Docker. 31 unit tests; labelled eval sets.",
], 17, INK2, bullet=True, spacing=14)

# 12 Trust + evaluation
s = prs.slides.add_slide(BLANK); header(s, "Trust, guardrails & measured accuracy", "Non-commercial, private, honest about uncertainty")
card(s, 0.6, 1.9, 3.9, 2.8, "Guardrails", ["No tips, predictions or buy/sell/hold views", "Advice questions refused", "No brokers promoted, no monetisation"], RED, body_size=15)
card(s, 4.7, 1.9, 3.9, 2.8, "Privacy", ["Full version runs on the user's device", "No SMS/OTP harvesting; nothing stored remotely", "Messages can be checked without saving"], GREEN, body_size=15)
card(s, 8.8, 1.9, 3.9, 2.8, "Uncertainty", ["Confidence on every finding", "Verbatim quotes to self-check", "\"Possible match: verify the number\""], PURPLE, body_size=15)
text(s, 0.6, 5.05, 12.2, 2.4, [
    [("Held-out test sets (never used for tuning): ", True, INK), ("video claims F1 0.89 vs 0.56 for keyword rules alone, 0 false alarms on clean videos; forwarded-message scams F1 0.96, 0 false alarms on clean messages (bank OTP SMS, news, family chats).", False, INK2)],
    [("Calibrated scoring: ", True, INK), ("registered analysts and educational videos score low (0-14); scams and guaranteed-return pitches score high. Test sets are published with the code.", False, INK2)],
], 16, spacing=12)

# 13 Feasibility & scale
s = prs.slides.add_slide(BLANK); header(s, "Feasibility & scale", "Infrastructure any institution can run")
text(s, 0.6, 2.0, 6.0, 5, [
    "Open source; runs on one consumer GPU with zero per-check cost, or on a hosted model API",
    "An exchange, depository, investor-education fund or NGO can host it for millions; users only need a phone browser",
    "Rules, registers and languages are data: add new scam patterns or regional languages without retraining",
], 20, INK2, bullet=True, spacing=18)
card(s, 7.0, 1.95, 5.7, 4.9, "Next steps", [
    "Share-to-Nirikshak from WhatsApp and a Telegram bot",
    "Tamil, Telugu, Bengali, Marathi via Bhashini / IndicTrans2",
    "IVR / missed-call verification of a registration number",
    "Brokers' and AMFI distributor registers; nightly SEBI sync",
    "Larger labelled dataset with investor-protection volunteers",
], ORANGE, body_size=16)

# 14 Close
s = prs.slides.add_slide(BLANK); bg(s, DARK)
text(s, 0.9, 2.3, 11.5, 1.3, ["Check before you trust."], 48, WHITE, True)
text(s, 0.9, 3.6, 11.5, 1.6, [[("Live demo  ", True, ORANGE), (LIVE, False, WHITE)], [("Code  ", True, ORANGE), (GH, False, WHITE)]], 20, spacing=10)
text(s, 0.9, 6.3, 11.5, 0.6, ["Awareness tool only. Not investment advice."], 13, RGBColor(0x9A, 0xA4, 0xB5))

prs.save(OUT)
print("saved", OUT)
