"""Compare English→Hindi translation prompts/models on real report sentences.

Automatic signals (human reading is still the final judge):
  stiff/100w  occurrences of textbook-Hindi calques (hindi.STIFF) per 100 Hindi words
  latin       English words left untranslated (excluding allowed names like SEBI/IPO)
  failed      sentences that came back empty

    uv run python eval/translate_eval.py data.json --prompt new --model gemma3:4b
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from nirikshak import analyse, hindi

OLD_PROMPT = ("Translate each numbered English sentence into simple, natural Hindi (Devanagari) "
              "for a first-time investor. Keep terms like SEBI, stock, demat, Telegram, IPO in "
              "English letters. Translate 'creator' as 'क्रिएटर' (never 'निर्माता'). Return a JSON array 'hindi' with exactly one translation per "
              "input, same order, no numbering, no transliteration.")
ALLOWED_LATIN = {"sebi", "ipo", "nps", "aum", "telegram", "whatsapp", "youtube", "fomo", "x", "ra", "ia", "ai", "id", "upi", "vip"}


def run(texts: list[str], prompt: str, model: str) -> list[str]:
    if prompt == "new":  # exactly what the app does, including per-sentence retry of bad batches
        analyse.HI_MODEL = model
        return analyse.translate_hi(texts)
    out = []
    for i in range(0, len(texts), 6):
        chunk = texts[i:i + 6]
        numbered = "\n".join(f"{j + 1}. {t}" for j, t in enumerate(chunk))
        data = analyse._chat([{"role": "system", "content": OLD_PROMPT},
                              {"role": "user", "content": numbered}],
                             analyse.TRANSLATE_SCHEMA, num_predict=200 + 150 * len(chunk), model=model)
        got = [t.strip() for t in data.get("hindi", [])]
        out += got if len(got) == len(chunk) else (got + [""] * len(chunk))[:len(chunk)]
    return out


def metrics(outs: list[str]) -> dict:
    words = sum(len(o.split()) for o in outs) or 1
    stiff = sum(o.count(w) for o in outs for w in hindi.STIFF)
    latin = sum(1 for o in outs for w in re.findall(r"[A-Za-z]+", o) if w.lower() not in ALLOWED_LATIN)
    return {"stiff_per_100w": round(100 * stiff / words, 2), "latin_words": latin,
            "failed": sum(1 for o in outs if not o)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=Path)
    ap.add_argument("--prompt", choices=["old", "new"], default="new")
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    texts = json.loads(a.data.read_text())
    model = a.model or analyse.HI_MODEL
    t0 = time.perf_counter()
    outs = run(texts, a.prompt, model)
    m = {"prompt": a.prompt, "model": model, **metrics(outs), "sec": round(time.perf_counter() - t0, 1)}
    print(json.dumps(m, ensure_ascii=False))
    if a.out:
        a.out.write_text(json.dumps([{"en": e, "hi": h} for e, h in zip(texts, outs)], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
