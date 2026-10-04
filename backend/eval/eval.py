"""Evaluate claim detection on hand-labelled transcript snippets.

Scoring is per snippet and per category: did we flag the category that a human
labeller expected (with confidence >= threshold)? Reports micro precision/recall/F1,
false-alarm rate on clean snippets, and latency.

    uv run python eval/eval.py                       # LLM + rules (the shipped pipeline)
    uv run python eval/eval.py --rules-only          # keyword baseline
    NIRIKSHAK_LLM=gemma3:4b uv run python eval/eval.py
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from nirikshak import analyse, rules
from nirikshak.config import LLM_MODEL
from nirikshak.models import Segment

HERE = Path(__file__).parent


def load(name: str) -> list[dict]:
    return [json.loads(l) for l in (HERE / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def predict(case: dict, rules_only: bool, threshold: float) -> set[str]:
    segs = [Segment(start=i * 5.0, end=i * 5.0 + 5, text=t) for i, t in enumerate(case["lines"])]
    hits = rules.scan_segments(segs)
    if rules_only:
        return {h.category for h in hits}
    claims = analyse.merge(analyse.analyse_window(segs, list(range(len(segs))), hits, "eval snippet"), hits)
    return {c.category for c in claims if c.confidence >= threshold}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules-only", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--set", default="cases", choices=["cases", "heldout"],
                    help="'cases' was used while developing prompts/rules; 'heldout' was written before tuning and not used for it")
    ap.add_argument("--json", type=Path, help="append a results row to this JSON file")
    args = ap.parse_args()

    cases = load(args.set)
    tp = fp = fn = 0
    clean_total = clean_flagged = 0
    t0 = time.perf_counter()
    for case in cases:
        exp = set(case["expect"])
        got = predict(case, args.rules_only, args.threshold)
        tp += len(exp & got)
        fp += len(got - exp)
        fn += len(exp - got)
        if not exp:
            clean_total += 1
            clean_flagged += bool(got)
        mark = "OK " if exp == got else "   "
        print(f"{mark}{case['id']:<24} expected={sorted(exp)} got={sorted(got)}")
    secs = time.perf_counter() - t0

    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * p * r / (p + r) if p + r else 0
    name = "rules-only" if args.rules_only else f"{LLM_MODEL} + rules"
    row = {
        "system": name, "set": args.set, "cases": len(cases), "precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3),
        "false_alarm_clean": f"{clean_flagged}/{clean_total}", "sec_per_case": round(secs / len(cases), 1),
    }
    print("\n" + json.dumps(row))
    if args.json:
        rows = json.loads(args.json.read_text()) if args.json.exists() else []
        rows = [x for x in rows if (x["system"], x.get("set")) != (name, args.set)] + [row]
        args.json.write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
