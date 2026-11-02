"""Metrics, recorder and M1 judging on mock data — no simulator needed."""
from __future__ import annotations

import csv
import math
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from copush import metrics as m  # noqa: E402
from copush.recorder import BASE_COLUMNS, BOX_COLUMNS, CsvRecorder  # noqa: E402

SAMPLE = ROOT / "data" / "sample" / "mock_run.csv"


@pytest.fixture
def run():
    return m.load_run(SAMPLE)


def test_load_run_shapes(run):
    assert set(run.ducks) == {"duck_a", "duck_b"}
    a, b = run.ducks["duck_a"], run.ducks["duck_b"]
    assert len(a.t) == len(b.t) == 40
    assert a.phase[0] == "1_a_walks" and a.phase[-1] == "3_stop"
    assert run.box is not None and len(run.box.t) == 40
    assert run.box.z[0] == pytest.approx(0.045)


def test_columns():
    with open(SAMPLE) as f:
        header = next(csv.reader(f))
    assert header == BASE_COLUMNS + BOX_COLUMNS


def test_displacement_and_path():
    xs, ys = [0, 3, 3], [0, 0, 4]
    assert m.displacement(xs, ys) == pytest.approx(5.0)
    assert m.path_length(xs, ys) == pytest.approx(7.0)
    assert m.max_excursion([0, 1, 0], [0, 0, 0]) == pytest.approx(1.0)
    assert m.displacement([1.0], [1.0]) == 0.0


def test_yaw_change_unwraps_across_pi():
    # +170 deg -> -170 deg is +20 deg of rotation, not -340
    yaws = [math.radians(170), math.radians(-170)]
    assert math.degrees(m.yaw_change(yaws)) == pytest.approx(20.0)
    # a full turn in small steps is 2*pi, not 0
    steps = [m.wrap_angle(k * 0.1) for k in range(64)]
    assert m.yaw_change(steps) == pytest.approx(6.3, abs=1e-9)


def test_phase_metrics_on_sample(run):
    a, b = run.ducks["duck_a"], run.ducks["duck_b"]
    t0, t1 = m.phase_window(a, "1_a_walks")
    i0, i1 = m.window(a.t, t0, t1 + 1e-9)
    assert m.displacement(a.x, a.y, i0, i1) > 0.8
    assert m.max_excursion(b.x, b.y, i0, i1) == pytest.approx(0.0)
    t0, t1 = m.phase_window(b, "2_b_turns")
    i0, i1 = m.window(b.t, t0, t1 + 1e-9)
    # 0.6 rad/s for 7.5 s of samples, crossing +pi on the way
    assert m.yaw_change(b.yaw, i0, i1) == pytest.approx(0.6 * 7.5, abs=1e-3)


def test_fall_detection():
    assert not m.fell([0.116, 0.113], [-0.999, -0.998])
    assert m.fell([0.116, 0.07], [-0.999, -0.999])          # sat down / collapsed
    assert m.fell([0.116, 0.116], [-0.999, -0.5])           # tipped 60 deg
    assert m.first_fall_time([0, 1, 2], [0.116, 0.116, 0.05], [-1, -1, -1]) == 2
    assert m.first_fall_time([0, 1], [0.116, 0.116], [-1, -1]) is None


def test_fall_thresholds_are_between_standing_and_sitting():
    # measured: standing 0.116 m / -0.999; SIT keyframe trunk 0.07 m
    assert 0.07 < m.TRUNK_Z_MIN < 0.113
    assert -0.998 < m.GRAVITY_Z_MAX < -0.5


def test_box_goal_errors():
    ep, et = m.box_goal_errors((0.3, 0.4), math.radians(170), (0.0, 0.0), math.radians(-170))
    assert ep == pytest.approx(0.5)
    assert math.degrees(et) == pytest.approx(20.0)
    assert math.degrees(m.orientation_error(math.radians(175), 0.0, symmetric=True)) == pytest.approx(5.0)
    assert m.object_progress((1.0, 0.0), (0.4, 0.0), (0.0, 0.0)) == pytest.approx(0.6)
    assert m.projected_displacement([0, 1], [0, 1], 0.0) == pytest.approx(1.0)


def test_box_displacement_on_sample(run):
    assert m.box_displacement(run.box) == pytest.approx(0.05, abs=1e-4)


def test_recorder_round_trip(tmp_path):
    path = tmp_path / "r.csv"
    with CsvRecorder(path, with_box=False) as rec:
        for k in range(3):
            st = {d: {"position": (k * 0.1, 0.0), "yaw": 0.1 * k, "trunk_z": 0.116, "gravity": (0, 0, -1)}
                  for d in ("duck_a", "duck_b")}
            rec.record(k * 0.1, st, {"duck_a": (0.3, 0, 0), "duck_b": (0, 0, 0)}, "p")
    run = m.load_run(path)
    assert run.box is None
    assert run.ducks["duck_a"].x == pytest.approx([0.0, 0.1, 0.2])
    assert run.ducks["duck_a"].cmd[0] == (0.3, 0.0, 0.0)


def _mutated_sample(tmp_path, duck, phase, dx):
    """Copy of the sample with `duck` shifted by dx in every row of `phase`'s second half."""
    out = tmp_path / "mut.csv"
    rows = list(csv.DictReader(open(SAMPLE)))
    in_phase = [r for r in rows if r["duck"] == duck and r["phase"] == phase]
    for r in in_phase[len(in_phase) // 2:]:
        r["x"] = f"{float(r['x']) + dx:.5f}"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    shutil.copy(SAMPLE.with_suffix(".json"), out.with_suffix(".json")) if SAMPLE.with_suffix(".json").exists() else None
    return out


def test_check_m1_judge_passes_on_sample():
    from check_m1 import judge

    summary = {"realtime_factor": 1.0, "ticks": 40, "late_ticks": 0, "vyaw": 1.2}
    rows = judge(SAMPLE, summary, 1.0, [("ctl health duck-a", True, "healthy")])
    failed = [r for r in rows if not r["pass"]]
    assert not failed, failed


def test_check_m1_judge_catches_coupling(tmp_path):
    from check_m1 import judge

    summary = {"realtime_factor": 1.0, "ticks": 40, "late_ticks": 0, "vyaw": 1.2}
    bad = _mutated_sample(tmp_path, "duck_b", "1_a_walks", 0.10)  # B drifts 10 cm while A walks
    rows = {r["criterion"]: r["pass"] for r in judge(bad, summary, 1.0, [])}
    assert rows["phase 1: B stays put"] is False
    assert rows["phase 1: A walks"] is True


def test_check_m1_judge_catches_slow_world():
    from check_m1 import judge

    summary = {"realtime_factor": 0.7, "ticks": 40, "late_ticks": 12, "vyaw": 1.2}
    rows = {r["criterion"]: r["pass"] for r in judge(SAMPLE, summary, 0.7, [])}
    assert rows["real time (duck-sim realtime)"] is False
    assert rows["real time (demo loop sim/wall)"] is False
