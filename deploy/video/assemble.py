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
durs = json.loads((rec / "durations.json").read_text())
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

# Silent stretches between narrations (clicks, page loads) are fast-forwarded down to a natural
# pause, so the voice flows from scene to scene. Piecewise-linear remap of the cut timeline.
PAUSE = 1.2
starts = [cut(s["t"]) or 0 for s in m["scenes"]]
squeeze = []  # (from, to, new length)
for i in range(len(starts) - 1):
    a = starts[i] + 0.3 + durs.get(m["scenes"][i]["id"], 0) + 0.3   # narration end + breath
    b = starts[i + 1] + 0.3 - 0.3                                    # next narration start - breath
    if b - a > PAUSE:
        squeeze.append((a, b, PAUSE - 0.6 if PAUSE > 0.6 else 0.2))


def remap(t: float) -> float:
    out = t
    for a, b, n in squeeze:
        if t >= b:
            out -= (b - a) - n
        elif t > a:
            out -= (t - a) - (t - a) * n / (b - a)
    return out


kept = [(remap(t), f) for t, f in kept]
end = remap(end)
lines = ["ffconcat version 1.0"]
for (t, f), nxt in zip(kept, [k[0] for k in kept[1:]] + [end]):
    lines += [f"file '{f}'", f"duration {max(nxt - t, 0.001):.4f}"]
lines.append(f"file '{kept[-1][1]}'")
(rec / "frames.ffconcat").write_text("\n".join(lines))

inputs, filters = [], []
for i, s in enumerate(m["scenes"]):
    start = remap(cut(s["t"]) or 0)
    inputs += ["-i", str(audio_dir / f"{s['id']}.wav")]
    filters.append(f"[{i + 1}:a]adelay={int(start * 1000 + 300)}|{int(start * 1000 + 300)}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(m["scenes"])))
filters.append(f"{mix}amix=inputs={len(m['scenes'])}:normalize=0[mixed]")

# Two-pass loudness normalisation in linear mode: one constant gain for the whole narration,
# so the voice keeps its natural dynamics instead of "pumping" as single-pass loudnorm can.
# input 0 is a placeholder so the [n:a] labels match the final command, where input 0 is the video
measure = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-f", "lavfi", "-i", "anullsrc", *inputs, "-filter_complex",
                          ";".join(filters) + ";[mixed]loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json[o]", "-map", "[o]",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
ln = json.loads(measure[measure.rindex("{"):measure.rindex("}") + 1])
filters[-1] = filters[-1].replace("[mixed]", "") + (
    f",loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:measured_I={ln['input_i']}:measured_TP={ln['input_tp']}"
    f":measured_LRA={ln['input_lra']}:measured_thresh={ln['input_thresh']}:offset={ln['target_offset']}[aout]")

# Silence between consecutive narrations (long gaps feel like the video has stalled).
for i, s in enumerate(m["scenes"][:-1]):
    gap = remap(starts[i + 1]) - remap(starts[i]) - durs.get(s["id"], 0)
    print(f"  pause after {s['id']}: {gap:.1f}s")

cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(rec / "frames.ffconcat"), *inputs,
       "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
       "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
       "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)]
subprocess.run(cmd, check=True)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True).stdout)
print(f"{out}  {int(dur // 60)}:{dur % 60:04.1f}  frames kept {len(kept)}/{len(frames)}")
