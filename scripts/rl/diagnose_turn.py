#!/usr/bin/env python3
"""Stage 1b diagnosis: is the stage 1 turn-direction blind spot physical or learned? (no training)

    scripts/rl.sh scripts/rl/diagnose_turn.py --config experiments/stage1-random-box-pose/config.yaml \
        --out experiments/stage1b-turn-direction-fix/results

1. side split   every controller's stage 1 test-set results by box angle sign (< -15, -15..+15, > +15 deg)
2. turning test both ducks start against the box on Shoe Push (nominal pose plus a small jitter per
                trial) and hold one command for TURN_S: full turn left, full turn right, duck A
                faster, duck B faster, plus the two pivots (one duck held on velstand, the other
                pushes alone, as pivot_push does). Box yaw rate in deg/s (> 0 counter-clockwise).
3. needed       per test start, the rotation the box needs: to aim its push face at the target
                (the pivot_push geometry) and to end inside the yaw tolerance.
4. realized     what the stage 1 policy actually does on each test start: the fastest 2 s box
                rotation it reaches in each direction.
Writes <out>/diagnosis.json and <out>/diagnosis.md.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copush.experiments import load_stage, load_test_set, repo_path  # noqa: E402
from copush.state import wrap_angle  # noqa: E402

SIDES = (("< -15", -90.0, -15.0), ("-15 to +15", -15.0, 15.0), ("> +15", 15.0, 90.0))
TURN_S, TRIALS, PUSH_VX = 6.0, 10, 0.2
CONDITIONS = {                                   # (A vx, A vyaw, B vx, B vyaw), m/s and rad/s
    "full turn left": (PUSH_VX, 1.5, PUSH_VX, 1.5),
    "full turn right": (PUSH_VX, -1.5, PUSH_VX, -1.5),
    "duck A faster": (0.3, 0.0, 0.1, 0.0),
    "duck B faster": (0.1, 0.0, 0.3, 0.0),
}
PIVOTS = {                                       # extra: one duck held on velstand, the other pushes alone (pivot_push)
    "pivot: A pushes, B held": ((PUSH_VX, 0.0, 0.0, 0.0), "duck_b"),
    "pivot: B pushes, A held": ((0.0, 0.0, PUSH_VX, 0.0), "duck_a"),
}


def side_of(dyaw: float) -> str:
    return next(n for n, lo, hi in SIDES if lo <= dyaw < hi)


def side_split(stage: dict) -> dict:
    ts = load_test_set(stage["test_set"])
    ep = json.load(open(os.path.join(repo_path(stage["results"]), "test_set.json")))["episodes"]
    out = {}
    for name, eps in ep.items():
        row = {n: [0, 0] for n, *_ in SIDES}
        for e in eps:
            r = row[side_of(ts["starts"][e["id"]]["dyaw"])]
            r[0] += e["reason"] == "success"
            r[1] += 1
        out[name] = row
    return out


def turning_test(cfg: dict) -> dict:
    from copush.env import CoPushEnv, cmd_to_action
    env = CoPushEnv(cfg, split="eval")
    rng = np.random.default_rng(20261112)
    jit = [{"dx": rng.uniform(-0.01, 0.01), "dy": rng.uniform(-0.01, 0.01), "dyaw": rng.uniform(-3, 3)}
           for _ in range(TRIALS)]
    b0, seed0 = env.box0, cfg["env"]["heldout_seeds"][0]
    out = {}
    conds = {n: (c, None) for n, c in CONDITIONS.items()} | PIVOTS
    for name, (cmd, held) in conds.items():
        act = cmd_to_action(*cmd)
        trials = []
        for i, j in enumerate(jit):
            env.reset(seed=seed0 + i, options={"box": {"x": b0["x"] + j["dx"], "y": b0["y"] + j["dy"],
                                                       "yaw": b0["yaw"] + j["dyaw"]}})
            for d in ("duck_a", "duck_b"):
                env.set_hold(d, d == held)
            yaw, t0 = env.state["box"]["yaw"], env.state["t"]
            turned, both, n, end = 0.0, 0, 0, "ok"
            while env.state["t"] - t0 < TURN_S - 1e-9:
                _, _, te, tr, info = env.step(act)
                st = env.state
                turned += wrap_angle(st["box"]["yaw"] - yaw)
                yaw = st["box"]["yaw"]
                n += 1
                both += all(st["contact"][d]["in_contact"] for d in ("duck_a", "duck_b"))
                if te or tr:
                    end = info["episode_stats"]["reason"]
                    break
            dt = env.state["t"] - t0
            trials.append({"rate": math.degrees(turned) / dt, "turned_deg": math.degrees(turned), "s": dt,
                           "both_contact": both / max(n, 1), "end": end})
        r = np.array([t["rate"] for t in trials])
        out[name] = {"mean": float(r.mean()), "std": float(r.std()), "min": float(r.min()), "max": float(r.max()),
                     "both_contact": float(np.mean([t["both_contact"] for t in trials])),
                     "ends": sorted({t["end"] for t in trials}), "trials": trials}
    return out


def needed(cfg: dict, starts) -> list:
    """Per start: aim = rotation to point the push face at the target (pivot_push err, deg, > 0
    counter-clockwise); final = smallest rotation that ends within the yaw tolerance of the target."""
    tg, tol = cfg["layouts"][cfg["env"]["layout"]]["target"], cfg["reward"]["success_yaw_deg"]
    out = []
    for s in starts:
        bearing = math.atan2(tg["y"] - s["y"], tg["x"] - s["x"])
        err = wrap_angle(bearing - math.radians(s["yaw"] - 90.0))
        aim = math.degrees((err + math.pi / 2) % math.pi - math.pi / 2)
        e = (s["yaw"] - tg["yaw"] + 90.0) % 180.0 - 90.0          # 180-degree symmetric box
        final = 0.0 if abs(e) <= tol else -math.copysign(abs(e) - tol, e)
        out.append({"id": s["id"], "dyaw": s["dyaw"], "side": side_of(s["dyaw"]), "aim_deg": aim, "final_deg": final})
    return out


def realized(cfg: dict, starts, policy_path: str) -> list:
    """Stage 1 policy on each test start: fastest box rotation over any 2 s window, each direction."""
    from test_set import make_act_factory
    from copush.env import CoPushEnv
    env = CoPushEnv(cfg, split="eval")
    make_act = make_act_factory("stage1", policy_path)
    seed0, w = cfg["env"]["heldout_seeds"][0], 10        # 10 env steps = 2 s
    out = []
    for i, s in enumerate(starts):
        act = make_act(env, seed0 + i)
        obs, _ = env.reset(seed=seed0 + i, options={"box": s})
        yaws = [env.state["box"]["yaw"]]
        while True:
            obs, _, te, tr, info = env.step(act(obs))
            yaws.append(env.state["box"]["yaw"])
            if te or tr:
                break
        cum = np.concatenate([[0.0], np.cumsum([wrap_angle(b - a) for a, b in zip(yaws, yaws[1:])])])
        win = [math.degrees(cum[k + w] - cum[k]) / 2.0 for k in range(len(cum) - w)] or [0.0]
        out.append({"id": s["id"], "side": side_of(s["dyaw"]), "success": info["episode_stats"]["reason"] == "success",
                    "max_ccw": max(0.0, max(win)), "max_cw": max(0.0, -min(win)),
                    "net_deg": math.degrees(cum[-1])})
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="the stage 1 config (its test set and results)")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    stage, cfg = load_stage(args.config)
    starts = load_test_set(stage["test_set"])["starts"]
    split = side_split(stage)
    turn = turning_test(cfg)
    need = needed(cfg, starts)
    real = realized(cfg, starts, stage["test"]["policies"]["stage1"])
    os.makedirs(repo_path(args.out), exist_ok=True)
    with open(os.path.join(repo_path(args.out), "diagnosis.json"), "w") as f:
        json.dump({"side_split": split, "turning_test": turn, "needed": need, "realized_stage1": real}, f, indent=1)

    md = ["# Stage 1b diagnosis", "", "## 1. Stage 1 test set by box angle sign (successes / starts)", "",
          "| controller | " + " | ".join(f"{n} deg" for n, *_ in SIDES) + " |", "|---|---|---|---|"]
    md += [f"| {n} | " + " | ".join(f"{w}/{k}" for w, k in row.values()) + " |" for n, row in split.items()]
    md += ["", f"## 2. Turning test ({TRIALS} trials each, {TURN_S:g} s, nominal pose +-1 cm / +-3 deg)", "",
           "Box yaw rate, deg/s; > 0 is counter-clockwise (CCW), < 0 clockwise (CW). Duck A is on the left of the push direction.", "",
           "| condition | mean | std | min | max | both ducks in contact | episode ends |", "|---|---|---|---|---|---|---|"]
    md += [f"| {n} | {r['mean']:+.2f} | {r['std']:.2f} | {r['min']:+.2f} | {r['max']:+.2f} | {100 * r['both_contact']:.0f}% | "
           f"{', '.join(r['ends'])} |" for n, r in turn.items()]
    md += ["", "## 3. Rotation each side needs (mean over test starts, deg; > 0 CCW)", "",
           "| side | starts | aim at target | end within tolerance |", "|---|---|---|---|"]
    for n, *_ in SIDES:
        rows = [x for x in need if x["side"] == n]
        md.append(f"| {n} | {len(rows)} | {np.mean([x['aim_deg'] for x in rows]):+.1f} "
                  f"({min(x['aim_deg'] for x in rows):+.0f} to {max(x['aim_deg'] for x in rows):+.0f}) | "
                  f"{np.mean([x['final_deg'] for x in rows]):+.1f} |")
    md += ["", "## 4. What the stage 1 policy does (fastest 2 s box rotation, deg/s, mean over starts)", "",
           "| side | starts | success | fastest CW | fastest CCW | net rotation (deg) |", "|---|---|---|---|---|---|"]
    for n, *_ in SIDES:
        rows = [x for x in real if x["side"] == n]
        md.append(f"| {n} | {len(rows)} | {sum(x['success'] for x in rows)}/{len(rows)} | "
                  f"{np.mean([x['max_cw'] for x in rows]):.1f} | {np.mean([x['max_ccw'] for x in rows]):.1f} | "
                  f"{np.mean([x['net_deg'] for x in rows]):+.1f} |")
    with open(os.path.join(repo_path(args.out), "diagnosis.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
