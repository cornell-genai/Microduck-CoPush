#!/usr/bin/env python3
"""Steering response of the Shoe Push forward policy WHILE PUSHING.

Can a coordinator steer a pushing duck? For each commanded yaw rate (ang_vel_z) the duck pushes
the B0 box straight at vx = 0.2 m/s; we measure the achieved trunk yaw rate (least-squares slope of
heading over t in [2, 10] s, i.e. after it has reached the box) and whether it keeps the box.

    uv run --project ../microduck_rl python scripts/b0/steering.py                     # backlash robot
    uv run --project ../microduck_rl python scripts/b0/steering.py --robot nobacklash
    uv run --project ../microduck_rl python scripts/b0/steering.py --json docs/results/data/steering_backlash.json

Reported per command: achieved yaw rate mean (sd), steering gain (achieved - achieved at 0) / cmd,
box lost, falls, box travel along the initial heading, and box yaw change.
"""
import argparse
import json
import math
import os

import numpy as np

import b0lib as L


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--robot", choices=("backlash", "nobacklash"), default="backlash")
    ap.add_argument("--policy", default="forward", choices=sorted(L.POLICY))
    ap.add_argument("--vx", type=float, default=0.2)
    ap.add_argument("--wz", type=float, nargs="+", default=[round(x, 1) for x in np.arange(-0.5, 0.51, 0.1)])
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-box", action="store_true", help="box-less floor instead of the B0 forward scene")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    L.check_policies()

    direction = None if args.no_box else ("backward" if args.vx < 0 else "forward")
    sign = -1 if args.vx < 0 else +1
    r = L.Rollout(L.scene(direction, args.robot), L.POLICY[args.policy])
    boxes = L.paired_boxes(args.trials, args.seed)
    rows = {}
    for wz in args.wz:
        rows[wz] = []
        for (m_, y_) in boxes:
            tr = []
            o = r.run((args.vx, 0.0, wz), args.duration, sign, sign * L.BOX_OFFSET, m_, y_, trace=tr)
            # unwrap the heading so a > 180 deg turn is still a slope
            h = np.degrees(np.unwrap(np.radians(np.array(tr)[:, 5])))
            t = np.array(tr)[:, 0]
            sel = t >= 2.0
            o["yaw_rate"] = float(np.radians(np.polyfit(t[sel], h[sel], 1)[0])) if sel.sum() > 10 and not o["fell"] else float("nan")
            o["total_turn_deg"] = float(h[-1])
            rows[wz].append(o)

    base = np.nanmean([o["yaw_rate"] for o in rows.get(0.0, rows[min(rows, key=abs)])])
    print(f"\n{args.policy} policy, robot={args.robot}, vx={args.vx:+.2f}, {'no box' if args.no_box else 'pushing the B0 box'}, "
          f"{args.trials} trials x {args.duration:.0f} s; yaw rate fitted over t >= 2 s\n")
    print("| cmd ang_vel_z (rad/s) | achieved yaw rate (rad/s) mean ± sd | gain (achieved − drift) / cmd | total turn (deg) | box lost | falls | box travel (m) | box yaw change (deg) |")
    print("|---|---|---|---|---|---|---|---|")
    summary = []
    for wz, os_ in rows.items():
        yr = np.array([o["yaw_rate"] for o in os_])
        gain = (np.nanmean(yr) - base) / wz if wz != 0 else float("nan")
        s = dict(cmd=wz, yaw_rate_mean=float(np.nanmean(yr)), yaw_rate_sd=float(np.nanstd(yr)), gain=float(gain),
                 turn_deg=float(np.mean([o["total_turn_deg"] for o in os_])),
                 lost=float(np.mean([o["lost"] for o in os_])), falls=float(np.mean([o["fell"] for o in os_])),
                 box_travel=float(np.mean([o.get("box_travel", np.nan) for o in os_])),
                 box_yaw=float(np.mean([o.get("box_yaw_change_deg", np.nan) for o in os_])))
        summary.append(s)
        print(f"| {wz:+.1f} | {s['yaw_rate_mean']:+.3f} ± {s['yaw_rate_sd']:.3f} | "
              f"{'—' if wz == 0 else f'{gain:+.2f}'} | {s['turn_deg']:+.0f} | {100 * s['lost']:.0f}% | "
              f"{100 * s['falls']:.0f}% | {s['box_travel']:.2f} | {s['box_yaw']:+.0f} |")
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        json.dump(dict(args=vars(args), summary=summary,
                       trials={str(k): v for k, v in rows.items()}), open(args.json, "w"), indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
