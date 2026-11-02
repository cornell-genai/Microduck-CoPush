"""Run a Controller against the live simulator for a fixed time, logging every tick.

The loop is the 10 Hz heartbeat robotd needs: read state -> controller -> robot.move to both
ducks -> log. robotd drops an intent ~500 ms after the last one, so a loop that stalls stops the
ducks rather than running them away — which is the behaviour we want from a failure here too.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Optional

from copush.recorder import CsvRecorder
from copush.sim_client import SimClient
from copush.state import STOP, Controller

REPO = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO / "data" / "runs"


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def run_episode(
    sim: SimClient,
    controller: Controller,
    duration: float,
    csv_path: Optional[Path] = None,
    rate_hz: float = 10.0,
    meta: Optional[dict] = None,
    verbose: bool = True,
) -> dict:
    """Run `controller` for `duration` seconds of simulator time. Returns a summary dict.

    Also writes `<csv>.json` next to the CSV with the summary (real-time factor, tick stats,
    whatever `meta` holds), so a run can be judged later without the simulator.
    """
    csv_path = Path(csv_path) if csv_path else RUNS_DIR / f"{timestamp()}.csv"
    controller.reset()
    period = 1.0 / rate_hz
    first = sim.read_state()
    t0_sim = first["time"]
    with_box = first.get("box") is not None
    ticks, late = 0, 0
    wall0 = time.perf_counter()
    next_tick = wall0
    last_phase = None
    with CsvRecorder(csv_path, with_box=with_box) as recorder:
        try:
            while True:
                state = sim.read_state()
                t = state["time"] - t0_sim
                if t >= duration:
                    break
                state["t"] = t
                actions = sim.send(controller.get_actions(state))
                phase = getattr(controller, "phase", "") or ""
                recorder.record(t, state, actions, phase)
                if verbose and phase != last_phase:
                    print(f"  t={t:5.2f}s  phase {phase}: {actions}", flush=True)
                    last_phase = phase
                ticks += 1
                next_tick += period
                slack = next_tick - time.perf_counter()
                if slack > 0:
                    time.sleep(slack)
                else:
                    late += 1
                    if slack < -0.3:  # resync rather than burst-sending to catch up
                        next_tick = time.perf_counter()
        finally:
            # Leave both ducks standing still even if the loop died mid-command.
            for _ in range(3):
                try:
                    sim.send({"duck_a": STOP, "duck_b": STOP})
                except Exception:
                    break
                time.sleep(0.05)
    wall = time.perf_counter() - wall0
    sim_elapsed = sim.sim_time() - t0_sim
    summary = {
        "csv": str(csv_path),
        "duration_s": duration,
        "ticks": ticks,
        "late_ticks": late,
        "rate_hz": rate_hz,
        "wall_s": round(wall, 3),
        "sim_s": round(sim_elapsed, 3),
        "realtime_factor": round(sim_elapsed / wall, 4) if wall > 0 else None,
        "with_box": with_box,
        **(meta or {}),
    }
    csv_path.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
