#!/usr/bin/env python3
"""Reachability sweep: where can the scripted baselines put the box?

    scripts/rl.sh scripts/rl/reachability.py --out runs/overnight-20261112/reachability

Targets at sideways offsets x distances ahead of the box (in_contact start, target to the right,
against Shoe Push's left drift, as in the `steer` layout), EPISODES episodes per cell per
controller, reward v1.1, eval split, seeds from rl.eval_seed. The box is randomized per episode
(env.random: position, yaw, mass), because with a fixed start the scripts are deterministic and
five episodes would be five copies; the fixed-start outcome is reported next to it.

Writes results.json, table.md, heatmap.png and layout.json (the training layout and curriculum
levels picked by the rule in --help) to --out.

Rule: training layout = the hardest cell (largest offset, then farthest) where the best script
succeeds in at least MIN_WINS of EPISODES; two curriculum levels are spaced evenly between `close`
(offset 0, 0.4 m) and that cell, snapped to the grid.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from copush.config import load_config, with_reward_version  # noqa: E402
from copush.rl_eval import episodes, summarize  # noqa: E402

OFFSETS = (0.0, 0.10, 0.15, 0.20, 0.25, 0.30)
DISTANCES = (0.4, 0.6, 0.8)
CONTROLLERS = ("push_steer", "pivot_push")
EPISODES, MIN_WINS = 5, 3


def cell_cfg(base: dict, off: float, dist: float, randomize: bool) -> dict:
    cfg = copy.deepcopy(base)
    cfg["layouts"]["sweep"] = {"start_mode": "in_contact",
                               "target": {"x": cfg["box"]["x"] + dist, "y": cfg["box"]["y"] - off, "yaw": 90}}
    cfg["env"]["layout"] = "sweep"
    cfg["env"]["randomize"] = randomize
    return cfg


def snap(v: float, grid) -> float:
    return min(grid, key=lambda g: (abs(g - v), g))


def pick_layout(wins: dict) -> dict:
    """wins[(off, dist)] = best script's wins. Returns the layout cell and two curriculum levels."""
    ok = [k for k, w in wins.items() if w >= MIN_WINS]
    if not ok:
        return {"layout": None, "levels": []}
    off, dist = max(ok)                                   # largest offset, then farthest
    mids = [(snap(off * f, OFFSETS), snap(0.4 + (dist - 0.4) * f, DISTANCES)) for f in (1 / 3, 2 / 3)]
    return {"layout": {"offset": off, "distance": dist},
            "levels": [{"offset": 0.0, "distance": 0.4}] + [{"offset": o, "distance": d} for o, d in mids]
                      + [{"offset": off, "distance": dist}]}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    os.makedirs(args.out, exist_ok=True)
    base = with_reward_version(load_config(), "v1.1")
    seed = base["rl"]["eval_seed"]
    cells = []
    for off in OFFSETS:
        for dist in DISTANCES:
            row = {"offset": off, "distance": dist}
            for c in CONTROLLERS:
                s = summarize(episodes(cell_cfg(base, off, dist, True), c, EPISODES, seed0=seed, split="eval"))
                f = episodes(cell_cfg(base, off, dist, False), c, 1, seed0=seed, split="eval")[0]
                row[c] = {"wins": round(s["success_rate"] * EPISODES), "success_rate": s["success_rate"],
                          "return_mean": s["return_mean"], "falls": s["episodes_with_fall"],
                          "box_lost": s["box_lost"], "reasons": s["reasons"],
                          "final_dist_mean": s["final_dist_mean"],
                          "fixed_start": {"reason": f["reason"], "return": f["return"],
                                          "final_dist": f["final_dist"], "final_yaw_deg": f["final_yaw_deg"]}}
            cells.append(row)
            print(f"offset {off:.2f} dist {dist:.1f}: " + "  ".join(
                f"{c} {row[c]['wins']}/{EPISODES} (fixed: {row[c]['fixed_start']['reason']})" for c in CONTROLLERS), flush=True)
    wins = {(r["offset"], r["distance"]): max(r[c]["wins"] for c in CONTROLLERS) for r in cells}
    choice = pick_layout(wins)
    res = {"offsets": OFFSETS, "distances": DISTANCES, "episodes": EPISODES, "min_wins": MIN_WINS,
           "seed0": seed, "randomize": base["env"]["random"], "cells": cells, "choice": choice}
    with open(os.path.join(args.out, "results.json"), "w") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(args.out, "layout.json"), "w") as f:
        json.dump(choice, f, indent=1)

    md = ["# Reachability sweep", "",
          f"Successes out of {EPISODES} episodes (randomized box, eval seeds from {seed}), reward v1.1; in brackets the "
          "outcome with the fixed start. Target to the right of the push line.", "",
          "| offset (m) | distance (m) | push_steer | pivot_push | best | push_steer return | pivot_push return | "
          "falls ps / pp | box lost ps / pp |", "|---|---|---|---|---|---|---|---|---|"]
    for r in cells:
        a, b = r["push_steer"], r["pivot_push"]
        md.append(f"| {r['offset']:.2f} | {r['distance']:.1f} | {a['wins']}/{EPISODES} ({a['fixed_start']['reason']}) | "
                  f"{b['wins']}/{EPISODES} ({b['fixed_start']['reason']}) | {max(a['wins'], b['wins'])}/{EPISODES} | "
                  f"{a['return_mean']:+.2f} | {b['return_mean']:+.2f} | {a['falls']} / {b['falls']} | "
                  f"{a['box_lost']} / {b['box_lost']} |")
    md += ["", "![success rate](heatmap.png)", "", f"Choice by the rule (>= {MIN_WINS}/{EPISODES} for the best script, "
           f"largest offset then farthest): `{json.dumps(choice)}`", ""]
    with open(os.path.join(args.out, "table.md"), "w") as f:
        f.write("\n".join(md))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    panels = list(CONTROLLERS) + ["best of both"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6), constrained_layout=True)
    for ax, name in zip(axes, panels):
        g = np.array([[(max(r[c]["wins"] for c in CONTROLLERS) if name == "best of both" else r[name]["wins"]) / EPISODES
                       for r in cells if r["distance"] == d] for d in DISTANCES])
        im = ax.imshow(g, vmin=0, vmax=1, cmap="viridis", origin="lower", aspect="auto")
        ax.set_xticks(range(len(OFFSETS)), [f"{o:.2f}" for o in OFFSETS])
        ax.set_yticks(range(len(DISTANCES)), [f"{d:.1f}" for d in DISTANCES])
        ax.set_xlabel("sideways offset (m)")
        ax.set_ylabel("distance ahead (m)")
        ax.set_title(name)
        for i in range(len(DISTANCES)):
            for j in range(len(OFFSETS)):
                ax.text(j, i, f"{round(g[i, j] * EPISODES)}/{EPISODES}", ha="center", va="center",
                        color="black" if g[i, j] > 0.6 else "white")
        if name == "best of both" and choice["layout"]:
            ax.scatter([OFFSETS.index(choice["layout"]["offset"])], [DISTANCES.index(choice["layout"]["distance"])],
                       s=900, facecolors="none", edgecolors="red", linewidths=2)
    fig.colorbar(im, ax=axes, label="success rate")
    fig.suptitle(f"Scripted success rate, {EPISODES} episodes per cell (red ring: training layout)")
    fig.savefig(os.path.join(args.out, "heatmap.png"), dpi=130)
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
