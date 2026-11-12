#!/usr/bin/env python3
"""RL plan step 3: sanity checks on copush.env before any training.

    scripts/rl.sh scripts/rl/check_env.py                # all checks, ~3-4 min
    scripts/rl.sh scripts/rl/check_env.py --episodes 5   # quicker

1. gymnasium check_env
2. speed: env steps/s and real-time factor, 1 env and 8 SubprocVecEnv workers
3. 20 episodes each of the baselines under the configured reward (fixed start, and
   again with randomized starts), plus random under v2 continuous falls (does a fallen duck get up?)
4. reward scale table: typical totals per outcome, configured reward and with continuous falls
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

from copush.config import effective_reward, load_config  # noqa: E402
from copush.env import BASELINES, CoPushEnv, baseline, make_env  # noqa: E402
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


# ── 3, 4: shared with scripts/rl/baselines.py ───────────────────────────────
from copush.rl_eval import episodes, fmt_block, scale_flags, scale_table, summarize  # noqa: E402


# ── report ───────────────────────────────────────────────────────────────────
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
    res["fixed"] = {b: summarize(episodes(cfg, b, n)) for b in BASELINES}
    rnd = copy.deepcopy(cfg)
    rnd["env"]["randomize"] = True
    res["random_starts"] = {b: summarize(episodes(rnd, b, n)) for b in BASELINES}
    cont = copy.deepcopy(cfg)
    cont["reward"]["fall_mode"] = "continuous"
    res["v2_continuous_random"] = {b: summarize(episodes(cont, b, n)) for b in ("random", "push_forward")}
    print("3. episodes done")

    res["scale"] = {}
    d0 = res["fixed"]["stand"]["final_dist_mean"]                # the layout's start distance
    for label, c in (("current reward", cfg), ("current reward, continuous falls", cont)):
        rows = scale_table(effective_reward(c), d0=d0)
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
          f"3. **Baseline episodes** (reward {cfg['reward']['version']}, layout {cfg['env']['layout']}; "
          "terms are per-episode sums)", "",
          fmt_block(f"fixed start, {n} episodes", res["fixed"]),
          fmt_block(f"randomized starts, {n} episodes", res["random_starts"]),
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
