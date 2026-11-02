#!/usr/bin/env python3
"""B0 evaluator: one duck pushing the Shoe Push box, Shoe Push policy vs velstand.

    uv run --project ../microduck_rl python scripts/b0/eval_push.py                       # backlash robot
    uv run --project ../microduck_rl python scripts/b0/eval_push.py --robot nobacklash    # first report's robot
    uv run --project ../microduck_rl python scripts/b0/eval_push.py --quick               # 1 fixed trial, 4 s

Per condition: 10 seeded trials x 10 s. Box 28 x 10 x 9 cm, mass ~ U(0.05, 0.30) kg, yaw ~ 90 deg +
U(-45, 45) deg (long side facing the robot at 0), centre 0.20 m ahead (forward scene) or behind
(backward scene). Command straight +0.2 / -0.2 m/s. BAM vin 7.4 V, sag 0.1 (infer_policy defaults).
Trial i uses seed+i for every condition, so conditions are paired.

Metrics:
  box travel   box-centre displacement projected on the push direction (robot's initial heading
               for forward, its opposite for backward)
  box |disp|   magnitude of the box-centre displacement (ignores curving)
  robot travel same projection for the trunk
  fall         trunk tilt > 60 deg or trunk z < 0.07 m at any time (trial stops)
  box lost     box centre > 0.40 m (horizontal) from the trunk at any time
  heading      final trunk yaw minus initial yaw (deg); mean signed and mean |.|
  contact      share of robot->box contact impulse by body group
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

import b0lib as L


def summarize(rows):
    def mean(k):
        return float(np.mean([r[k] for r in rows]))
    tot = {}
    for r in rows:
        for g, v in r["contact_impulse"].items():
            tot[g] = tot.get(g, 0.0) + v
    s = sum(tot.values())
    share = {g: v / s for g, v in sorted(tot.items(), key=lambda kv: -kv[1])} if s > 0 else {}
    return dict(
        n=len(rows),
        box_travel=mean("box_travel"),
        box_travel_std=float(np.std([r["box_travel"] for r in rows])),
        box_disp=float(np.mean([np.hypot(*r["box_dxy"]) for r in rows])),
        robot_travel=mean("robot_travel"),
        fall_rate=mean("fell"), lost_rate=mean("lost"),
        heading_mean=mean("heading_deg"),
        heading_abs=float(np.mean([abs(r["heading_deg"]) for r in rows])),
        contact_share=share,
    )


def fmt_share(share):
    return ", ".join(f"{g} {100 * v:.0f}%" for g, v in share.items() if v >= 0.01) or "none"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--robot", choices=("backlash", "nobacklash"), default="backlash",
                    help="robot_groundcontact_backlash.xml (default; duck-sim's robot) or robot_groundcontact.xml")
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--speed", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--mass-range", type=float, nargs=2, default=(0.05, 0.30))
    ap.add_argument("--yaw-range-deg", type=float, default=45.0)
    ap.add_argument("--quick", action="store_true", help="1 fixed trial per condition (150 g, yaw 0), 4 s")
    ap.add_argument("--json", default=None, help="write per-trial rows + summaries here")
    args = ap.parse_args()
    L.check_policies()

    sp = args.speed
    conds = []  # (label, policy key, direction, vx, push_sign, box_x)
    for direction, sign in (("forward", +1), ("backward", -1)):
        for key in (direction, "velstand v6", "velstand v8"):
            conds.append((key, direction, sign * sp, sign, sign * L.BOX_OFFSET))

    trials = 1 if args.quick else args.trials
    duration = 4.0 if args.quick else args.duration
    boxes = L.paired_boxes(trials, args.seed, tuple(args.mass_range), args.yaw_range_deg, fixed=args.quick)

    results = []
    for key, direction, vx, sign, bx in conds:
        t0 = time.time()
        sc = L.scene(direction, args.robot)
        r = L.Rollout(sc, L.POLICY[key])
        rows = [r.run(vx, duration, sign, bx, m_, y_) for (m_, y_) in boxes]
        s = summarize(rows)
        results.append(dict(policy=key, scene=os.path.basename(sc), direction=direction, vx=vx,
                            summary=s, trials=rows))
        if args.quick:
            o = rows[0]
            print(f"{key:12s} {direction:8s} vx={vx:+.2f} {duration:.0f}s: box travel {o['box_travel']:+.3f} m, "
                  f"robot travel {o['robot_travel']:+.3f} m, fell={o['fell']} lost={o['lost']} "
                  f"heading {o['heading_deg']:+.0f} deg, contact: {fmt_share(s['contact_share'])}")
        else:
            print(f"  done {key:12s} {direction:8s} in {time.time() - t0:.0f}s", file=sys.stderr)

    if not args.quick:
        print(f"\nrobot={args.robot}: {trials} trials x {duration:.0f} s, |cmd| {sp} m/s, box mass "
              f"U{tuple(args.mass_range)} kg, yaw +-{args.yaw_range_deg:.0f} deg, seeds "
              f"{args.seed}..{args.seed + trials - 1}, BAM vin 7.4 V\n")
        print("| scene | policy | box travel (m) | box abs disp (m) | robot travel (m) | falls | box lost | heading mean (abs) | contact share (robot->box) |")
        print("|---|---|---|---|---|---|---|---|---|")
        for res in results:
            s = res["summary"]
            print(f"| {res['direction']} | {res['policy']} | {s['box_travel']:.2f} ± {s['box_travel_std']:.2f} | "
                  f"{s['box_disp']:.2f} | {s['robot_travel']:.2f} | {100 * s['fall_rate']:.0f}% | "
                  f"{100 * s['lost_rate']:.0f}% | {s['heading_mean']:+.0f}° ({s['heading_abs']:.0f}°) | "
                  f"{fmt_share(s['contact_share'])} |")
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(dict(args=vars(args), results=results), f, indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
