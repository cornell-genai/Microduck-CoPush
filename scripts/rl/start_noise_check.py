#!/usr/bin/env python3
"""Reset-only check of a start-noise level (no training, no policy): how often starts are redrawn, how often a reset runs
out of redraws, and how often a duck is already down when the controller takes its first step.

    scripts/rl.sh scripts/rl/start_noise_check.py --config experiments/d2-steering/night5/run-l2/config.yaml
    scripts/rl.sh scripts/rl/start_noise_check.py --config ... --resets 500 --tighten     # night 5's rule

Per reset (training seeds 0, 1, ..., resets - 1, split="train", the config's box starts):
    redraws            draws that failed the start check (copush.env._start_ok) and were drawn again
    out of redraws     resets where every one of the 1 + max_resamples draws failed (the env keeps the last, failed one)
    down at first step a duck is down in the state the controller sees first (after the settle, before any action)
    down in step 1     a duck goes down during the first 0.2 s env step, with both ducks commanded straight ahead at
                       0.15 m/s (extra information, not part of the rule)
--tighten applies night 5's rule: while the redraw rate is above 5% or the down-at-first-step rate above 3%, the heading limit
is lowered by 5 degrees and the check runs again (never below 5 degrees). Prints the final level.
"""
from __future__ import annotations

import argparse
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from copush.experiments import load_stage  # noqa: E402

MAX_REDRAW, MAX_DOWN, STEP_DEG, MIN_DEG = 0.05, 0.03, 5.0, 5.0


def check(cfg: dict, resets: int) -> dict:
    from copush.env import CoPushEnv, cmd_to_action
    env = CoPushEnv(copy.deepcopy(cfg), split="train")
    act = cmd_to_action(0.15, 0.0, 0.15, 0.0)
    mx = env.max_resamples + 1
    out = dict(resets=resets, draws=0, redraws=0, exhausted=0, down0=0, down1=0)
    for i in range(resets):
        d0, r0 = env.start_draws, env.start_resamples
        env.reset(seed=i)
        dr, rr = env.start_draws - d0, env.start_resamples - r0
        out["draws"] += dr
        out["redraws"] += rr
        out["exhausted"] += rr >= mx
        st = env.state
        down0 = any(st[d]["down"] for d in ("duck_a", "duck_b"))
        out["down0"] += down0
        if not down0:
            env.step(act)
            out["down1"] += any(env.state[d]["down"] for d in ("duck_a", "duck_b"))
    env.close()
    out["redraw_rate"] = out["redraws"] / max(1, out["draws"])
    out["exhausted_rate"] = out["exhausted"] / resets
    out["down0_rate"] = out["down0"] / resets
    out["down1_rate"] = out["down1"] / resets
    return out


def fmt(sn: dict) -> str:
    return (f"heading {sn['duck_heading_std_deg']:g} deg (+-{sn.get('duck_heading_limit_deg')}), spacing "
            f"{100 * sn['duck_spacing_std_m']:g} cm (+-{100 * (sn.get('duck_spacing_limit_m') or 0):g}), setback "
            f"{100 * sn['duck_setback_std_m']:g} cm (+{100 * (sn.get('duck_setback_back_limit_m') or 0):g} back / "
            f"-{100 * (sn.get('duck_setback_forward_limit_m') or 0):g} forward)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", required=True)
    p.add_argument("--resets", type=int, default=500)
    p.add_argument("--tighten", action="store_true", help="night 5's rule: lower the heading limit by 5 deg until it passes")
    a = p.parse_args()
    _, cfg = load_stage(a.config)
    while True:
        r = check(cfg, a.resets)
        sn = cfg["start_noise"]
        ok = r["redraw_rate"] <= MAX_REDRAW and r["down0_rate"] <= MAX_DOWN
        print(f"{fmt(sn)}\n  {a.resets} resets, {r['draws']} draws: redraw rate {100 * r['redraw_rate']:.1f}% "
              f"({r['redraws']}), out of redraws {100 * r['exhausted_rate']:.1f}% ({r['exhausted']}), "
              f"down at first step {100 * r['down0_rate']:.1f}% ({r['down0']}), down in step 1 {100 * r['down1_rate']:.1f}% "
              f"({r['down1']}): {'PASS' if ok else 'FAIL'} (redraw <= 5%, down at first step <= 3%)", flush=True)
        lim = sn.get("duck_heading_limit_deg")
        if ok or not a.tighten:
            break
        if lim is None or lim - STEP_DEG < MIN_DEG:
            print("cannot tighten the heading limit further", flush=True)
            break
        sn["duck_heading_limit_deg"] = lim - STEP_DEG
        print(f"  -> heading limit {lim:g} -> {sn['duck_heading_limit_deg']:g} deg, checking again", flush=True)
    print(f"FINAL: {fmt(cfg['start_noise'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
