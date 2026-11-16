#!/usr/bin/env python3
"""How often can each duck see its partner? No training: a trained decentral policy on a test set.

    scripts/rl.sh scripts/rl/visibility_check.py --config experiments/stage1-random-box-pose/config.yaml \
        --test-set experiments/test_sets/stage1.json --policy runs/decentral-p2-d2/model.zip \
        --out experiments/chirp-partner-sensing/visibility-check/results

A duck sees its partner while the partner is inside its front camera's field of view and range (copush.vision),
optionally not hidden behind the box. Three runs, one deterministic episode per start:
    exact        the policy acts on exact partner info (D2 as trained); the camera check (fov, range, and with the
                 box blocking) is only measured on its trajectories
    vision       the policy gets vision (copush.vision) with chirps (2 s, 30 deg) as the fallback: exact partner info
                 while in view, the last chirp out of view
    vision+box   the same, and the box blocks the view too
Reports, for each duck, the percent of steps (every state, from the first to the last of each episode) in which
it sees its partner, and the percent of steps in which both do.
Writes <out>/visibility.md and <out>/visibility.json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DUCKS = ("duck_a", "duck_b")


def _run(job):
    cfg_path, ts_path, policy, name, fov, rng_m, limit = job
    from stable_baselines3 import PPO
    from copush.decentral import decentral_action
    from copush.env import CoPushEnv
    from copush.experiments import load_stage, load_test_set, repo_path
    from copush.sim import BOX_HALF
    from copush.vision import visible
    _, cfg = load_stage(cfg_path)
    if name != "exact":
        cfg["chirp"] = {**cfg["chirp"], "enabled": True, "interval_s": 2.0, "direction_noise_deg": 30.0,
                        "distance": False, "heading": "zero"}
        cfg["vision"] = {**cfg["vision"], "enabled": True, "fov_deg": fov, "range_m": rng_m,
                         "occlusion": name == "vision+box"}
    starts = load_test_set(ts_path)["starts"][:limit]
    model = PPO.load(repo_path(policy), device="cpu")
    env = CoPushEnv(cfg, split="eval")
    seed0 = cfg["env"]["heldout_seeds"][0]
    steps = 0
    seen = {"no_box": {d: 0 for d in DUCKS}, "box": {d: 0 for d in DUCKS}}
    both = {"no_box": 0, "box": 0}
    episodes = []
    for i, s in enumerate(starts):
        env.reset(seed=seed0 + i, options={"box": s})
        ep = {"id": s["id"], "steps": 0, "seen_box": 0, "reason": None}
        while True:
            st = env.state
            v = {k: {d: visible(st, d, fov, rng_m, half) for d in DUCKS}
                 for k, half in (("no_box", None), ("box", BOX_HALF[:2]))}
            for k in v:
                for d in DUCKS:
                    seen[k][d] += v[k][d]
                both[k] += all(v[k].values())
            steps += 1
            ep["steps"] += 1
            ep["seen_box"] += sum(v["box"].values())
            _, _, te, tr, info = env.step(decentral_action(model, env.state, True))
            if te or tr:
                ep["reason"] = info["episode_stats"]["reason"]
                break
        episodes.append(ep)
    pct = lambda n: round(100.0 * n / steps, 1)                                    # noqa: E731
    return name, {"episodes": len(starts), "states": steps,
                  "success": sum(e["reason"] == "success" for e in episodes),
                  **{k: {"duck_a": pct(seen[k]["duck_a"]), "duck_b": pct(seen[k]["duck_b"]), "both": pct(both[k])}
                     for k in seen}}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--test-set", required=True)
    p.add_argument("--policy", required=True, help="a decentral (D2) model.zip")
    p.add_argument("--out", required=True)
    p.add_argument("--fov", type=float, default=120.0, help="deg, placeholder until measured on the real camera")
    p.add_argument("--limit", type=int, default=None, help="only the first N starts (smoke tests)")
    p.add_argument("--range", type=float, default=0.8, dest="range_m", help="m, placeholder")
    a = p.parse_args()
    jobs = [(a.config, a.test_set, a.policy, n, a.fov, a.range_m, a.limit) for n in ("exact", "vision", "vision+box")]
    with Pool(len(jobs)) as pool:
        res = dict(pool.map(_run, jobs))
    from copush.experiments import repo_path
    out = repo_path(a.out)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "visibility.json"), "w") as f:
        json.dump({"policy": a.policy, "fov_deg": a.fov, "range_m": a.range_m, "runs": res}, f, indent=1)
    md = [f"# Visibility check: {a.policy}", "",
          f"Front camera field of view {a.fov:g} deg, range {a.range_m:g} m (placeholders). One deterministic episode per "
          f"start of `{a.test_set}`. Percent of steps in which a duck sees its partner.", "",
          "| run | what the policy acts on | box blocks the view | duck A sees B | duck B sees A | both see each other | "
          "episodes won |", "|---|---|---|---|---|---|---|"]
    acts = {"exact": "exact partner info (D2 as trained)", "vision": "vision, chirps out of view",
            "vision+box": "vision, chirps out of view"}
    for name, r in res.items():
        for k, label in (("no_box", "no"), ("box", "yes")):
            if name == "vision" and k == "box" or name == "vision+box" and k == "no_box":
                continue                                                           # that run is only valid for its own setting
            md.append(f"| {name} | {acts[name]} | {label} | {r[k]['duck_a']}% | {r[k]['duck_b']}% | {r[k]['both']}% | "
                      f"{r['success']}/{r['episodes']} |")
    with open(os.path.join(out, "visibility.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
