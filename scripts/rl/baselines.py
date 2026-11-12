#!/usr/bin/env python3
"""Scripted baselines per layout, the PPO gates, policy-switch wobble, baseline videos.

    scripts/rl.sh scripts/rl/baselines.py                 # close (5 episodes) + steer (10), reward v1.1
    scripts/rl.sh scripts/rl/baselines.py --version v1.2

Gates:
    close  push_steer's mean return beats stand's
    steer  push_steer's success rate beats random's by at least STEER_MARGIN

Episodes use the eval split, seeds rl.eval_seed, rl.eval_seed + 1, ... (with a fixed start only the
random controller depends on the seed). All videos use rl.eval_seed, the seed the PPO video
callback evaluates on. Every Shoe Push <-> velstand switch is checked over the next 1 s (trunk
height, tilt, counted fall, box movement). Exit code 1 if any gate fails.

Writes runs/rl-baselines-<timestamp>/ (report.md, results.json, videos/).
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from copush.config import load_config, with_reward_version  # noqa: E402
from copush.env import CoPushEnv, baseline  # noqa: E402
from copush.rl_eval import episodes, summarize, switch_summary  # noqa: E402
from copush.video import VideoLog  # noqa: E402

CONTROLLERS = ("stand", "random", "push_forward", "push_steer")
PLAN = (("close", 5), ("steer", 10))
STEER_MARGIN = 0.30


def table(summ: dict) -> list:
    out = ["| controller | mean return ± sd | success | falls | box lost | ends | push share A / B | flags (episodes) |",
           "|---|---|---|---|---|---|---|---|"]
    for c, s in summ.items():
        sh = "-" if math.isnan(s["push_share_a_mean"]) else f"{100 * s['push_share_a_mean']:.0f} / {100 - 100 * s['push_share_a_mean']:.0f}%"
        out.append(f"| {c} | {s['return_mean']:+.2f} ± {s['return_std']:.2f} | {100 * s['success_rate']:.0f}% | "
                   f"{s['episodes_with_fall']}/{s['n']} | {s['box_lost']}/{s['n']} | "
                   f"{', '.join(f'{k} {v}' for k, v in sorted(s['reasons'].items()))} | {sh} | "
                   f"{', '.join(f'{k} {v}' for k, v in sorted(s['flag_episodes'].items())) or 'none'} |")
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--version", default="v1.1")
    p.add_argument("--no-videos", action="store_true")
    args = p.parse_args()
    base = with_reward_version(load_config(), args.version)
    seed = base["rl"]["eval_seed"]
    run_id = "rl-baselines-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(ROOT, "runs", run_id)
    os.makedirs(run_dir)
    vlog = None if args.no_videos else VideoLog(run_dir, base["video"])
    res = {"run_id": run_id, "reward_version": args.version, "eval_seed": seed, "layouts": {}}
    md = [f"# Baselines and gates ({run_id})", "", f"Reward {args.version}, eval split, seeds from {seed}; videos on seed {seed}.", ""]
    switches, ok_all = [], True
    for layout, n in PLAN:
        cfg = copy.deepcopy(base)
        cfg["env"]["layout"] = layout
        summ = {c: summarize(episodes(cfg, c, n, seed0=seed, split="eval", switch_log=switches)) for c in CONTROLLERS}
        if layout == "close":
            ok = summ["push_steer"]["return_mean"] > summ["stand"]["return_mean"]
            gate = (f"push_steer mean return {summ['push_steer']['return_mean']:+.2f} vs stand "
                    f"{summ['stand']['return_mean']:+.2f}: {'PASS' if ok else 'FAIL'}")
        else:
            ok = summ["push_steer"]["success_rate"] >= summ["random"]["success_rate"] + STEER_MARGIN
            gate = (f"push_steer success {100 * summ['push_steer']['success_rate']:.0f}% vs random "
                    f"{100 * summ['random']['success_rate']:.0f}% (needs +{100 * STEER_MARGIN:.0f} points): "
                    f"{'PASS' if ok else 'FAIL'}")
        ok_all &= ok
        res["layouts"][layout] = {"summary": summ, "gate_passed": ok, "gate": gate, "episodes": n}
        md += [f"## Layout `{layout}` ({n} episodes per controller)", ""] + table(summ) + ["", f"**Gate:** {gate}", ""]
        if vlog is not None:
            for c in CONTROLLERS:
                env = CoPushEnv(cfg, split="eval")
                vlog.record(env, baseline(c, env, seed=seed), training_step=0, reason="baseline", seed=seed,
                            label=f"{layout}_{c}")
    sw = switch_summary(switches)
    res["switches"] = {"summary": sw, "windows": switches}
    md += ["## Policy switches (next 1 s after each)", "",
           "| switch | count | stumbles (tilt > 26° or z < 0.095) | counted falls | worst tilt | lowest trunk z | box moved (max) |",
           "|---|---|---|---|---|---|---|"]
    md += [f"| {k} | {b['n']} | {b['stumbles']} | {b['falls']} | {b['worst_tilt']:.1f}° | {b['lowest_z']:.3f} m | "
           f"{100 * b['box_moved_max']:.1f} cm |" for k, b in sorted(sw.items())]
    worst = max(switches, key=lambda w: w["max_tilt"], default=None)
    if worst:
        md += ["", f"Worst: {worst['controller']} ({worst['duck']}, {worst['from']}->{worst['to']}, episode "
                   f"{worst['episode']}, t={worst['t']:.2f} s): tilt {worst['max_tilt']:.1f}°, fell {worst['fell']}"]
    res["gates_passed"] = ok_all
    md.insert(4, f"**Gates: {', '.join(f'{k} ' + ('PASS' if v['gate_passed'] else 'FAIL') for k, v in res['layouts'].items())}**\n")
    if vlog is not None:
        md += ["", "Videos: [videos/index.md](videos/index.md). The switch to velstand (hold) is at the end of "
                   "`step_0_baseline_close_push_steer.mp4`.", ""]
    with open(os.path.join(run_dir, "results.json"), "w") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(run_dir, "report.md"), "w") as f:
        f.write("\n".join(md))
    print("\n".join(md))
    print(f"\nwrote runs/{run_id}/report.md")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
