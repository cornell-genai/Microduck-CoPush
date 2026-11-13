#!/usr/bin/env python3
"""The fixed test set ("exam") of a stage: make it once, evaluate every controller on it, videos.

    scripts/rl.sh scripts/rl/test_set.py make --config experiments/stage1-random-box-pose/config.yaml
    scripts/rl.sh scripts/rl/test_set.py eval --config experiments/stage1-random-box-pose/config.yaml
    scripts/rl.sh scripts/rl/test_set.py side-by-side --config ... --left pivot_push --right stage1 [--start ID]

make          test.n box poses from the FINAL env.box_start range with its own RNG (test.rng_seed),
              written to the stage's test_set file; refuses to overwrite it. Each start is checked:
              both ducks must touch the box in the first 1 s of push_forward (the in-contact
              start leaves them a hair behind the face; standing still they never touch it).
              --checks: the stage's check_set instead (check.n / check.rng_seed), the fixed starts
              the training checks run on; it must share no start with the test set.
eval          every test.controllers baseline and test.policies PPO policy (deterministic; missing
              files are skipped), one episode per start, in parallel. Writes to the stage's results/:
              test_set.md (table), test_set.json (per-episode outcomes) and difficulty.png (success
              vs box offset and box angle buckets).
side-by-side  one start, two controllers, one mp4 each and an hstack (ffmpeg) in <out>/videos/.
              Default start: the hardest (largest angle, then offset) where --right succeeds and
              --left does not, from results/test_set.json (--positive: only starts turned > +15 deg).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from copush.experiments import (difficulty, load_stage, load_test_set, make_test_set,  # noqa: E402
                                repo_path, test_set_episodes)

OFFSET_BINS = (0.0, 0.05, 0.10, 0.15, 0.22)        # m; the corners of a +-0.15 m square reach 0.21
ANGLE_BINS = (0.0, 15.0, 30.0, 45.0)               # deg; 15 = the success tolerance
SIGNED_BINS = (-45.0, -30.0, -15.0, 15.0, 30.0, 45.0)   # deg, box yaw minus nominal; the sign is which way it is turned
HIGHLIGHT = {"stage1": "#2a78d6", "01_reference": "#eb6834", "pivot_push": "#1baf7a",   # dataviz slots 1-5,
             "a_oversample": "#eda100", "b_time_penalty": "#e87ba4"}                   # fixed per policy
MUTED = "#a3a29b"


def policy_path(spec) -> str:
    return spec["path"] if isinstance(spec, dict) else spec


def make_act_factory(name: str, path=None):
    """-> make_act(env, seed) for test_set_episodes. path: a model.zip, or {path, decentral:
    {include_partner}} for a decentralized policy (copush.decentral, run once per duck)."""
    from copush.env import baseline
    if path is None:
        return lambda env, seed: baseline(name, env, seed=seed)
    from stable_baselines3 import PPO
    model = PPO.load(repo_path(policy_path(path)), device="cpu")
    if isinstance(path, dict) and path.get("decentral") is not None:
        from copush.decentral import decentral_action
        ip = bool(path["decentral"].get("include_partner"))
        return lambda env, seed: (lambda obs: decentral_action(model, env.state, ip))
    return lambda env, seed: (lambda obs: model.predict(obs, deterministic=True)[0])


def _eval_one(job):
    cfg_path, name, path = job
    _, cfg = load_stage(cfg_path)
    ts = load_test_set(load_stage(cfg_path)[0]["test_set"])
    stats = test_set_episodes(cfg, ts["starts"], make_act_factory(name, path))
    return name, stats


def cmd_make(stage: dict, cfg: dict, cfg_path: str, checks: bool = False) -> int:
    rel = stage["check_set"] if checks else stage["test_set"]
    path = repo_path(rel)
    if os.path.exists(path):
        print(f"{rel} exists; a test set is written once (delete it by hand to remake)")
        return 1
    t = stage["check"] if checks else stage["test"]
    starts = make_test_set(cfg, t["n"], t["rng_seed"])
    if checks:
        pose = lambda s: (s["x"], s["y"], s["yaw"])                      # noqa: E731
        shared = {pose(s) for s in starts} & {pose(s) for s in load_test_set(stage["test_set"])["starts"]}
        if shared:
            print(f"check set shares {len(shared)} starts with the test set; pick another check.rng_seed")
            return 1
    stats = test_set_episodes(cfg, starts, make_act_factory("push_forward"))
    bad = [s["start"]["id"] for s in stats if min(s["touch_s"].values()) <= 0.0]
    if bad:
        print(f"starts where a duck does not touch the box in the first 1 s of push_forward: {bad}")
        return 1
    tg = cfg["layouts"][cfg["env"]["layout"]]["target"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"stage": stage["name"], "created": f"{dt.date.today()}", "config": cfg_path,
                   "n": t["n"], "rng_seed": t["rng_seed"], "range": cfg["env"]["box_start"],
                   "nominal_box": {k: cfg["box"][k] for k in ("x", "y", "yaw")}, "target": tg,
                   "layout": cfg["env"]["layout"], "mass": cfg["box"]["mass"],
                   "note": "box poses (x, y in m, yaw in deg) for env.reset(options={'box': start}); "
                           + ("training checks (early stop) only, separate from the test set. " if checks else
                              "never used in training. ")
                           + "Both ducks touch the box in the first 1 s of push_forward from every start.",
                   "starts": starts}, f, indent=1)
    print(f"wrote {rel}: {len(starts)} starts, all with both ducks touching the box within 1 s of push_forward")
    return 0


def _row(name: str, s: dict) -> str:
    sh = s["push_share_a_mean"]
    share = "-" if math.isnan(sh) else f"{100 * sh:.0f} / {100 - 100 * sh:.0f}%"
    flags = ", ".join(f"{k} {v}" for k, v in sorted(s["flag_episodes"].items())) or "none"
    return (f"| {name} | {100 * s['success_rate']:.0f}% ({round(s['success_rate'] * s['n'])}/{s['n']}) | "
            f"{s['episodes_with_fall']}/{s['n']} | {s['box_lost']}/{s['n']} | {share} | {s['return_mean']:+.2f} | "
            f"{s['steps_mean']:.0f} | {s['final_dist_mean']:.2f} | "
            f"{', '.join(f'{k} {v}' for k, v in sorted(s['reasons'].items()))} | {flags} |")


def buckets(stats, key: str, bins):
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        val = (lambda st: st["dyaw"]) if key == "signed_angle" else (lambda st: difficulty(st)[key])
        sel = [s for s in stats if lo <= val(s["start"]) < hi]
        out.append((lo, hi, len(sel), sum(s["reason"] == "success" for s in sel)))
    return out


def plot(res: dict, path: str, title: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#3d3d3a", "xtick.color": "#3d3d3a",
                         "ytick.color": "#3d3d3a", "axes.titlesize": 11})
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), constrained_layout=True,
                             gridspec_kw={"width_ratios": [1, 1, 1.1]})
    order = [n for n in res if n not in HIGHLIGHT] + [n for n in HIGHLIGHT if n in res]   # highlights on top
    for ax, key, bins, unit in ((axes[0], "offset", OFFSET_BINS, "m"), (axes[1], "signed_angle", SIGNED_BINS, "deg")):
        any_b = buckets(next(iter(res.values())), key, bins)
        xs = list(range(len(any_b)))
        ends = []
        for name in order:
            b = buckets(res[name], key, bins)
            ys = [100 * w / n if n else float("nan") for _, _, n, w in b]
            hi = name in HIGHLIGHT
            ax.plot(xs, ys, color=HIGHLIGHT.get(name, MUTED), lw=2, marker="o", ms=8 if hi else 6,
                    alpha=1.0 if hi else 0.6, zorder=3 if hi else 2, markeredgecolor="white", markeredgewidth=1.5,
                    label=name)
            if hi:
                ends.append([ys[-1], ys[-1], name])
        ends.sort()
        for i in range(1, len(ends)):                    # spread the end labels at least 6 points apart
            ends[i][1] = max(ends[i][1], ends[i - 1][1] + 6)
        for y, ly, name in ends:
            ax.annotate(name, (xs[-1], y), xytext=(xs[-1] + 0.12, ly), va="center", fontsize=9, color="#3d3d3a")
        ax.set_xticks(xs, [f"{lo:g}-{hi:g} {unit}\n(n={n})" for lo, hi, n, _ in any_b])
        ax.set_xlim(-0.3, len(xs) - 0.3 + 0.6)
        ax.set_ylim(-3, 103)
        ax.set_ylabel("success rate (%)")
        ax.set_xlabel("box offset from nominal start" if key == "offset" else "box angle vs target, signed (deg)")
        ax.grid(axis="y", color="#e8e7e2", lw=0.8)
        ax.set_title(f"Success by {'offset' if key == 'offset' else 'angle'}")
        if key == "signed_angle":
            ax.set_xticks(xs, [f"{lo:+g}..{hi:+g}\n(n={n})" for lo, hi, n, _ in any_b])
    axes[0].legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    ax = axes[2]
    pol = list(res)[-1]                                  # the stage's own policy (listed last in test.policies)
    for won, mk, col, lab in ((True, "o", HIGHLIGHT.get(pol, "#2a78d6"), "success"), (False, "X", "#3d3d3a", "fail")):
        pts = [s["start"] for s in res[pol] if (s["reason"] == "success") == won]
        ax.scatter([p["dyaw"] for p in pts], [p["dy"] for p in pts], s=[60 + 600 * max(0, p["dx"] + 0.15) for p in pts],
                   marker=mk, color=col, edgecolors="white", linewidths=1.5, label=lab, alpha=0.9, zorder=3)
    ax.axvspan(-15, 15, color="#f0efec", zorder=0)
    ax.set_xlabel("box angle vs target (deg)")
    ax.set_ylabel("box sideways offset dy (m, > 0 = away from target)")
    ax.set_title(f"{pol}: each test start (bigger = closer to target)")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    ax.grid(color="#e8e7e2", lw=0.8)
    fig.suptitle(title, fontsize=12)
    fig.savefig(path, dpi=130, facecolor="white")


def cmd_eval(stage: dict, cfg: dict, cfg_path: str) -> int:
    t = stage["test"]
    ts = load_test_set(stage["test_set"])
    jobs = [(cfg_path, c, None) for c in t["controllers"]]
    for name, path in (t.get("policies") or {}).items():
        if os.path.exists(repo_path(policy_path(path))):
            jobs.append((cfg_path, name, path))
        else:
            print(f"skipping {name}: {path} not found")
    from copush.rl_eval import summarize
    with Pool(len(jobs)) as pool:
        res = dict(pool.map(_eval_one, jobs))
    res = {j[1]: res[j[1]] for j in jobs}
    summ = {n: summarize(s) for n, s in res.items()}
    rdir = repo_path(stage["results"])
    os.makedirs(rdir, exist_ok=True)
    keep = ("reason", "return", "steps", "fell", "push_share", "final_dist", "final_yaw_deg", "touch_s")
    with open(os.path.join(rdir, "test_set.json"), "w") as f:
        json.dump({"test_set": stage["test_set"], "n": len(ts["starts"]),
                   "summary": {n: {k: v for k, v in s.items() if k != "terms"} for n, s in summ.items()},
                   "episodes": {n: [dict({k: e[k] for k in keep}, id=e["start"]["id"],
                                         flags=sorted({f.split(':')[0] for f in e["flags"]})) for e in st]
                                for n, st in res.items()}}, f, indent=1)
    rng = ts["range"]
    md = [f"# Test set results: {stage['name']}", "",
          f"{len(ts['starts'])} fixed held-out starts ([{stage['test_set']}](../../test_sets/{os.path.basename(stage['test_set'])})), "
          f"box offset up to +-{rng['dx']:.2f} m (x) / +-{rng['dy']:.2f} m (y) and +-{rng['dyaw']:.0f} deg, both ducks "
          f"against the box. One deterministic episode per start, reward {cfg['reward']['version']}.", "",
          "| controller | success | falls | box lost | push share A / B | mean return | mean steps | final dist (m) | ends | monitor flags (episodes) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    md += [_row(n, s) for n, s in summ.items()]
    md += ["", "Success by difficulty (successes / starts in the bucket):", "",
           "| controller | " + " | ".join(f"offset {a:g}-{b:g} m" for a, b in zip(OFFSET_BINS[:-1], OFFSET_BINS[1:])) + " | "
           + " | ".join(f"angle {a:g}-{b:g} deg" for a, b in zip(ANGLE_BINS[:-1], ANGLE_BINS[1:])) + " |",
           "|---|" + "---|" * (len(OFFSET_BINS) + len(ANGLE_BINS) - 2)]
    for n, st in res.items():
        cells = [f"{w}/{k}" for *_, k, w in buckets(st, "offset", OFFSET_BINS)]
        cells += [f"{w}/{k}" for *_, k, w in buckets(st, "angle", ANGLE_BINS)]
        md.append(f"| {n} | " + " | ".join(cells) + " |")
    md += ["", "Success by signed angle (box yaw minus nominal, deg):", "",
           "| controller | " + " | ".join(f"{a:+g} to {b:+g}" for a, b in zip(SIGNED_BINS[:-1], SIGNED_BINS[1:])) + " |",
           "|---|" + "---|" * (len(SIGNED_BINS) - 1)]
    for n, st in res.items():
        md.append(f"| {n} | " + " | ".join(f"{w}/{k}" for *_, k, w in buckets(st, "signed_angle", SIGNED_BINS)) + " |")
    md += ["", "![success vs difficulty](difficulty.png)", ""]
    with open(os.path.join(rdir, "test_set.md"), "w") as f:
        f.write("\n".join(md))
    plot(res, os.path.join(rdir, "difficulty.png"),
         f"{stage['name']}: success on the {len(ts['starts'])}-start test set")
    print("\n".join(md))
    return 0


def cmd_side_by_side(stage: dict, cfg: dict, args) -> int:
    from copush.env import CoPushEnv
    from copush.video import record_episode
    ts = load_test_set(stage["test_set"])
    pols = stage["test"].get("policies") or {}
    if args.start is None:
        ep = json.load(open(os.path.join(repo_path(stage["results"]), "test_set.json")))["episodes"]
        won = {e["id"] for e in ep[args.right] if e["reason"] == "success"}
        lost = {e["id"] for e in ep[args.left] if e["reason"] != "success"
                and (not args.positive or ts["starts"][e["id"]]["dyaw"] > 15)}
        ids = sorted(won & lost, key=lambda i: (abs(ts["starts"][i]["dyaw"]), difficulty(ts["starts"][i])["offset"]))
        if not ids:
            print(f"no start where {args.right} succeeds and {args.left} does not; pass --start")
            return 1
        args.start = ids[-1]
    start = ts["starts"][args.start]
    vdir = os.path.join(repo_path(args.out or stage["out"]), "videos", "side_by_side")
    os.makedirs(vdir, exist_ok=True)
    seed = cfg["env"]["heldout_seeds"][0] + args.start
    paths = []
    for name in (args.left, args.right):
        env = CoPushEnv(cfg, split="eval")
        act = make_act_factory(name, pols.get(name))(env, seed)
        p = os.path.join(vdir, f"start{args.start:02d}_{name}.mp4")
        s = record_episode(env, act, p, seed=seed, video_cfg=cfg["video"], options={"box": start})
        print(f"{name}: {s['reason']} in {s['steps']} steps, return {s['return']:+.2f} -> {os.path.relpath(p, ROOT)}")
        paths.append(p)
    both = os.path.join(vdir, f"start{args.start:02d}_{args.left}_vs_{args.right}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", paths[0], "-i", paths[1], "-filter_complex",
                    "[0:v]scale=-2:270[a];[1:v]scale=-2:270[b];[a][b]hstack=inputs=2:shortest=0",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-an", both], check=True)
    print(f"start {args.start}: dx {start['dx']:+.3f} m, dy {start['dy']:+.3f} m, dyaw {start['dyaw']:+.1f} deg; "
          f"side by side ({args.left} left) -> {os.path.relpath(both, ROOT)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=("make", "eval", "side-by-side"))
    p.add_argument("--config", required=True)
    p.add_argument("--left", default="pivot_push")
    p.add_argument("--right", default="stage1")
    p.add_argument("--start", type=int, default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--checks", action="store_true", help="make: the check set instead of the test set")
    p.add_argument("--positive", action="store_true", help="side-by-side: only starts turned > +15 deg")
    args = p.parse_args()
    stage, cfg = load_stage(args.config)
    if args.cmd == "make":
        return cmd_make(stage, cfg, args.config, checks=args.checks)
    if args.cmd == "eval":
        return cmd_eval(stage, cfg, args.config)
    return cmd_side_by_side(stage, cfg, args)


if __name__ == "__main__":
    sys.exit(main())
