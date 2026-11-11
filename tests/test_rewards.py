"""copush.rewards: example reward and the suspicious-behaviour flags, on synthetic states."""
from __future__ import annotations

import math

from copush.rewards import RewardMonitor, progress_reward

DT = 0.02


def _state(t, dist=0.8, box=(0.4, 0.0), yaw=math.pi / 2, inside=False, a=None, b=None, fallen=None):
    return {"t": t, "box_to_target": dist, "inside": inside,
            "box": {"position": box, "yaw": yaw},
            "contact": {"duck_a": {"by_part": a or {}}, "duck_b": {"by_part": b or {}}},
            "fallen": fallen or {"duck_a": False, "duck_b": False}}


def _run(states, reward_fn=progress_reward):
    m = RewardMonitor(reward_fn)
    flags = []
    for s in states:
        flags += [f.split(":")[0] for f in m.update(s)[1]]
    return m, flags


def test_progress_reward_pays_for_getting_closer_and_charges_a_fall():
    s0, s1 = _state(0.0, dist=0.80), _state(DT, dist=0.79)
    assert progress_reward(None, s0) == 0.0
    assert progress_reward(s0, s1) == 10.0 * (0.80 - 0.79)
    s2 = _state(2 * DT, dist=0.79, fallen={"duck_a": True, "duck_b": False})
    assert progress_reward(s1, s2) == -1.0


def test_honest_push_raises_no_flags():
    states = [_state(k * DT, dist=0.8 - 0.002 * k, box=(0.4 + 0.002 * k, 0.0),
                     a={"hips": 0.01}, b={"hips": 0.01}) for k in range(200)]
    m, flags = _run(states)
    assert flags == []
    assert m.cum > 0


def test_one_duck_doing_the_work_is_flagged_once():
    states = [_state(k * DT, a={"hips": 0.02}, b={"hips": 0.001}) for k in range(200)]
    assert _run(states)[1] == ["contact_share"]


def test_trunk_or_head_contact_is_flagged():
    states = [_state(k * DT, a={"trunk": 0.01, "head": 0.01, "hips": 0.005}, b={"hips": 0.02}) for k in range(150)]
    assert "bad_part_duck_a" in _run(states)[1]


def test_box_spinning_in_place_is_flagged():
    states = [_state(k * DT, yaw=math.pi / 2 + 0.01 * k) for k in range(150)]      # ~0.5 rad/s, no travel
    assert "spin" in _run(states)[1]


def test_reward_rising_while_distance_does_not_fall_is_flagged():
    def contact_bonus(prev, s):            # a gameable reward: pays for touching, not for progress
        return 0.01 * len(s["contact"]["duck_a"]["by_part"])
    states = [_state(k * DT, dist=0.8, a={"hips": 0.01}, b={"hips": 0.01}) for k in range(150)]
    assert "reward_vs_dist" in _run(states, contact_bonus)[1]


def test_fall_is_flagged_once():
    states = [_state(k * DT, fallen={"duck_a": k >= 50, "duck_b": False}) for k in range(150)]
    assert _run(states)[1] == ["fall_duck_a"]


def test_oscillating_at_the_target_edge_is_flagged():
    states = [_state(k * DT, inside=(k // 10) % 2 == 0) for k in range(150)]       # in/out every 0.2 s
    assert "edge" in _run(states)[1]
