"""HeadingHoldPush (B0 one-duck heading hold) — pure logic, no simulator needed."""
from __future__ import annotations

import math

import pytest

from copush.controllers import HeadingHoldPush
from copush.state import STOP, validate_actions


def _state(t, yaw, box_y=0.0, box_x=0.4, duck=(0.0, 0.0)):
    return {"t": t,
            "duck_a": {"position": duck, "yaw": yaw, "velocity": (0.0, 0.0)},
            "duck_b": {"position": (0.0, 0.5), "yaw": 0.0, "velocity": (0.0, 0.0)},
            "box": {"position": (box_x, box_y), "yaw": math.pi / 2, "velocity": (0.0, 0.0)},
            "goal": None}


def test_on_line_and_on_heading_sends_the_bias_and_stops_duck_b():
    c = HeadingHoldPush(vx=0.2, bias0=-0.6)
    a = validate_actions(c.get_actions(_state(0.0, 0.0)))
    assert a["duck_a"] == pytest.approx((0.2, 0.0, -0.6))
    assert a["duck_b"] == STOP


def test_line_is_latched_from_the_first_call():
    c = HeadingHoldPush(bias0=0.0, ki=0.0)
    c.get_actions(_state(0.0, 0.3, box_y=0.05))
    assert c.line_yaw == pytest.approx(0.3)
    assert c.line_origin == pytest.approx((0.4, 0.05))


def test_turns_back_toward_the_heading():
    c = HeadingHoldPush(bias0=0.0, ki=0.0, kp=2.0)
    c.get_actions(_state(0.0, 0.0))              # latch heading 0
    left = c.get_actions(_state(0.2, 0.2))["duck_a"][2]
    assert left == pytest.approx(-0.4)           # drifted left -> turn right


def test_box_left_of_line_steers_right():
    c = HeadingHoldPush(bias0=0.0, ki=0.0, kp=1.0, k_cross=2.0)
    c.get_actions(_state(0.0, 0.0, box_y=0.0))
    vyaw = c.get_actions(_state(0.2, 0.0, box_y=0.1))["duck_a"][2]
    assert vyaw == pytest.approx(-math.atan(0.2))


def test_integral_absorbs_a_persistent_error_and_saturation_is_respected():
    c = HeadingHoldPush(bias0=0.0, kp=0.0, ki=1.0, vyaw_max=1.5)
    c.get_actions(_state(0.0, 0.0))
    for k in range(1, 6):
        c.get_actions(_state(0.2 * k, -0.5))     # duck keeps pointing 0.5 rad right
    assert c.bias == pytest.approx(0.5 * 0.2 * 5)  # sum of ki * err * dt
    big = HeadingHoldPush(bias0=0.0, kp=100.0, ki=0.0, vyaw_max=1.5)
    big.get_actions(_state(0.0, 0.0))
    assert big.get_actions(_state(0.2, 1.0))["duck_a"][2] == -1.5


def test_anti_windup_does_not_integrate_further_into_saturation():
    c = HeadingHoldPush(bias0=0.0, kp=100.0, ki=1.0, vyaw_max=1.5)
    c.get_actions(_state(0.0, 0.0))
    for k in range(1, 20):
        c.get_actions(_state(0.2 * k, 1.0))      # saturated at -1.5 the whole time
    assert c.bias == 0.0


def test_reset_restores_the_seed_and_unlatches_the_line():
    c = HeadingHoldPush(bias0=-0.6)
    c.get_actions(_state(0.0, 0.0)); c.get_actions(_state(1.0, -0.4))
    c.reset()
    assert c.bias == -0.6 and c.line_yaw is None and c.line_origin is None
