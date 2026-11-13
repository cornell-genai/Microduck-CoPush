"""Evaluation metrics on logged runs (CSV from copush.recorder). No simulator needed.

Week 1 uses displacement, yaw change and fall detection; the box-to-goal errors are the plan's
core benchmark metrics (docs/archive/COPUSH_PLAN.md section 5) for later weeks:

    e_p     = || p_box - p_goal ||_2
    e_theta = | wrap(theta_box - theta_goal) |
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from copush.state import wrap_angle

# ── upright thresholds ───────────────────────────────────────────────────────
# Measured on this setup (velstand, 2 ducks, headless): standing trunk_z = 0.116 m and gravity_z =
# -0.999..-1.000; walking at 0.3 m/s and turning at 1.2 rad/s kept trunk_z in 0.113..0.119 and
# gravity_z <= -0.998. A seated duck is at ~0.07 m (SIT keyframe), a fallen one lower.
#
# TRUNK_Z_MIN = 0.095 m is duck-sim's own "did it stand" line (halfway between STAND 0.12 and SIT
# 0.07), ~2 cm below the lowest healthy value seen, and ~2.5 cm above sitting. Height alone is not
# enough (a duck sitting upright has gravity [0,0,-1]), and gravity alone is not enough (a seated
# trunk is vertical), so both are required.
# GRAVITY_Z_MAX = -0.90 allows <= ~26 deg of trunk tilt — far beyond the ~3.6 deg (-0.998) seen in
# healthy walking, yet well inside the 60 deg tilt (-0.5) the Shoe Push evaluation counts as a fall.
TRUNK_Z_MIN = 0.095
GRAVITY_Z_MAX = -0.90


@dataclass
class Series:
    t: List[float] = field(default_factory=list)
    x: List[float] = field(default_factory=list)
    y: List[float] = field(default_factory=list)
    yaw: List[float] = field(default_factory=list)
    trunk_z: List[float] = field(default_factory=list)
    gravity_z: List[float] = field(default_factory=list)
    cmd: List[Tuple[float, float, float]] = field(default_factory=list)
    phase: List[str] = field(default_factory=list)


@dataclass
class BoxSeries:
    t: List[float] = field(default_factory=list)
    x: List[float] = field(default_factory=list)
    y: List[float] = field(default_factory=list)
    z: List[float] = field(default_factory=list)
    yaw: List[float] = field(default_factory=list)


@dataclass
class Run:
    ducks: Dict[str, Series]
    box: Optional[BoxSeries]
    path: Optional[Path] = None


def load_run(path) -> Run:
    """Read a run CSV into per-duck series (and the box, if the CSV has box columns)."""
    ducks: Dict[str, Series] = {}
    box: Optional[BoxSeries] = None
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        has_box = "box_x" in (reader.fieldnames or [])
        if has_box:
            box = BoxSeries()
        for row in reader:
            s = ducks.setdefault(row["duck"], Series())
            t = float(row["t"])
            s.t.append(t)
            s.x.append(float(row["x"]))
            s.y.append(float(row["y"]))
            s.yaw.append(float(row["yaw"]))
            s.trunk_z.append(float(row["trunk_z"]))
            s.gravity_z.append(float(row["gravity_z"]))
            s.cmd.append((float(row["cmd_vx"]), float(row["cmd_vy"]), float(row["cmd_vyaw"])))
            s.phase.append(row.get("phase", "") or "")
            # one box sample per tick: take it from the first duck's row of that tick
            if box is not None and row["duck"] == "duck_a" and row.get("box_x"):
                box.t.append(t)
                box.x.append(float(row["box_x"]))
                box.y.append(float(row["box_y"]))
                box.z.append(float(row["box_z"]))
                box.yaw.append(float(row["box_yaw"]))
    if box is not None and not box.t:
        box = None
    return Run(ducks=ducks, box=box, path=Path(path))


# ── windows ──────────────────────────────────────────────────────────────────

def window(t: Sequence[float], start: float, end: float) -> Tuple[int, int]:
    """Indices [i0, i1) of samples with start <= t < end."""
    i0 = next((i for i, v in enumerate(t) if v >= start), len(t))
    i1 = next((i for i, v in enumerate(t) if v >= end), len(t))
    return i0, i1


def phase_window(s: Series, phase: str) -> Tuple[float, float]:
    """(first t, last t) of the samples labelled `phase`."""
    ts = [t for t, p in zip(s.t, s.phase) if p == phase]
    if not ts:
        raise KeyError(f"no samples in phase {phase!r}")
    return ts[0], ts[-1]


# ── per-duck metrics ─────────────────────────────────────────────────────────

def displacement(xs: Sequence[float], ys: Sequence[float], i0: int = 0, i1: Optional[int] = None) -> float:
    """Straight-line distance between the first and last sample of [i0, i1)."""
    i1 = len(xs) if i1 is None else i1
    if i1 - i0 < 2:
        return 0.0
    return math.hypot(xs[i1 - 1] - xs[i0], ys[i1 - 1] - ys[i0])


def max_excursion(xs: Sequence[float], ys: Sequence[float], i0: int = 0, i1: Optional[int] = None) -> float:
    """Largest distance from the window's first sample (catches move-and-return)."""
    i1 = len(xs) if i1 is None else i1
    if i1 - i0 < 2:
        return 0.0
    return max(math.hypot(xs[i] - xs[i0], ys[i] - ys[i0]) for i in range(i0, i1))


