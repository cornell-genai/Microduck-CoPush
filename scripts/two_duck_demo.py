#!/usr/bin/env python3
"""Version 0 of the coordinator: fixed commands on a ~20 s schedule, every tick logged to CSV.

    phase 1 (8 s): duck A walks forward (vx 0.3 m/s), duck B stands still
    phase 2 (8 s): duck A stands still, duck B turns in place (vyaw 1.2 rad/s commanded,
                   which velstand turns at ~0.6 rad/s; 0.6 commanded does not turn at all)
    phase 3 (4 s): both stop

Needs two ducks running (`scripts/sim.sh up`, or `scripts/sim.sh up --viewer` to watch).

    uv run python scripts/two_duck_demo.py
    uv run python scripts/two_duck_demo.py --out data/runs/mine.csv --vyaw 1.0
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from copush.controllers import DEMO_VX, DEMO_VYAW, SequenceController, m1_demo_phases  # noqa: E402
from copush.metrics import displacement, load_run, phase_window, window, yaw_change  # noqa: E402
from copush.runner import RUNS_DIR, run_episode, timestamp  # noqa: E402
from copush.sim_client import SimClient, SimNotRunning  # noqa: E402


def run_demo(out: Path | None = None, vx: float = DEMO_VX, vyaw: float = DEMO_VYAW,
             verbose: bool = True) -> dict:
    controller = SequenceController(m1_demo_phases(vx, vyaw))
    out = out or RUNS_DIR / f"{timestamp()}.csv"
    with SimClient() as sim:
        if verbose:
            objects = "on" if sim.box_supported else "off"
            box = "present" if sim.read_box() else "none"
            print(f"connected: duck A + duck B, objects op {objects}, box {box}")
        summary = run_episode(
            sim, controller, controller.total, csv_path=out, verbose=verbose,
            meta={"controller": "SequenceController/m1_demo", "vx": vx, "vyaw": vyaw,
                  "phases": controller.windows()},
        )
    return summary


def print_phase_table(csv_path: Path) -> None:
    run = load_run(csv_path)
    a = run.ducks["duck_a"]
    print(f"\n{'phase':<12} {'duck':<7} {'moved cm':>9} {'turned deg':>11}")
    for phase in dict.fromkeys(a.phase):
        for key in ("duck_a", "duck_b"):
            s = run.ducks[key]
            t0, t1 = phase_window(s, phase)
            i0, i1 = window(s.t, t0, t1 + 1e-9)
            print(f"{phase:<12} {key:<7} {100 * displacement(s.x, s.y, i0, i1):9.1f} "
                  f"{math.degrees(yaw_change(s.yaw, i0, i1)):11.1f}")
    if run.box is not None:
        print(f"box: start ({run.box.x[0]:.3f}, {run.box.y[0]:.3f}, z {run.box.z[0]:.3f})  "
              f"end ({run.box.x[-1]:.3f}, {run.box.y[-1]:.3f}, z {run.box.z[-1]:.3f})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, help="CSV path (default data/runs/<timestamp>.csv)")
    parser.add_argument("--vx", type=float, default=DEMO_VX, help="duck A forward speed, m/s")
    parser.add_argument("--vyaw", type=float, default=DEMO_VYAW, help="duck B turn command, rad/s")
    args = parser.parse_args()
    try:
        summary = run_demo(args.out, args.vx, args.vyaw)
    except SimNotRunning as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"\nwrote {summary['csv']}  ({summary['ticks']} ticks, {summary['late_ticks']} late, "
          f"real-time factor {summary['realtime_factor']})")
    print_phase_table(Path(summary["csv"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
