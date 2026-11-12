#!/usr/bin/env python3
"""Scripted baselines under each reward version, the PPO gate, the scale table, baseline videos.

    scripts/rl.sh scripts/rl/baselines.py                          # v1.1 and v1.2, 5 episodes each
    scripts/rl.sh scripts/rl/baselines.py --versions v1.1 --episodes 10

Episodes use the eval split, seeds rl.eval_seed, rl.eval_seed + 1, ... (with a fixed start only the
random controller depends on the seed). Videos all use rl.eval_seed, the seed the PPO video
callback evaluates on. Gate: push_steer's mean return must beat stand's and random's under every
version; the script exits 1 if it does not.

Writes runs/rl-baselines-<timestamp>/ (report.md, results.json, videos/).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from copush.config import effective_reward, load_config, with_reward_version  # noqa: E402
from copush.env import CoPushEnv, baseline  # noqa: E402
from copush.rl_eval import episodes, fmt_block, scale_flags, scale_table, summarize  # noqa: E402
from copush.video import VideoLog  # noqa: E402

CONTROLLERS = ("stand", "random", "push_forward", "push_steer")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--versions", nargs="+", default=["v1.1", "v1.2"])
    p.add_argument("--episodes", type=int, default=5)
    p.add_argument("--no-videos", action="store_true")
    args = p.parse_args()
    base = load_config()
    seed = base["rl"]["eval_seed"]
    run_id = "rl-baselines-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(ROOT, "runs", run_id)
    os.makedirs(run_dir)
    res = {"run_id": run_id, "layout": base["env"]["layout"], "eval_seed": seed, "versions": {}}
    md = [f"# Baselines and gate ({run_id})", "",
          f"Layout `{base['env']['layout']}`, eval split, {args.episodes} episodes per controller "
          f"(seeds {seed}..{seed + args.episodes - 1}); videos on seed {seed}.", ""]
    gate_ok = True
    vlog = None if args.no_videos else VideoLog(run_dir, base["video"])
    for v in args.versions:
        cfg = with_reward_version(base, v)
        summ = {c: summarize(episodes(cfg, c, args.episodes, seed0=seed, split="eval")) for c in CONTROLLERS}
        g = {o: summ["push_steer"]["return_mean"] > summ[o]["return_mean"] for o in ("stand", "random")}
        gate_ok &= all(g.values())
        d0 = summ["stand"]["final_dist_mean"] if summ["stand"]["reasons"].get("timeout") else 0.40
        rows = scale_table(effective_reward(cfg), d0=d0)
        res["versions"][v] = {"summary": summ, "gate": g, "scale": {"rows": rows, "flags": scale_flags(rows)}}
        md += [f"## Reward {v}", "", fmt_block(f"{v}: baselines", summ),
               "**Gate** (push_steer mean return beats): " + ", ".join(
                   f"{o} {'PASS' if ok else 'FAIL'} ({summ['push_steer']['return_mean']:+.2f} vs {summ[o]['return_mean']:+.2f})"
                   for o, ok in g.items()), "",
               f"**Scale table** (synthetic episodes, start {d0:.2f} m)", "",
               "| outcome | total | ends at step | ends by |", "|---|---|---|---|"]
        md += [f"| {r['outcome']} | {r['total']:+.2f} | {r['steps']} | {r['ends']} |" for r in rows]
        md += ["", "Flags: " + ("; ".join(res["versions"][v]["scale"]["flags"]) or "none"), ""]
        if vlog is not None:
            for c in CONTROLLERS:
                env = CoPushEnv(cfg, split="eval")
                vlog.record(env, baseline(c, env, seed=seed), training_step=0, reason="baseline", seed=seed,
                            label=f"{c}_{v.replace('.', '')}")
    res["gate_passed"] = gate_ok
    md.insert(4, f"**Gate: {'PASSED' if gate_ok else 'FAILED'}**\n")
    if vlog is not None:
        md += ["Videos: [videos/index.md](videos/index.md)", ""]
    with open(os.path.join(run_dir, "results.json"), "w") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(run_dir, "report.md"), "w") as f:
        f.write("\n".join(md))
    print("\n".join(md))
    print(f"\nwrote runs/{run_id}/report.md")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