def path_length(xs: Sequence[float], ys: Sequence[float], i0: int = 0, i1: Optional[int] = None) -> float:
    i1 = len(xs) if i1 is None else i1
    return sum(math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]) for i in range(i0 + 1, i1))


def yaw_change(yaws: Sequence[float], i0: int = 0, i1: Optional[int] = None) -> float:
    """Total signed rotation over [i0, i1), unwrapped (a full turn is 2*pi, not 0)."""
    i1 = len(yaws) if i1 is None else i1
    return sum(wrap_angle(yaws[i] - yaws[i - 1]) for i in range(i0 + 1, i1))


def max_abs_yaw_excursion(yaws: Sequence[float], i0: int = 0, i1: Optional[int] = None) -> float:
    """Largest |unwrapped rotation| from the window's first sample."""
    i1 = len(yaws) if i1 is None else i1
    total, worst = 0.0, 0.0
    for i in range(i0 + 1, i1):
        total += wrap_angle(yaws[i] - yaws[i - 1])
        worst = max(worst, abs(total))
    return worst


def upright_mask(trunk_z: Sequence[float], gravity_z: Sequence[float],
                 trunk_min: float = TRUNK_Z_MIN, gravity_max: float = GRAVITY_Z_MAX) -> List[bool]:
    return [tz >= trunk_min and gz <= gravity_max for tz, gz in zip(trunk_z, gravity_z)]


def fell(trunk_z: Sequence[float], gravity_z: Sequence[float],
         trunk_min: float = TRUNK_Z_MIN, gravity_max: float = GRAVITY_Z_MAX) -> bool:
    """True if the duck was ever not upright (too low or too tilted)."""
    return not all(upright_mask(trunk_z, gravity_z, trunk_min, gravity_max))


def first_fall_time(t: Sequence[float], trunk_z: Sequence[float], gravity_z: Sequence[float],
                    trunk_min: float = TRUNK_Z_MIN, gravity_max: float = GRAVITY_Z_MAX) -> Optional[float]:
    for ti, ok in zip(t, upright_mask(trunk_z, gravity_z, trunk_min, gravity_max)):
        if not ok:
            return ti
    return None


# ── box / goal metrics (later weeks) ─────────────────────────────────────────

def position_error(box_xy: Sequence[float], goal_xy: Sequence[float]) -> float:
    """e_p = || p_box - p_goal ||_2 (planar)."""
    return math.hypot(box_xy[0] - goal_xy[0], box_xy[1] - goal_xy[1])


def orientation_error(box_yaw: float, goal_yaw: float, symmetric: bool = False) -> float:
    """e_theta = | wrap(theta_box - theta_goal) |, in radians.

    `symmetric=True` treats the box as 180-degree symmetric (a rectangle looks the same rotated by
    pi), so the error is at most pi/2. Off by default, to match the plan's definition.
    """
    err = abs(wrap_angle(box_yaw - goal_yaw))
    if symmetric:
        err = min(err, math.pi - err)
    return err


def box_goal_errors(box_xy, box_yaw: float, goal_xy, goal_yaw: float) -> Tuple[float, float]:
    return position_error(box_xy, goal_xy), orientation_error(box_yaw, goal_yaw)


def object_progress(box_xy_start, box_xy_end, goal_xy) -> float:
    """Reduction in box-to-goal distance (positive = closer)."""
    return position_error(box_xy_start, goal_xy) - position_error(box_xy_end, goal_xy)


def box_displacement(box: BoxSeries) -> float:
    return displacement(box.x, box.y)


def projected_displacement(xs, ys, direction_rad: float) -> float:
    """Displacement from first to last sample, projected on a direction (e.g. the push line)."""
    dx, dy = xs[-1] - xs[0], ys[-1] - ys[0]
    return dx * math.cos(direction_rad) + dy * math.sin(direction_rad)
