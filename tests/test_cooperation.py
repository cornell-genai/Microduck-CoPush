"""copush.cooperation: push shares by both measures, the cooperative-success threshold, and that the env's task outcome
does not depend on any of it."""
from __future__ import annotations

import math
import os

import pytest

from copush import cooperation as C
from copush.config import load_config, policy_path


# ── share math ──────────────────────────────────────────────────────────────

def test_share_is_a_ducks_part_of_both_ducks_total():
    assert C.share_a(3.0, 1.0) == pytest.approx(0.75)
    assert C.share_a(0.0, 2.0) == 0.0
    assert C.share_a(0.0, 0.0) is None                          # nobody touched the box: no share
    s = C.shares({"duck_a": 6.0, "duck_b": 2.0})
    assert s == {"duck_a": pytest.approx(0.75), "duck_b": pytest.approx(0.25)}
    assert all(math.isnan(v) for v in C.shares({"duck_a": 0.0, "duck_b": 0.0}).values())


def test_weaker_share_is_the_smaller_ducks():
    assert C.weaker_share(0.8) == pytest.approx(0.2)
    assert C.weaker_share(0.3) == pytest.approx(0.3)
    assert C.weaker_share(None) is None and C.weaker_share(float("nan")) is None


# ── threshold logic ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("share, ok", [(0.5, True), (0.25, True), (0.75, True), (0.2499, False), (0.7501, False),
                                       (0.0, False), (1.0, False), (None, False), (float("nan"), False)])
def test_cooperative_needs_each_duck_at_the_threshold(share, ok):
    assert C.is_cooperative(True, share, 0.25) is ok
    assert C.is_cooperative(False, share, 0.25) is False        # never cooperative without task success


def test_threshold_is_a_config_setting_defaulting_to_25_percent():
    assert C.threshold_of(load_config()) == 0.25 == C.DEFAULT_THRESHOLD
    assert C.threshold_of(load_config(overrides={"metrics": {"cooperative_share": 0.4}})) == 0.4
    assert C.threshold_of({}) == 0.25
    assert C.is_cooperative(True, 0.3, 0.4) is False and C.is_cooperative(True, 0.3, 0.25) is True


EPS = [  # success, contact share A, along-the-line share A
    {"i": 0, "success": True, "contact_share_a": 0.50, "push_share_a": 0.50},     # cooperative by both
    {"i": 1, "success": True, "contact_share_a": 0.70, "push_share_a": 0.95},     # contact only (B held the box)
    {"i": 2, "success": True, "contact_share_a": 0.90, "push_share_a": 0.72},     # along the line only
    {"i": 3, "success": True, "contact_share_a": 1.00, "push_share_a": 1.00},     # solo
    {"i": 4, "success": True, "contact_share_a": 0.22, "push_share_a": 0.12},     # cooperative only at <= 20% / 10%
    {"i": 5, "success": False, "contact_share_a": 0.50, "push_share_a": 0.50},    # balanced but failed
    {"i": 6, "success": False, "contact_share_a": None, "push_share_a": None},
    {"i": 7, "success": True, "contact_share_a": None, "push_share_a": None},     # success with no contact at all
]


def test_summarize_counts_task_and_cooperative_success_for_both_measures():
    s = C.summarize(EPS, 0.25)
    assert (s["n"], s["task"]["k"]) == (8, 6)
    assert s["cooperative"]["contact"]["k"] == 2 and s["cooperative"]["push"]["k"] == 2
    assert s["cooperative"]["contact"]["rate"] == pytest.approx(2 / 8)          # of all episodes, not of successes
    assert s["cooperative"]["contact"]["ci"] == pytest.approx(list(C.wilson(2, 8)))
    assert [s["sweep"]["contact"][t]["k"] for t in ("0.10", "0.20", "0.25", "0.30", "0.40")] == [4, 3, 2, 2, 1]
    assert [s["sweep"]["push"][t]["k"] for t in ("0.10", "0.20", "0.25", "0.30", "0.40")] == [3, 2, 2, 1, 1]
    u = s["one_duck_under"]["contact"]                           # successes that are not cooperative, of the successes
    assert (u["k"], u["n"]) == (4, 6)
    d = s["disagree"]
    assert (d["k"], d["contact_only"], d["push_only"], d["ids"]) == (2, 1, 1, [1, 2])


