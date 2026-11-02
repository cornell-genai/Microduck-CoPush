#!/usr/bin/env python3
"""One duck + heading hold: can Shoe Push forward push the box 1 m in a straight line?

Compares, on the same 10 paired boxes (mass 0.05-0.30 kg, yaw +-45 deg):
  open loop     vx = 0.2, vyaw = 0 (what B0 does)
  heading hold  copush.controllers.HeadingHoldPush at 5 Hz (PI on heading + box cross-track)

Gains: picked on box seeds 100-109 (backlash robot, `--seed 100`), reported on seeds 0-9 (the
default), so the reported numbers are not tuned on the boxes they are measured on.

A trial ends when the box centre has gone GOAL m along the line (the duck's initial heading,
through the box's start) or at the time limit. Success = box reached GOAL m, |box cross-track|
<= TOL m when it got there, no fall, box never lost.

    uv run --project ../microduck_rl python scripts/b0/heading_hold.py                    # backlash robot
    uv run --project ../microduck_rl python scripts/b0/heading_hold.py --robot nobacklash
    uv run --project ../microduck_rl python scripts/b0/heading_hold.py --json docs/results/data/heading_hold_backlash.json
"""
import argparse
import json
import math
import os

import numpy as np

import b0lib as L
from copush.controllers import HeadingHoldPush
from copush.state import STOP, Controller


class OpenLoop(Controller):
    def __init__(self, vx):
        self.vx = vx

    def get_actions(self, state):
        return {"duck_a": (self.vx, 0.0, 0.0), "duck_b": STOP}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--robot", choices=("backlash", "nobacklash"), default="backlash")
    ap.add_argument("--vx", type=float, default=0.2)
    ap.add_argument("--goal", type=float, default=1.0, help="box travel along the line to stop at (m)")
    ap.add_argument("--tol", type=float, default=0.10, help="max |box cross-track| at the goal (m)")
    ap.add_argument("--time-limit", type=float, default=25.0)
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--rate", type=float, default=5.0, help="controller rate (Hz)")
    ap.add_argument("--kp", type=float, default=6.0)
    ap.add_argument("--ki", type=float, default=3.0)
    ap.add_argument("--k-cross", type=float, default=1.5)
    ap.add_argument("--bias0", type=float, default=-0.6)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    L.check_policies()

    r = L.Rollout(L.scene("forward", args.robot), L.POLICY["forward"])
    boxes = L.paired_boxes(args.trials, args.seed)
    ctrls = {
        "open loop": OpenLoop(args.vx),
        "heading hold": HeadingHoldPush(vx=args.vx, kp=args.kp, ki=args.ki, k_cross=args.k_cross, bias0=args.bias0),
    }
    out = {}
    for name, ctrl in ctrls.items():
        out[name] = []
        for (m_, y_) in boxes:
            tr = []
            box0 = (L.BOX_OFFSET, 0.0)
            reached = lambda s: s["box"]["position"][0] - box0[0] >= args.goal
            o = r.run((args.vx, 0.0, 0.0), args.time_limit, +1, L.BOX_OFFSET, m_, y_, trace=tr,
                      controller=ctrl, ctrl_period=1.0 / args.rate, stop_when=reached)
            tr = np.array(tr)
            cross = tr[:, 4] - box0[1]                          # line = world x axis through the box start
            o["reached"] = o["stopped_t"] is not None
            o["t_goal"] = o["stopped_t"]
            o["cross_at_end"] = float(cross[-1])
            o["max_abs_cross"] = float(np.nanmax(np.abs(cross)))
            o["duck_heading_end"] = float(tr[-1, 5])
            o["success"] = bool(o["reached"] and abs(o["cross_at_end"]) <= args.tol and not o["fell"] and not o["lost"])
            o["trace"] = tr[::5].tolist()                       # 10 Hz, for plots
            out[name].append(o)

    print(f"\nShoe Push forward, robot={args.robot}, vx={args.vx}, goal {args.goal} m along the line, "
          f"tol {args.tol} m, limit {args.time_limit:.0f} s, {args.trials} paired boxes; heading hold at {args.rate:.0f} Hz "
          f"(kp {args.kp}, ki {args.ki}, k_cross {args.k_cross}, bias0 {args.bias0})\n")
    print("| controller | success | reached 1 m | time to 1 m (s) | box cross-track at end (m) | max abs cross-track (m) | duck heading at end (deg) | box yaw change (deg) | falls | box lost |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    summary = {}
    for name, rows in out.items():
        reached = [o for o in rows if o["reached"]]
        s = dict(success=sum(o["success"] for o in rows), reached=len(reached), n=len(rows),
                 t_goal=float(np.mean([o["t_goal"] for o in reached])) if reached else float("nan"),
                 cross_end=float(np.mean([abs(o["cross_at_end"]) for o in rows])),
                 cross_max=float(np.mean([o["max_abs_cross"] for o in rows])),
                 heading_end=float(np.mean([o["duck_heading_end"] for o in rows])),
                 box_yaw=float(np.mean([o["box_yaw_change_deg"] for o in rows])),
                 falls=sum(o["fell"] for o in rows), lost=sum(o["lost"] for o in rows),
                 box_travel=float(np.mean([o["box_travel"] for o in rows])))
        summary[name] = s
        print(f"| {name} | **{s['success']}/{s['n']}** | {s['reached']}/{s['n']} | "
              f"{s['t_goal']:.1f} | {s['cross_end']:.3f} | {s['cross_max']:.3f} | {s['heading_end']:+.0f} | "
              f"{s['box_yaw']:+.0f} | {s['falls']} | {s['lost']} |")
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        json.dump(dict(args=vars(args), summary=summary, trials=out), open(args.json, "w"))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
