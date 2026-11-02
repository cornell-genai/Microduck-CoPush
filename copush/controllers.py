"""Controllers. Version 0 of the coordinator: fixed commands on a schedule."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from copush.state import STOP, Command, Controller, State


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
