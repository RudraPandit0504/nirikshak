import argparse
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(prog="nirikshak", description="Audit finance-influencer videos for investor-harm red flags.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="audit a YouTube URL or a local audio/video file")
    a.add_argument("target")
    a.add_argument("-o", "--out", type=Path, help="write the report JSON here")
    a.add_argument("--whisper", action="store_true", help="ignore captions and transcribe the audio")

    sub.add_parser("sebi-sync", help="download SEBI's RA/IA registry")

    rs = sub.add_parser("resummarize", help="re-score and rewrite the summary of saved reports (no re-analysis)")
    rs.add_argument("ids", nargs="*", help="report ids (default: all)")

    s = sub.add_parser("serve", help="run the web API (and built frontend)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    args = ap.parse_args()

    if args.cmd == "audit":
        from .pipeline import run_audit

        def progress(stage, frac, msg):
            print(f"\r[{stage:<10}] {msg[:70]:<70}", end="" if frac < 1 else "\n", file=sys.stderr, flush=True)

        target = Path(args.target) if Path(args.target).exists() else args.target
        r = run_audit(target, progress, force_whisper=args.whisper)
        if args.out:
            args.out.write_text(r.model_dump_json(indent=2), encoding="utf-8")
        print(f"\n{r.source.title}\nRisk: {r.risk_score}/100 ({r.risk_level})   registry: {r.registry.verdict}")
        for c in r.claims:
            t = f"{int(c.start // 60):02d}:{int(c.start % 60):02d}" if c.where == "transcript" else "desc "
            print(f"  {t}  [{c.category}] sev{c.severity} conf{c.confidence:.2f} {c.origin:<9} \"{c.quote[:90]}\"")
        print(f"\n{r.summary_en}\n{r.summary_hi}\nTimings: {r.timings}")

    elif args.cmd == "sebi-sync":
        from .sebi import sync

        print(f"Synced {sync()} registered entities.")

    elif args.cmd == "resummarize":
        from .config import REPORTS_DIR, SPEECH_DIR
        from .models import Report
        from .pipeline import finalize, save

        paths = [REPORTS_DIR / f"{i}.json" for i in args.ids] or sorted(REPORTS_DIR.glob("*.json"))
        for p in paths:
            r = finalize(Report.model_validate_json(p.read_text(encoding="utf-8")))
            save(r)
            for old in SPEECH_DIR.glob(f"{r.id}-*"):
                old.unlink()  # cached audio of the old summary
            print(f"{r.id}  {r.risk_score:>3} {r.risk_level:<6} {r.summary['en'].headline}")

    elif args.cmd == "serve":
        import socket

        import uvicorn

        with socket.socket() as s:
            if s.connect_ex((args.host, args.port)) == 0:
                sys.exit(f"Port {args.port} is already in use (is Nirikshak already running?). "
                         f"Stop the other process or use: nirikshak serve --port {args.port + 1}")
        print(f"Nirikshak running at http://{args.host}:{args.port}")
        uvicorn.run("nirikshak.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
