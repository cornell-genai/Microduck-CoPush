#!/usr/bin/env python3
"""One test-set start, two policies, one labeled side-by-side GIF (and mp4), each run under its own settings.

    scripts/rl.sh scripts/rl/side_by_side_policies.py --config experiments/stage1-random-box-pose/config.yaml \
        --test-set experiments/test_sets/stage1.json --start 8 \
        --left "D2, exact partner info=runs/decentral-p2-d2/model.zip@partner" \
        --right "D2 with chirps (2 s, 30 deg)=runs/chirp-partner-sensing/finetune-2s-30deg/model.zip@partner@chirp:2:30" \
        --out experiments/chirp-partner-sensing/finetune-2s-30deg/results

A spec is label=path@partner or @own, optionally followed by @chirp:<interval_s>:<direction_noise_deg>[:<distance_noise>]
(as in scripts/rl/compare_policies.py). The outcome of each episode is written under its label. Writes
<out>/start<N>_side_by_side.gif and .mp4 (GIF under 1 MB).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def parse(spec: str):
    label, path = spec.split("=", 1)
    chirp = re.search(r"@chirp:([\d.]+):([\d.]+)(?::([\d.]+))?$", path)
    if chirp:
        path = path[: chirp.start()]
    own = path.endswith("@own")
    path = path[: path.rindex("@")]
    dc = {"include_partner": not own}
    if chirp:
        dc["chirp"] = {"interval_s": float(chirp[1]), "direction_noise_deg": float(chirp[2]), "distance": chirp[3] is not None,
                       **({"distance_noise": float(chirp[3])} if chirp[3] else {})}
    return label, {"path": path, "decentral": dc}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--test-set", required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--left", required=True)
    p.add_argument("--right", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    from copush.env import CoPushEnv
    from copush.experiments import load_stage, load_test_set, repo_path
    from copush.video import record_episode
    from test_set import make_act_factory
    _, cfg0 = load_stage(a.config)
    start = load_test_set(a.test_set)["starts"][a.start]
    seed = cfg0["env"]["heldout_seeds"][0] + a.start
    out = repo_path(a.out)
    os.makedirs(out, exist_ok=True)
    clips, notes = [], []
    for i, spec in enumerate((a.left, a.right)):
        label, pol = parse(spec)
        cfg = dict(cfg0)
        if "chirp" in pol["decentral"]:
            cfg["chirp"] = {**cfg0["chirp"], "enabled": True, **pol["decentral"]["chirp"]}
        env = CoPushEnv(cfg, split="eval")
        act = make_act_factory(label, pol)(env, seed)
        mp4 = os.path.join(out, f"start{a.start:02d}_{i}.mp4")
        s = record_episode(env, act, mp4, seed=seed, video_cfg=cfg["video"], options={"box": start})
        note = ("won in %d steps" % s["steps"]) if s["reason"] == "success" else {"timeout": "ran out of time (%d steps)" % s["steps"]}.get(s["reason"], f"{s['reason']} after {s['steps']} steps")
        print(f"{label}: {note}")
        clips.append(mp4)
        notes.append((label, note))
    box = "fontfile=%s:fontsize=13:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=5" % FONT
    esc = lambda s: s.replace(":", "\\:").replace("'", "")                                      # noqa: E731
    draw = lambda i: (f"drawtext={box}:text='{esc(notes[i][0])}':x=(w-tw)/2:y=h-th-34," +        # noqa: E731
                      f"drawtext={box}:text='{esc(notes[i][1])}':x=(w-tw)/2:y=h-th-8")
    base = os.path.join(out, f"start{a.start:02d}_side_by_side")
    graph = f"[0:v]scale=300:-2,{draw(0)}[a];[1:v]scale=300:-2,{draw(1)}[b];[a][b]hstack=inputs=2"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clips[0], "-i", clips[1], "-filter_complex",
                    f"{graph},fps=5,tpad=stop_mode=clone:stop_duration=1.5,split[x][y];[x]palettegen=max_colors=24:stats_mode=diff[pl];"
                    "[y][pl]paletteuse=dither=none:diff_mode=rectangle", "-loop", "0", base + ".gif"], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clips[0], "-i", clips[1], "-filter_complex",
                    f"[0:v]scale=480:-2,{draw(0)}[a];[1:v]scale=480:-2,{draw(1)}[b];[a][b]hstack=inputs=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "28", "-preset", "veryfast", "-an", base + ".mp4"], check=True)
    for c in clips:
        os.remove(c)
    for f in (base + ".gif", base + ".mp4"):
        print("%7.0f KB  %s" % (os.path.getsize(f) / 1024, os.path.relpath(f, ROOT)))
    print(f"start {a.start}: dx {start['dx']:+.3f} m, dy {start['dy']:+.3f} m, dyaw {start['dyaw']:+.1f} deg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
