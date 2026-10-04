"""Turn the recorded screencast + markers + narration into the final mp4.

Waiting periods (marked as skips) are cut out, the timeline is shifted accordingly, and
each scene's narration is placed at that scene's start on the cut timeline.
usage: python assemble.py <rec-dir> <audio-dir> <out.mp4>
"""
import json
import subprocess
import sys
from pathlib import Path

rec, audio_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
frames = json.loads((rec / "frames.json").read_text())
m = json.loads((rec / "markers.json").read_text())
skips = [(s["from"], s["to"]) for s in m["skips"] if s["to"] > s["from"]]
t0 = frames[0]["t"]


def cut(t: float) -> float | None:
    """Time on the cut timeline, or None if t falls inside a skipped window."""
    shift = 0.0
    for a, b in skips:
        if a <= t < b:
            return None
        if t >= b:
            shift += b - a
    return t - t0 - shift


kept = [(cut(f["t"]), f["f"]) for f in frames]
kept = [(t, f) for t, f in kept if t is not None]
end = cut(m["end"]) or kept[-1][0] + 1
lines = ["ffconcat version 1.0"]
for (t, f), nxt in zip(kept, [k[0] for k in kept[1:]] + [end]):
    lines += [f"file '{f}'", f"duration {max(nxt - t, 0.001):.4f}"]
lines.append(f"file '{kept[-1][1]}'")
(rec / "frames.ffconcat").write_text("\n".join(lines))

inputs, filters = [], []
for i, s in enumerate(m["scenes"]):
    start = cut(s["t"]) or 0
    inputs += ["-i", str(audio_dir / f"{s['id']}.wav")]
    filters.append(f"[{i + 1}:a]adelay={int(start * 1000 + 300)}|{int(start * 1000 + 300)}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(m["scenes"])))
filters.append(f"{mix}amix=inputs={len(m['scenes'])}:normalize=0,loudnorm=I=-16:TP=-1.5[aout]")

cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(rec / "frames.ffconcat"), *inputs,
       "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
       "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
       "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)]
subprocess.run(cmd, check=True)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True).stdout)
print(f"{out}  {dur / 60:.0f}:{dur % 60:04.1f}  frames kept {len(kept)}/{len(frames)}")
