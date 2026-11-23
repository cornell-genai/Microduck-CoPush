#!/usr/bin/env python3
"""Diagnostic (night 2 heading investigation, experiments/d2-rendezvous/night2/heading-investigation.md): can
velstand (the frozen walking policy) walk and turn in place at the same time, or does commanding both interfere
with one or the other? Duck A only (duck B stands at zero command); three 2-second runs, same duck, same config:

    walk_only  vx=0.25, vyaw=0.0
    turn_only  vx=0.00, vyaw=0.5
    combined   vx=0.25, vyaw=0.5

Logs yaw and position every control step (0.02 s, 50 Hz -- the ONNX policy's own rate) to a CSV per run and prints
a summary: net heading change, net distance travelled, mean forward speed, each compared across runs.

    scripts/rl.sh scripts/rl/diag_velstand_turn.py [--out DIR] [--duration 2.0]
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from copush.config import load_config  # noqa: E402
from copush.sim import CONTROL_DT, CoPushSim  # noqa: E402
from copush.state import wrap_angle  # noqa: E402

RUNS = {"walk_only": (0.25, 0.0), "turn_only": (0.0, 0.5), "combined": (0.25, 0.5)}


def run_one(cfg: dict, vx: float, vyaw: float, duration: float) -> list:
    sim = CoPushSim(cfg)
    sim.reset()
    sim.set_policy("A", "velstand")
    sim.set_policy("B", "velstand")
    n = max(1, round(duration / CONTROL_DT))
    rows = []
    st = sim.get_state()
    x0, y0, yaw0 = *st["duck_a"]["position"], st["duck_a"]["yaw"]
    rows.append({"t": 0.0, "x": x0, "y": y0, "yaw_deg": math.degrees(yaw0), "dyaw_deg": 0.0,
                "dist_m": 0.0, "fwd_speed": 0.0, "down": st["duck_a"]["down"]})
    for i in range(n):
        st = sim.step({"A": (vx, 0.0, vyaw), "B": (0.0, 0.0, 0.0)})
        x, y, yaw = *st["duck_a"]["position"], st["duck_a"]["yaw"]
        vxw, vyw = st["duck_a"]["velocity"]
        fwd = vxw * math.cos(yaw) + vyw * math.sin(yaw)
        rows.append({"t": round((i + 1) * CONTROL_DT, 4), "x": x, "y": y, "yaw_deg": math.degrees(yaw),
                    "dyaw_deg": math.degrees(wrap_angle(yaw - yaw0)), "dist_m": math.dist((x, y), (x0, y0)),
                    "fwd_speed": fwd, "down": st["duck_a"]["down"]})
    return rows


def summarize(name: str, rows: list) -> dict:
    last = rows[-1]
    mean_fwd = sum(r["fwd_speed"] for r in rows[1:]) / max(1, len(rows) - 1)
    return {"run": name, "net_heading_change_deg": last["dyaw_deg"], "net_distance_m": round(last["dist_m"], 4),
            "mean_forward_speed": round(mean_fwd, 4), "fell": any(r["down"] for r in rows)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="runs/diag_velstand_turn")
    ap.add_argument("--duration", type=float, default=2.0)
    a = ap.parse_args()
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)
    cfg = load_config()
    summaries = []
    for name, (vx, vyaw) in RUNS.items():
        rows = run_one(cfg, vx, vyaw, a.duration)
        path = os.path.join(out, f"{name}.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        s = summarize(name, rows)
        summaries.append(s)
        print(f"{name:>10} (vx={vx}, vyaw={vyaw}): net heading {s['net_heading_change_deg']:+.1f} deg, "
              f"net distance {s['net_distance_m']:.3f} m, mean forward speed {s['mean_forward_speed']:.3f} m/s, "
              f"fell={s['fell']} -> {os.path.relpath(path, ROOT)}")

    w, t, c = (s for s in summaries)  # walk_only, turn_only, combined, in RUNS' insertion order
    print()
    print("comparison:")
    print(f"  heading change: combined {c['net_heading_change_deg']:+.1f} deg vs turn_only {t['net_heading_change_deg']:+.1f} deg "
          f"({100 * c['net_heading_change_deg'] / t['net_heading_change_deg']:.0f}% of turn_only)" if t["net_heading_change_deg"]
          else "  heading change: turn_only produced no net heading change (unexpected)")
    print(f"  forward speed:  combined {c['mean_forward_speed']:.3f} m/s vs walk_only {w['mean_forward_speed']:.3f} m/s "
          f"({100 * c['mean_forward_speed'] / w['mean_forward_speed']:.0f}% of walk_only)" if w["mean_forward_speed"]
          else "  forward speed: walk_only produced no forward speed (unexpected)")
    print(f"  net distance:   combined {c['net_distance_m']:.3f} m vs walk_only {w['net_distance_m']:.3f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
