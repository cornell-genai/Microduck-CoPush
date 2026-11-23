#!/usr/bin/env python3
"""Side-by-side clip of one rendezvous-set start through the whole pipeline (rendezvous, handoff, push): left and right
are two rendezvous controllers (scripted, or a model.zip), both followed by the same push policy. 2x speed.

    scripts/rl.sh scripts/rl/rendezvous_gif.py --start 7 --left scripted --right runs/d2-rendezvous-r1-delta-reward/s1/model.zip \
        --out runs/d2-rendezvous-r1-delta-reward/gifs

Writes <out>/start<N>_side_by_side.gif (small) and .mp4.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts", "rl")]
os.chdir(ROOT)

import rendezvous_eval as rve  # noqa: E402

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def record(rendezvous: str, push: str, i: int, mp4: str, label: str) -> dict:
    from copush.sim import CONTROL_DT
    from copush.video import VideoRecorder
    rve._W.clear()
    rve._init(rendezvous, push, False, None)
    env, rv = rve._W["env"], rve._W["rv"]
    rec = VideoRecorder(env.sim.m, mp4, fps=25, width=480, height=270)
    every = max(1, round(2 / (25 * CONTROL_DT)))
    count, phase = [0], ["rendezvous"]

    def hook(st, _):
        if count[0] % every == 0:
            rec.frame(env.sim.d, st, [label, phase[0]])
        count[0] += 1
    rv.frame_hook = hook
    env.frame_hook = hook
    begin = env.begin_push_phase

    def begin_push(*a, **k):
        phase[0] = "push"
        return begin(*a, **k)
    env.begin_push_phase = begin_push
    try:
        out = rve.episode(i)
    finally:
        rec.close()
    return out


def note(r: dict) -> str:
    rvn = f"arrived in {r['rv_steps']} steps" if r["arrived"] else f"not docked after {r['rv_steps']} steps"
    push = "push: success" if r.get("push_success") else f"push: {r.get('push_reason')}"
    return f"{rvn}, {push}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--left", default="scripted")
    ap.add_argument("--right", required=True)
    ap.add_argument("--left-label", default=None)
    ap.add_argument("--right-label", default=None)
    ap.add_argument("--push", default=rve.PUSH)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)
    clips, notes = [], []
    for k, (spec, lab) in enumerate(((a.left, a.left_label), (a.right, a.right_label))):
        lab = lab or ("scripted" if spec == "scripted" else os.path.basename(os.path.dirname(spec)))
        mp4 = os.path.join(out, f"start{a.start:03d}_{k}.mp4")
        r = record(spec, a.push, a.start, mp4, lab)
        clips.append(mp4)
        notes.append((lab, note(r)))
        print(f"{lab}: {note(r)}")
    box = "fontfile=%s:fontsize=12:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=4" % FONT
    esc = lambda s: s.replace(":", "\\:").replace("'", "").replace(",", "\\,")                  # noqa: E731
    draw = lambda i: (f"drawtext={box}:text='{esc(notes[i][0])}':x=(w-tw)/2:y=h-th-30," +        # noqa: E731
                      f"drawtext={box}:text='{esc(notes[i][1])}':x=(w-tw)/2:y=h-th-8")
    base = os.path.join(out, f"start{a.start:03d}_side_by_side")
    # the two clips can differ in length: pad the shorter with its last frame
    graph = (f"[0:v]scale=300:-2,tpad=stop_mode=clone:stop_duration=30,{draw(0)}[a];"
             f"[1:v]scale=300:-2,tpad=stop_mode=clone:stop_duration=30,{draw(1)}[b];[a][b]hstack=inputs=2:shortest=0")
    dur = max(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", c],
                                   capture_output=True, text=True).stdout.strip() or 0) for c in clips) + 1.5
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clips[0], "-i", clips[1], "-filter_complex",
                    f"{graph},fps=5,split[x][y];[x]palettegen=max_colors=24:stats_mode=diff[pl];"
                    "[y][pl]paletteuse=dither=none:diff_mode=rectangle", "-t", f"{dur:.2f}", "-loop", "0", base + ".gif"], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clips[0], "-i", clips[1], "-filter_complex", graph,
                    "-t", f"{dur:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "28", "-preset", "veryfast", "-an",
                    base + ".mp4"], check=True)
    for c in clips:
        os.remove(c)
    for f in (base + ".gif", base + ".mp4"):
        print("%7.0f KB  %s" % (os.path.getsize(f) / 1024, os.path.relpath(f, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
