#!/usr/bin/env python3
"""RL plan step 3: sanity checks on copush.env before any training.

    scripts/rl.sh scripts/rl/check_env.py                # all checks, ~3-4 min
    scripts/rl.sh scripts/rl/check_env.py --episodes 5   # quicker

1. gymnasium check_env
2. speed: env steps/s and real-time factor, 1 env and 8 SubprocVecEnv workers
3. 20 episodes each of random / zero / stand / push_forward under reward v1 (fixed start, and
   again with randomized starts), plus random under v2 continuous falls (does a fallen duck get up?)
4. reward scale table: typical totals per outcome under v1 and v2 continuous falls
5. one video each of random, zero and push_forward -> runs/<run_id>/videos/

Everything goes to runs/rl-checks-<timestamp>/ (report.md, results.json, videos/).
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from copush.config import load_config  # noqa: E402
from copush.env import BASELINES, CoPushEnv, baseline, make_env  # noqa: E402
from copush.rewards import TERMS, StepSummary, TaskReward  # noqa: E402
from copush.video import VideoLog  # noqa: E402

DUCKS = ("duck_a", "duck_b")


# ── 2. speed ─────────────────────────────────────────────────────────────────
def speed(cfg, n_single=300, n_envs=8, n_vec=100):
    env = CoPushEnv(cfg)
    env.reset(seed=0)
    rng = np.random.default_rng(0)
    t0 = time.perf_counter()
    for _ in range(n_single):
        _, _, te, tr, _ = env.step(rng.uniform(-1, 1, 4))
        if te or tr:
            env.reset()
    wall = time.perf_counter() - t0
    single = {"steps": n_single, "wall_s": wall, "steps_per_s": n_single / wall,
              "rtf": n_single * env.dt / wall}
    from stable_baselines3.common.vec_env import SubprocVecEnv
    vec = SubprocVecEnv([make_env(cfg) for _ in range(n_envs)])
    vec.seed(0)
    vec.reset()
    t0 = time.perf_counter()
    for _ in range(n_vec):
        vec.step(rng.uniform(-1, 1, (n_envs, 4)).astype(np.float32))
    wall = time.perf_counter() - t0
    vec.close()
    par = {"envs": n_envs, "steps": n_vec * n_envs, "wall_s": wall, "steps_per_s": n_vec * n_envs / wall,
           "rtf": n_vec * n_envs * env.dt / wall}
    return {"single": single, "parallel": par}


# ── 3. baseline episodes ─────────────────────────────────────────────────────
def episodes(cfg, name, n, seed0=0):
    env = CoPushEnv(cfg)
    out = []
    for i in range(n):
        act = baseline(name, env, seed=seed0 + i)
        obs, _ = env.reset(seed=seed0 + i)
        while True:
            obs, _, te, tr, info = env.step(act(obs))
            if te or tr:
                out.append(info["episode_stats"])
                break
    return out


def summarize(stats):
    ret = np.array([s["return"] for s in stats])
    terms = {k: (float(np.mean([s["terms"][k] for s in stats])), float(np.std([s["terms"][k] for s in stats])))
             for k in TERMS}
    reasons = {}
    for s in stats:
        reasons[s["reason"]] = reasons.get(s["reason"], 0) + 1
    shares = [s["push_share"]["duck_a"] for s in stats if not math.isnan(s["push_share"]["duck_a"])]
    flags = {}
    for s in stats:
        for f in {f.split(":")[0] for f in s["flags"]}:
            flags[f] = flags.get(f, 0) + 1
    return {"n": len(stats), "return_mean": float(ret.mean()), "return_std": float(ret.std()),
            "return_min": float(ret.min()), "return_max": float(ret.max()), "terms": terms,
            "success_rate": reasons.get("success", 0) / len(stats),
            "episodes_with_fall": sum(any(s["fell"].values()) for s in stats), "reasons": reasons,
            "push_share_a_mean": float(np.mean(shares)) if shares else float("nan"),
            "pushing_episodes": len(shares),
            "contact_time_mean": {d: float(np.mean([s["contact_time"][d] for s in stats])) for d in DUCKS},
            "final_dist_mean": float(np.mean([s["final_dist"] for s in stats])),
            "min_dist_mean": float(np.mean([s["min_dist"] for s in stats])),
            "stood_up": {d: sum(s["stood_up"][d] > 0 for s in stats) for d in DUCKS},
            "flag_episodes": flags}


# ── 4. scale table ───────────────────────────────────────────────────────────
def scenario(rcfg, name):
    """Synthetic but realistic episodes (start 0.85 m, yaw error 0), through TaskReward itself."""
    task = TaskReward(rcfg)
    cont = rcfg["fall_mode"] == "continuous"
    d0, dt_ = 0.85, 0.2
    total, steps, reason = 0.0, 0, None

    def run(dists, yaws, fall_at=None, lost_at=None, success_from=None, down_after=None):
        nonlocal total, steps, reason
        held = 0.0
        for k in range(1, len(dists)):
            if success_from is not None and k >= success_from:
                held += dt_
            s = StepSummary(dists[k - 1], dists[k], yaws[k - 1], yaws[k], success_held_s=held,
                            fell=(fall_at == k), down_s=dt_ if (down_after is not None and k >= down_after) else 0.0,
                            box_lost=(lost_at == k))
            t, term, why = task.step(s)
            total += sum(t.values())
            steps = k
            if term:
                reason = why
                return
        reason = "timeout"

    lin = lambda a, b, n: list(np.linspace(a, b, n + 1))
    if name == "success (12 s)":
        run(lin(d0, 0.08, 60) + [0.08] * 6, lin(0, math.radians(5), 60) + [math.radians(5)] * 6, success_from=61)
    elif name == "fall early (2 s, no progress)":
        run([d0] * 101, [0.0] * 101, fall_at=10, down_after=10 if cont else None)
    elif name == "fall late (15 s, after 0.40 m)":
        run(lin(d0, 0.45, 75) + [0.45] * 25, [0.0] * 101, fall_at=75, down_after=75 if cont else None)
    elif name == "box lost (10 s, after 0.25 m)":
        run(lin(d0, 0.60, 50) + [0.60] * 50, [0.0] * 101, lost_at=50)
    elif name == "timeout, partial progress (0.40 m)":
        run(lin(d0, 0.45, 100), lin(0, math.radians(10), 100))
    elif name == "timeout, no progress":
        run([d0] * 101, [0.0] * 101)
    elif name == "timeout, overshoot (like push_forward)":
        run(lin(d0, 0.38, 50) + lin(0.38, 1.15, 50)[1:], lin(0, math.radians(60), 100))
    return {"outcome": name, "total": total, "steps": steps, "ends": reason}


SCENARIOS = ("success (12 s)", "fall early (2 s, no progress)", "fall late (15 s, after 0.40 m)",
             "box lost (10 s, after 0.25 m)", "timeout, partial progress (0.40 m)", "timeout, no progress",
             "timeout, overshoot (like push_forward)")


def scale_flags(rows):
    tot = {r["outcome"]: r["total"] for r in rows}
    out = []
    succ = tot["success (12 s)"]
    for k, v in tot.items():
        if not k.startswith("success") and v >= succ:
            out.append(f"{k} ({v:+.2f}) scores >= success ({succ:+.2f})")
    early = tot["fall early (2 s, no progress)"]
    for k, v in tot.items():
        if k.startswith("timeout") and early > v:
            out.append(f"falling early ({early:+.2f}) beats continuing to '{k}' ({v:+.2f})")
    lost = tot["box lost (10 s, after 0.25 m)"]
    for k, v in tot.items():
        if k.startswith("timeout") and lost > v:
            out.append(f"losing the box ({lost:+.2f}) beats continuing to '{k}' ({v:+.2f})")
    return out


# ── report ───────────────────────────────────────────────────────────────────
def fmt_block(title, res):
    lines = [f"### {title}", "",
             "| controller | return mean ± sd [min, max] | " + " | ".join(TERMS) +
             " | success | falls | ends | push share A | contact s A / B | closest m | final m | flags (episodes) |",
             "|---|---|" + "---|" * len(TERMS) + "---|---|---|---|---|---|---|---|"]
    for name, s in res.items():
        terms = " | ".join(f"{m:+.2f} ± {sd:.2f}" for m, sd in (s["terms"][k] for k in TERMS))
        share = "-" if math.isnan(s["push_share_a_mean"]) else f"{100 * s['push_share_a_mean']:.0f}% ({s['pushing_episodes']} ep)"
        lines.append(f"| {name} | {s['return_mean']:+.2f} ± {s['return_std']:.2f} [{s['return_min']:+.2f}, {s['return_max']:+.2f}] | "
                     f"{terms} | {100 * s['success_rate']:.0f}% | {s['episodes_with_fall']}/{s['n']} | "
                     f"{', '.join(f'{k} {v}' for k, v in sorted(s['reasons'].items()))} | {share} | "
                     f"{s['contact_time_mean']['duck_a']:.1f} / {s['contact_time_mean']['duck_b']:.1f} | "
                     f"{s['min_dist_mean']:.2f} | {s['final_dist_mean']:.2f} | "
                     f"{', '.join(f'{k} {v}' for k, v in sorted(s['flag_episodes'].items())) or 'none'} |")
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--episodes", type=int, default=20)
    args = p.parse_args()
    cfg = load_config()
    run_id = "rl-checks-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(ROOT, "runs", run_id)
    os.makedirs(run_dir)
    res = {"run_id": run_id}

    from gymnasium.utils.env_checker import check_env
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        check_env(CoPushEnv(cfg), skip_render_check=True)
    res["check_env"] = {"passed": True, "warnings": sorted({str(x.message) for x in w})}
    print("1. check_env passed;", len(res["check_env"]["warnings"]), "warning(s)")

    res["speed"] = speed(cfg)
    print("2. speed", json.dumps(res["speed"], indent=1))

    n = args.episodes
    res["v1_fixed"] = {b: summarize(episodes(cfg, b, n)) for b in BASELINES}
    rnd = copy.deepcopy(cfg)
    rnd["env"]["randomize"] = True
    res["v1_random_starts"] = {b: summarize(episodes(rnd, b, n)) for b in BASELINES}
    cont = copy.deepcopy(cfg)
    cont["reward"]["fall_mode"] = "continuous"
    res["v2_continuous_random"] = {b: summarize(episodes(cont, b, n)) for b in ("random", "push_forward")}
    print("3. episodes done")

    res["scale"] = {}
    for label, rc in (("v1", cfg["reward"]), ("v2 continuous falls", cont["reward"])):
        rows = [scenario(rc, s) for s in SCENARIOS]
        res["scale"][label] = {"rows": rows, "flags": scale_flags(rows)}
    print("4. scale table done")

    vlog = VideoLog(run_dir, cfg["video"])
    for b in ("random", "zero", "push_forward"):
        env = CoPushEnv(cfg)
        vlog.record(env, baseline(b, env, seed=0), training_step=0, reason="baseline", seed=0, label=b)
    res["videos"] = sorted(f for f in os.listdir(vlog.dir) if f.endswith(".mp4"))
    print("5. videos", res["videos"])

    with open(os.path.join(run_dir, "results.json"), "w") as f:
        json.dump(res, f, indent=1)
    sp = res["speed"]
    md = [f"# RL environment checks ({run_id})", "",
          f"1. **check_env:** passed. Warnings: {'; '.join(res['check_env']['warnings']) or 'none'}", "",
          f"2. **Speed (random actions):** 1 env {sp['single']['steps_per_s']:.0f} steps/s "
          f"({sp['single']['rtf']:.1f}x real time); {sp['parallel']['envs']} SubprocVecEnv workers "
          f"{sp['parallel']['steps_per_s']:.0f} steps/s total ({sp['parallel']['rtf']:.1f}x real time)", "",
          "3. **Baseline episodes** (reward v1 unless stated; terms are per-episode sums)", "",
          fmt_block(f"v1, fixed start, {n} episodes", res["v1_fixed"]),
          fmt_block(f"v1, randomized starts, {n} episodes", res["v1_random_starts"]),
          fmt_block(f"v2 continuous falls, fixed start, {n} episodes", res["v2_continuous_random"]),
          "Stood back up after a fall (episodes): " + json.dumps(
              {b: s["stood_up"] for b, s in res["v2_continuous_random"].items()}), "",
          "4. **Reward scale** (synthetic episodes through TaskReward)", ""]
    for label, sc in res["scale"].items():
        md += [f"### {label}", "", "| outcome | total | ends at step | ends by |", "|---|---|---|---|"]
        md += [f"| {r['outcome']} | {r['total']:+.2f} | {r['steps']} | {r['ends']} |" for r in sc["rows"]]
        md += ["", "Flags: " + ("; ".join(sc["flags"]) or "none"), ""]
    md += ["5. **Videos:** see [videos/index.md](videos/index.md)", ""]
    with open(os.path.join(run_dir, "report.md"), "w") as f:
        f.write("\n".join(md))
    print(f"\nwrote runs/{run_id}/report.md")


if __name__ == "__main__":
    main()
