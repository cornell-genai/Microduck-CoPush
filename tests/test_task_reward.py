"""copush.rewards.TaskReward (RL reward v1 and the v2 options): pure logic, no simulator."""
from __future__ import annotations

import math

import pytest

pytest.importorskip("yaml")                      # copush.config; this repo's own venv has no PyYAML

from copush.config import DEFAULTS  # noqa: E402
from copush.metrics import orientation_error  # noqa: E402
from copush.rewards import TERMS, StepSummary, TaskReward, balance  # noqa: E402

V1 = DEFAULTS["reward"]


def cfg(**over):
    return {**V1, **over}


def S(db=0.80, da=0.80, yb=0.0, ya=0.0, **kw):
    return StepSummary(dist_before=db, dist_after=da, yaw_before=yb, yaw_after=ya, **kw)


def total(terms):
    return sum(terms.values())


# ── v1 ───────────────────────────────────────────────────────────────────────
def test_v1_progress_terms_and_time_penalty():
    t, term, why = TaskReward(V1).step(S(db=0.80, da=0.78, yb=0.30, ya=0.25))
    assert set(t) == set(TERMS)
    assert t["pos"] == pytest.approx(10 * 0.02)
    assert t["yaw"] == pytest.approx(3 * 0.05)
    assert t["time"] == pytest.approx(-0.01)
    assert t["coop"] == 0.0 and not term and why is None


def test_yaw_error_is_modulo_180_degrees():
    goal = math.radians(90)
    assert orientation_error(goal + math.pi, goal, symmetric=True) == pytest.approx(0.0)       # turned around
    assert math.degrees(orientation_error(goal + math.radians(100), goal, symmetric=True)) == pytest.approx(80)
    assert orientation_error(goal + math.radians(170), goal, symmetric=True) <= math.pi / 2


def test_success_needs_the_hold_time_then_ends_with_bonus():
    r = TaskReward(V1)
    t, term, _ = r.step(S(success_held_s=0.8))
    assert not term and t["success"] == 0.0
    t, term, why = r.step(S(success_held_s=1.0))
    assert term and why == "success" and t["success"] == 10.0


def test_v1_fall_ends_the_episode_with_minus_10():
    t, term, why = TaskReward(V1).step(S(fell=True, down_s=0.2))
    assert term and why == "fall" and t["fall"] == -10.0


@pytest.mark.parametrize("kw,why", [({"box_tilt_deg": 31.0}, "box_tipped"), ({"box_lost": True}, "box_lost")])
def test_box_tipped_or_lost_ends_with_minus_5(kw, why):
    t, term, reason = TaskReward(V1).step(S(**kw))
    assert term and reason == why and t["box_fail"] == -5.0


def test_failure_wins_over_success_in_the_same_step():
    t, term, why = TaskReward(V1).step(S(fell=True, success_held_s=1.0))
    assert why == "fall" and t["success"] == 0.0


# ── v2: continuous falls ─────────────────────────────────────────────────────
def test_continuous_fall_mode_keeps_going_and_charges_per_second_down():
    r = TaskReward(cfg(fall_mode="continuous", fall_rate=2.0))
    t, term, why = r.step(S(fell=True, down_s=0.2))
    assert not term and why is None
    assert t["fall"] == pytest.approx(-2.0 * 0.2)
    t, term, _ = r.step(S(down_s=0.0))                     # back up (or never down this step)
    assert t["fall"] == 0.0 and not term


# ── v2: gated balanced cooperation ───────────────────────────────────────────
COOP = cfg(cooperation_mode="gated_balanced", coop_lambda=5.0)


def clipped_mean(projected_substeps):
    """What CoPushSim does per duck: clip each substep's projected force at 0, then average."""
    return sum(max(0.0, p) for p in projected_substeps) / len(projected_substeps)


def test_balance_definition():
    assert balance(2.0, 2.0) == 1.0
    assert balance(2.0, 0.0) == 0.0
    assert balance(0.0, 0.0) == 0.0
    assert balance(1.0, 4.0) == 0.25


def test_coop_equal_pushing_gives_b_1():
    t, _, _ = TaskReward(COOP).step(S(db=0.80, da=0.78, push={"duck_a": 1.5, "duck_b": 1.5}))
    assert t["coop"] == pytest.approx(5.0 * 0.02 * 1.0)


def test_coop_one_duck_pushing_gives_b_0():
    t, _, _ = TaskReward(COOP).step(S(db=0.80, da=0.78, push={"duck_a": 1.5, "duck_b": 0.0}))
    assert t["coop"] == 0.0


def test_coop_both_touching_without_progress_gives_no_bonus():
    for da in (0.80, 0.82):                                # no progress, and moving away
        t, _, _ = TaskReward(COOP).step(S(db=0.80, da=da, push={"duck_a": 1.5, "duck_b": 1.5}))
        assert t["coop"] == 0.0


def test_coop_pinching_from_opposite_sides_gives_no_bonus():
    # A pushes toward the target, B pushes back from the far side: B's projection is negative,
    # clipped to 0 every substep, so b = 0 even though both press hard and the box creeps forward
    f_a = clipped_mean([+2.0, +2.1, +1.9, +2.0])
    f_b = clipped_mean([-2.0, -1.9, -2.1, -2.0])
    assert f_b == 0.0
    t, _, _ = TaskReward(COOP).step(S(db=0.80, da=0.799, push={"duck_a": f_a, "duck_b": f_b}))
    assert t["coop"] == 0.0


def test_coop_is_off_in_v1():
    t, _, _ = TaskReward(V1).step(S(db=0.80, da=0.78, push={"duck_a": 1.5, "duck_b": 1.5}))
    assert t["coop"] == 0.0