def test_summarize_follows_the_threshold():
    assert C.summarize(EPS, 0.20)["cooperative"]["contact"]["k"] == 3
    assert C.summarize(EPS, 0.40)["cooperative"]["contact"]["k"] == 1
    assert C.summarize(EPS, 0.40)["threshold"] == 0.40
    assert C.summarize([], 0.25)["task"]["k"] == 0


def test_report_lines_lead_with_contact_impulse():
    text = "\n".join(C.report_lines({"policy": C.summarize(EPS, 0.25)}))
    assert "cooperative success (contact impulse, 25%)" in text and "along the line, 25%" in text
    assert "| policy | 8 | 75.0%" in text and "—" not in text


# ── the env: both measures are recorded, and the task outcome is untouched ───

def _env_ready():
    try:
        import gymnasium  # noqa: F401
        import mujoco  # noqa: F401
    except ImportError:
        return False
    return all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush"))


needs_env = pytest.mark.skipif(not _env_ready(), reason="needs the RL overlay and the policies (scripts/rl.sh -m pytest)")


def _episode(overrides=None, idle_b=False, steps=30):
    from copush.env import CoPushEnv, cmd_to_action
    env = CoPushEnv(load_config(overrides={"env": {"max_steps": steps, "stand_still": {"enabled": True}}, **(overrides or {})}))
    env.reset(seed=3)
    act = cmd_to_action(0.2, 0.0, 0.0 if idle_b else 0.2, 0.0)
    trace, tot = [], {"contact": {"duck_a": 0.0, "duck_b": 0.0}, "push": {"duck_a": 0.0, "duck_b": 0.0}}
    while True:
        _, r, te, tr, info = env.step(act)
        trace.append((r, info["box_to_target"], info["inside"]))
        for d in tot["contact"]:
            tot["contact"][d] += info["contact_force"][d] * env.dt
            tot["push"][d] += info["push_force"][d] * env.dt
        if te or tr:
            return info["episode_stats"], trace, tot


@needs_env
def test_env_records_both_impulses_and_their_shares():
    es, _, tot = _episode()
    for d in ("duck_a", "duck_b"):
        assert es["contact_impulse"][d] == pytest.approx(tot["contact"][d], abs=1e-9)
        assert es["push_impulse"][d] == pytest.approx(tot["push"][d], abs=1e-9)
        assert es["contact_impulse"][d] >= es["push_impulse"][d] - 1e-9   # the part toward the target is at most the whole
        assert es["contact_impulse"][d] > 0
    assert es["contact_share"] == pytest.approx(C.shares(tot["contact"]))
    assert es["push_share"] == pytest.approx(C.shares(tot["push"]))        # the existing measure is unchanged
    assert sum(es["contact_share"].values()) == pytest.approx(1.0)
    assert es["cooperative_threshold"] == 0.25
    assert es["cooperative"] == C.is_cooperative(es["reason"] == "success", es["contact_share"]["duck_a"], 0.25)


@needs_env
def test_an_idle_duck_gets_a_small_share():
    es, _, _ = _episode(idle_b=True)
    assert es["contact_share"]["duck_b"] < 0.25 < es["contact_share"]["duck_a"]
    assert es["cooperative"] is False


@needs_env
def test_task_outcome_does_not_depend_on_the_cooperative_threshold():
    a, ta, _ = _episode()
    b, tb, _ = _episode({"metrics": {"cooperative_share": 0.45}})
    assert ta == tb                                               # every step's reward, distance and inside flag
    for k in ("reason", "steps", "return", "terms", "fell", "push_share", "final_dist", "min_dist", "final_yaw_deg",
              "contact_impulse", "push_impulse"):
        assert a[k] == b[k], k
    assert (a["cooperative_threshold"], b["cooperative_threshold"]) == (0.25, 0.45)
