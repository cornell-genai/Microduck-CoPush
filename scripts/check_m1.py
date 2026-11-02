#!/usr/bin/env python3
"""Checkpoint M1: two ducks in one world, independently controllable, both healthy.

Launches two ducks headless (scripts/sim.sh up), checks `ctl health` for both, runs the 20 s
two-duck demo while `duck-sim realtime` samples the real-time factor, then judges the CSV:

  upright        both ducks, every tick: trunk_z >= 0.095 m and gravity_z <= -0.90
  independence   phase 1: A walks (>= 0.5 m), B stays put (< 3 cm, < 8 deg)
                 phase 2: B turns (>= 90 deg), A stays put (< 3 cm, < 8 deg) after a 1 s settle
  real time      duck-sim realtime and the loop's own sim/wall ratio within 0.95..1.05
  health         `ctl health` says healthy for both ducks, before and after

Thresholds and their justification: docs/WEEK1_STATUS.md, and copush/metrics.py for upright.

    uv run python scripts/check_m1.py               # launch, check, shut down
    uv run python scripts/check_m1.py --runs 3      # three fresh launches
    uv run python scripts/check_m1.py --no-launch   # use ducks that are already running
Exit code 0 only if every criterion passes in every run.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from copush.metrics import (  # noqa: E402
    GRAVITY_Z_MAX, TRUNK_Z_MIN, load_run, max_abs_yaw_excursion, max_excursion, displacement,
    phase_window, upright_mask, window, yaw_change,
)
from copush.runner import RUNS_DIR, timestamp  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from two_duck_demo import run_demo  # noqa: E402

SIM = str(ROOT / "scripts" / "sim.sh")

ACTIVE_WALK_MIN_M = 0.50      # A in phase 1; typical ~1.0 m in 8 s at vx 0.3
ACTIVE_TURN_MIN_DEG = 90.0    # B in phase 2; typical ~240 deg in 8 s at vyaw 1.2
IDLE_MAX_DISP_M = 0.03        # idle duck: max excursion; typical 0.2 cm
IDLE_MAX_YAW_DEG = 8.0        # idle duck: max |rotation|; typical 1-4 deg
SETTLE_S = 1.0                # a duck that was just stopped finishes its last step first
RTF_LO, RTF_HI = 0.95, 1.05   # duck-sim's own "ok" band is >= 0.95


def sh(*args: str, env: dict | None = None, timeout: float = 600) -> subprocess.CompletedProcess:
    import os
    full_env = {**os.environ, **(env or {})}
    return subprocess.run([SIM, *args], capture_output=True, text=True, env=full_env, timeout=timeout)


def health(duck: str) -> tuple[bool, str]:
    out = sh("ctl", "health", env={"DUCK_SIM_DUCK": duck}, timeout=30)
    text = out.stdout + out.stderr
    first = text.strip().splitlines()[0] if text.strip() else "(no output)"
    loop = next((l.strip() for l in text.splitlines() if l.strip().startswith("loop")), "")
    ok = out.returncode == 0 and re.match(r"robot\s+healthy", first) is not None
    return ok, f"{first.split()[-1] if first else '?'} · {loop}"


def realtime_factor() -> float | None:
    out = sh("realtime", timeout=30)
    m = re.search(r"([0-9.]+)x real time", out.stdout + out.stderr)
    return float(m.group(1)) if m else None


def judge(csv_path: Path, summary: dict, rtf_sampled: float | None, health_rows: list) -> list:
    run = load_run(csv_path)
    a, b = run.ducks["duck_a"], run.ducks["duck_b"]
    rows = []

    def add(name, ok, value, rule):
        rows.append({"criterion": name, "pass": bool(ok), "value": value, "rule": rule})

    for name, ok, detail in health_rows:
        add(name, ok, detail, "robot healthy")

    for key, s in (("duck_a", a), ("duck_b", b)):
        mask = upright_mask(s.trunk_z, s.gravity_z)
        add(f"upright {key}", all(mask),
            f"trunk_z min {min(s.trunk_z):.3f} m, gravity_z max {max(s.gravity_z):.3f}, "
            f"{len(mask)} ticks over {s.t[-1]:.1f} s",
            f"trunk_z >= {TRUNK_Z_MIN}, gravity_z <= {GRAVITY_Z_MAX} every tick")

    p1 = phase_window(a, "1_a_walks")
    p2 = phase_window(a, "2_b_turns")
    end1, end2 = p1[1] + 1e-9, p2[1] + 1e-9

    i0, i1 = window(a.t, p1[0], end1)
    walked = displacement(a.x, a.y, i0, i1)
    add("phase 1: A walks", walked >= ACTIVE_WALK_MIN_M,
        f"{100 * walked:.1f} cm ({walked / (p1[1] - p1[0]):.3f} m/s of 0.3 asked)",
        f">= {100 * ACTIVE_WALK_MIN_M:.0f} cm")

    i0, i1 = window(b.t, p1[0], end1)
    bd, by = max_excursion(b.x, b.y, i0, i1), math.degrees(max_abs_yaw_excursion(b.yaw, i0, i1))
    add("phase 1: B stays put", bd < IDLE_MAX_DISP_M and by < IDLE_MAX_YAW_DEG,
        f"{100 * bd:.1f} cm, {by:.1f} deg", f"< {100 * IDLE_MAX_DISP_M:.0f} cm and < {IDLE_MAX_YAW_DEG:.0f} deg")

    i0, i1 = window(b.t, p2[0], end2)
    turned = math.degrees(yaw_change(b.yaw, i0, i1))
    add("phase 2: B turns", abs(turned) >= ACTIVE_TURN_MIN_DEG,
        f"{turned:+.1f} deg ({math.radians(turned) / (p2[1] - p2[0]):.2f} rad/s achieved, "
        f"{summary.get('vyaw')} commanded); moved {100 * max_excursion(b.x, b.y, i0, i1):.1f} cm",
        f">= {ACTIVE_TURN_MIN_DEG:.0f} deg")

    i0, i1 = window(a.t, p2[0] + SETTLE_S, end2)
    ad, ay = max_excursion(a.x, a.y, i0, i1), math.degrees(max_abs_yaw_excursion(a.yaw, i0, i1))
    j0, j1 = window(a.t, p2[0], end2)
    add("phase 2: A stays put", ad < IDLE_MAX_DISP_M and ay < IDLE_MAX_YAW_DEG,
        f"{100 * ad:.1f} cm, {ay:.1f} deg after {SETTLE_S:.0f} s settle "
        f"(whole phase: {100 * max_excursion(a.x, a.y, j0, j1):.1f} cm, "
        f"{math.degrees(max_abs_yaw_excursion(a.yaw, j0, j1)):.1f} deg)",
        f"< {100 * IDLE_MAX_DISP_M:.0f} cm and < {IDLE_MAX_YAW_DEG:.0f} deg")

    add("real time (duck-sim realtime)", rtf_sampled is not None and RTF_LO <= rtf_sampled <= RTF_HI,
        f"{rtf_sampled}x" if rtf_sampled is not None else "no reading", f"{RTF_LO}..{RTF_HI}")
    loop_rtf = summary.get("realtime_factor")
    add("real time (demo loop sim/wall)", loop_rtf is not None and RTF_LO <= loop_rtf <= RTF_HI,
        f"{loop_rtf}x, {summary['ticks']} ticks, {summary['late_ticks']} late", f"{RTF_LO}..{RTF_HI}")
    return rows


def one_run(index: int, launch: bool, keep_up: bool) -> tuple[bool, dict]:
    print(f"\n######## M1 check, run {index} ########", flush=True)
    if launch:
        print("launching two ducks headless (scripts/sim.sh up) ...", flush=True)
        out = sh("up")
        if out.returncode != 0:
            print(out.stdout[-2000:], out.stderr[-2000:])
            raise SystemExit("could not launch the ducks; see above")
        for line in out.stdout.splitlines():
            if "standing" in line or "did not stand" in line:
                print("  " + re.sub(r"\x1b\[[0-9;]*m", "", line).strip())

    health_rows = []
    for duck in ("duck-a", "duck-b"):
        ok, detail = health(duck)
        health_rows.append((f"ctl health {duck} (before)", ok, detail))

    # Sample duck-sim's own real-time factor while the demo runs (1 s in, 3 s window).
    rtf: dict = {}

    def sample():
        time.sleep(1.0)
        rtf["value"] = realtime_factor()

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    stamp = timestamp()
    summary = run_demo(RUNS_DIR / f"{stamp}.csv", verbose=False)
    sampler.join(timeout=10)

    for duck in ("duck-a", "duck-b"):
        ok, detail = health(duck)
        health_rows.append((f"ctl health {duck} (after)", ok, detail))

    rows = judge(Path(summary["csv"]), summary, rtf.get("value"), health_rows)
    width = max(len(r["criterion"]) for r in rows)
    for r in rows:
        print(f"  {'PASS' if r['pass'] else 'FAIL'}  {r['criterion']:<{width}}  {r['value']}   [{r['rule']}]")
    passed = all(r["pass"] for r in rows)
    print(f"  => run {index}: {'PASS' if passed else 'FAIL'}   ({summary['csv']})")

    result = {"run": index, "pass": passed, "csv": summary["csv"], "summary": summary, "criteria": rows}
    Path(summary["csv"]).with_suffix(".m1.json").write_text(json.dumps(result, indent=2) + "\n")
    if launch and not keep_up:
        sh("down")
    return passed, result


def main() -> int:
    parser = argparse.ArgumentParser(description="Checkpoint M1 (two ducks, headless)")
    parser.add_argument("--runs", type=int, default=1, help="repeat with a fresh launch each time")
    parser.add_argument("--no-launch", action="store_true", help="use ducks that are already running")
    parser.add_argument("--keep-up", action="store_true", help="leave the ducks running afterwards")
    args = parser.parse_args()

    results = []
    for index in range(1, args.runs + 1):
        passed, result = one_run(index, launch=not args.no_launch, keep_up=args.keep_up)
        results.append(result)

    print("\n######## M1 summary ########")
    for r in results:
        print(f"  run {r['run']}: {'PASS' if r['pass'] else 'FAIL'}  {r['csv']}")
    overall = all(r["pass"] for r in results)
    print(f"  M1: {'PASS' if overall else 'FAIL'} ({sum(r['pass'] for r in results)}/{len(results)} runs)")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
