"""scripts/rl/compare_policies.py: the hold and pivot metrics, and the stand-still override. Needs the RL overlay."""
from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("gymnasium")
pytest.importorskip("mujoco")
pytest.importorskip("stable_baselines3")

from copush.config import load_config, policy_path  # noqa: E402

if not all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush")):
    pytest.skip("policies missing (scripts/fetch_policies.sh)", allow_module_level=True)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "rl"))
import compare_policies as cp  # noqa: E402
import side_by_side_policies as sbp  # noqa: E402

CFG = "experiments/stage1-random-box-pose/config.yaml"
TS = "experiments/test_sets/stage1.json"
HOLD_KEYS = ("hold_a_frac", "hold_b_frac", "both_hold_steps", "one_hold_steps", "hold_a_alone", "hold_b_alone",
             "rot_one_hold_deg", "max_pivot_run")


def test_side_by_side_policy_specs_support_central_and_decentral_controllers():
    label, central = sbp.parse("central=runs/central/model.zip")
    assert label == "central" and central == {"path": "runs/central/model.zip", "standstill": False}
    _, held = sbp.parse("central held=runs/central/model.zip@standstill")
    assert held == {"path": "runs/central/model.zip", "standstill": True}
    _, d2 = sbp.parse("d2=runs/d2/model.zip@partner@standstill")
    assert d2["path"] == "runs/d2/model.zip" and d2["decentral"] == {"include_partner": True}


def _long_turn_indices(n=3):
    from copush.experiments import load_test_set
    starts = load_test_set(TS)["starts"]
    return {i for i, s in enumerate(starts) if s["dyaw"] > 15}, starts


def test_the_pivot_script_shows_up_as_one_duck_holding_while_the_other_works():
    idx, _ = _long_turn_indices()
    rows = cp._run((CFG, TS, "pivot_push", None, set(sorted(idx)[:4])))[1]
    assert len(rows) == 4 and all(k in r for r in rows for k in HOLD_KEYS)
    assert any(r["one_hold_steps"] > 0 and r["max_pivot_run"] >= 3 for r in rows)        # pivot_push pivots
    for r in rows:
        assert r["hold_a_alone"] + r["hold_b_alone"] == r["one_hold_steps"]
        assert 0.0 <= r["hold_a_frac"] <= 1.0 and 0.0 <= r["hold_b_frac"] <= 1.0


def test_a_learned_policy_without_stand_still_never_holds():
    idx, _ = _long_turn_indices()
    path = "runs/decentral-p2-d2/model.zip"
    if not os.path.exists(path):
        pytest.skip("D2 stage 1 policy missing (scripts/get_policies.sh)")
    rows = cp._run((CFG, TS, "d2", {"path": path, "decentral": {"include_partner": True}}, set(sorted(idx)[:2])))[1]
    assert all(r["one_hold_steps"] == 0 and r["both_hold_steps"] == 0 and r["hold_a_frac"] == 0.0 for r in rows)


def test_max_steps_changes_the_episode_time_limit():
    idx, _ = _long_turn_indices()
    pick = set(sorted(idx)[:2])
    short = cp._run((CFG, TS, "stand", None, pick, 7))[1]                  # 'stand' never finishes: it runs to the limit
    default = cp._run((CFG, TS, "stand", None, pick))[1]
    assert all(r["steps"] == 7 and r["reason"] == "timeout" for r in short)
    assert all(r["steps"] == 100 for r in default)
