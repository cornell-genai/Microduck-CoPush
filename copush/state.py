"""The shared state format and controller interface (docs/archive/COPUSH_PLAN.md, "Shared interface").

Everything in CoPush speaks these two shapes, so the simulator client, the controllers and the
evaluation code can be developed independently:

    state = {
        "duck_a": {"position": (x, y), "yaw": rad, "velocity": (vx, vy)},
        "duck_b": {...},
        "box":    {"position": (x, y), "yaw": rad, "velocity": (vx, vy)} or None,
        "goal":   {"position": (x, y), "yaw": rad} or None,
    }

    actions = controller.get_actions(state)
    actions == {"duck_a": (vx, vy, vyaw), "duck_b": (vx, vy, vyaw)}

Conventions:
  * World frame, metres and radians. x is duck A's initial forward direction, y is to its left,
    z is up; yaw is about +z, wrapped to (-pi, pi].
  * `velocity` is the planar world-frame velocity of the trunk (or box) centre, in m/s.
  * Action commands are in each duck's *own* body frame, exactly as robotd's `robot.move` takes
    them: vx forward, vy left, vyaw counter-clockwise (m/s, m/s, rad/s).

A duck entry may carry extra keys (the sim client adds `trunk_z` and `gravity`, for health
checks); controllers must ignore keys they do not know.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional, Tuple, TypedDict

DUCKS = ("duck_a", "duck_b")

Vec2 = Tuple[float, float]
Command = Tuple[float, float, float]  # (vx, vy, vyaw), body frame


class AgentState(TypedDict, total=False):
    position: Vec2
    yaw: float
    velocity: Vec2
    # Optional extras added by copush.sim_client (not part of the agreed interface):
    trunk_z: float
    gravity: Tuple[float, float, float]
    z: float


class GoalState(TypedDict):
    position: Vec2
    yaw: float


class State(TypedDict):
    duck_a: AgentState
    duck_b: AgentState
    box: Optional[AgentState]
    goal: Optional[GoalState]


Actions = Mapping[str, Command]

STOP: Command = (0.0, 0.0, 0.0)


def wrap_angle(angle: float) -> float:
    """Wrap to (-pi, pi]."""
    wrapped = math.atan2(math.sin(angle), math.cos(angle))
    return math.pi if wrapped == -math.pi else wrapped


def make_state(duck_a: AgentState, duck_b: AgentState,
               box: Optional[AgentState] = None, goal: Optional[GoalState] = None) -> State:
    return {"duck_a": duck_a, "duck_b": duck_b, "box": box, "goal": goal}


def validate_actions(actions: Actions) -> dict:
    """Check a controller's output and return it as plain float tuples.

    Raises ValueError on a missing duck, a wrong arity or a non-finite number — a NaN that reached
    robotd would be dropped there, silently, so it is refused here instead.
    """
    out = {}
    for duck in DUCKS:
        if duck not in actions:
            raise ValueError(f"actions has no command for {duck!r}: {dict(actions)!r}")
        command = tuple(float(v) for v in actions[duck])
        if len(command) != 3:
            raise ValueError(f"{duck}: expected (vx, vy, vyaw), got {actions[duck]!r}")
        if not all(math.isfinite(v) for v in command):
            raise ValueError(f"{duck}: non-finite command {command!r}")
        out[duck] = command
    return out


class Controller:
    """Base class for every coordinator: fixed-command, scripted feedback, or learned.

    Subclasses implement `get_actions`. `reset` is called once before an episode starts.
    """

    def reset(self) -> None:  # pragma: no cover - default is stateless
        pass

    def get_actions(self, state: State) -> Actions:
        raise NotImplementedError


class StopController(Controller):
    """Both ducks stand still."""

    def get_actions(self, state: State) -> Actions:
        return {"duck_a": STOP, "duck_b": STOP}
