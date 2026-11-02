#!/usr/bin/env python3
"""Regenerate data/sample/mock_run.csv: a small, synthetic, deterministic run (no simulator).

Same shape as a real two_duck_demo run with a box, sampled at 2 Hz instead of 10 Hz to stay small:
  phase 1_a_walks (0-8 s):  A walks +x at 0.12 m/s with a slow right drift; B still
  phase 2_b_turns (8-16 s): A still (one last 2 cm step); B turns +0.6 rad/s, crossing +pi
  phase 3_stop   (16-20 s): both still
  box: starts at (0.6, 0), A's walk nudges it 5 cm in +x during the last 2 s of phase 1.

    uv run python tests/make_sample_csv.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from copush.recorder import CsvRecorder  # noqa: E402
from copush.state import wrap_angle  # noqa: E402

OUT = ROOT / "data" / "sample" / "mock_run.csv"
DT = 0.5


def main() -> None:
    with CsvRecorder(OUT, with_box=True) as rec:
        b_yaw0 = 2.0  # so B's turn wraps past +pi
        for i in range(int(20 / DT)):
            t = i * DT
            if t < 8:
                phase, ax, ayaw = "1_a_walks", 0.12 * t, -0.03 * t
                b_yaw = b_yaw0
                cmd_a, cmd_b = (0.3, 0.0, 0.0), (0.0, 0.0, 0.0)
            elif t < 16:
                phase, ax, ayaw = "2_b_turns", 0.96 + (0.02 if t >= 8.5 else 0.0), -0.24
                b_yaw = b_yaw0 + 0.6 * (t - 8)
                cmd_a, cmd_b = (0.0, 0.0, 0.0), (0.0, 0.0, 1.2)
            else:
                phase, ax, ayaw = "3_stop", 0.98, -0.24
                b_yaw = b_yaw0 + 0.6 * 8
                cmd_a, cmd_b = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
            box_x = 0.6 + (min(max(t - 6.0, 0.0), 2.0) * 0.025)
            state = {
                "duck_a": {"position": (ax, -0.1 * ax * ax), "yaw": ayaw, "trunk_z": 0.116 - 0.002 * (phase == "1_a_walks"),
                           "gravity": (0.0, 0.0, -0.999)},
                "duck_b": {"position": (0.04, 0.505), "yaw": wrap_angle(b_yaw), "trunk_z": 0.116,
                           "gravity": (0.0, 0.0, -1.0)},
                "box": {"position": (box_x, 0.0), "yaw": math.pi / 2, "z": 0.045},
            }
            rec.record(t, state, {"duck_a": cmd_a, "duck_b": cmd_b}, phase)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
