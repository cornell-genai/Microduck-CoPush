"""Controllers. Version 0 of the coordinator: fixed commands on a schedule."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from copush.state import STOP, Command, Controller, State, wrap_angle


@dataclass(frozen=True)
class Phase:
    name: str
    duration: float  # seconds of simulator time
    duck_a: Command = STOP
    duck_b: Command = STOP


class SequenceController(Controller):
    """Open-loop: each phase holds fixed commands for its duration, then the next phase starts.

    Time comes from `state["t"]` (episode time, set by copush.runner). After the last phase it
    keeps sending STOP. `self.phase` names the current phase, for logging.
    """

    def __init__(self, phases: Sequence[Phase]):
        self.phases = list(phases)
        self.phase = self.phases[0].name if self.phases else ""

    def current(self, t: float) -> Phase | None:
        start = 0.0
        for phase in self.phases:
            if t < start + phase.duration:
                return phase
            start += phase.duration
        return None

    def windows(self) -> dict:
        """phase name -> (start, end) in episode seconds."""
        out, start = {}, 0.0
        for phase in self.phases:
            out[phase.name] = (start, start + phase.duration)
            start += phase.duration
        return out

    @property
    def total(self) -> float:
        return sum(p.duration for p in self.phases)

    def reset(self) -> None:
        self.phase = self.phases[0].name if self.phases else ""

    def get_actions(self, state: State):
        phase = self.current(float(state.get("t", 0.0)))  # type: ignore[arg-type]
        if phase is None:
            self.phase = "done"
            return {"duck_a": STOP, "duck_b": STOP}
        self.phase = phase.name
        return {"duck_a": phase.duck_a, "duck_b": phase.duck_b}


# ── the M1 demo ──────────────────────────────────────────────────────────────

# 0.3 m/s forward: velstand needs ~0.25 m/s to start walking from rest.
DEMO_VX = 0.3
# 1.2 rad/s *commanded* gives ~0.6 rad/s *achieved* turning in place. velstand does not turn in
# place at all below ~0.95 rad/s commanded (measured: 0.6 -> 3 deg in 6 s, 0.9 -> 7 deg,
# 1.0 -> 0.39 rad/s, 1.2 -> 0.62 rad/s, 1.5 -> 0.83 rad/s). See docs/WEEK1_STATUS.md.
DEMO_VYAW = 1.2


def m1_demo_phases(vx: float = DEMO_VX, vyaw: float = DEMO_VYAW) -> list[Phase]:
    return [
        Phase("1_a_walks", 8.0, duck_a=(vx, 0.0, 0.0), duck_b=STOP),
        Phase("2_b_turns", 8.0, duck_a=STOP, duck_b=(0.0, 0.0, vyaw)),
        Phase("3_stop", 4.0, duck_a=STOP, duck_b=STOP),
    ]


# ── B0: one duck, heading hold while pushing ─────────────────────────────────

def _clip(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class HeadingHoldPush(Controller):
    """Push a box along a straight line with ONE duck: constant vx, yaw rate from a PI heading loop.

    Built for the Shoe Push forward policy, whose yaw response while pushing is weak and biased
    (docs/results/b0_single_duck_push.md, "Steering"): achieved yaw rate ~= 0.15 * (cmd - c0),
    with c0 ~= -0.6 rad/s (a +0.08..0.1 rad/s left drift at zero command), saturating near the
    +-1.5 rad/s the policies were driven with. Hence high proportional gain, and an integral term
    that finds the drift-cancelling bias by itself (`bias0` only seeds it).

    Reference heading = the line's direction, bent toward the line by the box's cross-track error
    (box centre's signed distance from the line, left positive), so the box, not just the duck,
    comes back onto the line:

        heading_ref = line_yaw - atan(k_cross * cross_track)
        err         = wrap(heading_ref - duck_yaw)
        vyaw        = clip(bias + kp * err, -vyaw_max, vyaw_max);  bias += ki * err * dt

    The line passes through `line_origin` (default: the box's position at the first call) along
    `line_yaw` (default: the duck's heading at the first call). Only `duck_a` is commanded;
    `duck_b` gets STOP, so it drops into the two-duck interface unchanged.

    Default gains were picked on box seeds 100-109 (backlash robot) and reported on seeds 0-9
    (scripts/b0/heading_hold.py): kp 6, ki 3, k_cross 1.5.
    """

    def __init__(self, vx: float = 0.2, kp: float = 6.0, ki: float = 3.0, k_cross: float = 1.5,
                 bias0: float = -0.6, vyaw_max: float = 1.5, line_yaw: float | None = None,
                 line_origin: tuple | None = None, duck: str = "duck_a"):
        self.vx, self.kp, self.ki, self.k_cross = vx, kp, ki, k_cross
        self.bias0, self.vyaw_max, self.duck = bias0, vyaw_max, duck
        self._line_yaw0, self._line_origin0 = line_yaw, line_origin
        self.reset()

    def reset(self) -> None:
        self.bias = self.bias0
        self.line_yaw = self._line_yaw0
        self.line_origin = self._line_origin0
        self.t_prev = None
        self.last = {}

    def get_actions(self, state: State):
        me = state[self.duck]  # type: ignore[literal-required]
        box = state.get("box")
        t = float(state.get("t", 0.0))  # type: ignore[arg-type]
        if self.line_yaw is None:
            self.line_yaw = float(me["yaw"])
        if self.line_origin is None:
            self.line_origin = tuple(box["position"]) if box else tuple(me["position"])
        ref_pt = box["position"] if box else me["position"]
        dx, dy = ref_pt[0] - self.line_origin[0], ref_pt[1] - self.line_origin[1]
        cross = -dx * math.sin(self.line_yaw) + dy * math.cos(self.line_yaw)
        heading_ref = self.line_yaw - math.atan(self.k_cross * cross)
        err = wrap_angle(heading_ref - float(me["yaw"]))
        dt = 0.0 if self.t_prev is None else max(0.0, t - self.t_prev)
        self.t_prev = t
        raw = self.bias + self.kp * err
        vyaw = _clip(raw, -self.vyaw_max, self.vyaw_max)
        # anti-windup: integrate only while not pushing further into saturation
        if raw == vyaw or (raw > vyaw) != (err > 0):
            self.bias = _clip(self.bias + self.ki * err * dt, -self.vyaw_max, self.vyaw_max)
        self.last = {"cross": cross, "err": err, "bias": self.bias, "vyaw": vyaw}
        other = "duck_b" if self.duck == "duck_a" else "duck_a"
        return {self.duck: (self.vx, 0.0, vyaw), other: STOP}
