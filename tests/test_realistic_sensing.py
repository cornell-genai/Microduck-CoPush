"""Settings for realistic sensing, all off by default: box.mass_range, obs.history_steps, vision.
The config and unit tests need only numpy; the env tests need the RL overlay and the walking policies."""
from __future__ import annotations

import os

import numpy as np
import pytest

from copush.config import load_config, policy_path


def _env(central=False, **over):
    pytest.importorskip("gymnasium")
    pytest.importorskip("mujoco")
    pytest.importorskip("stable_baselines3")
    if not all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush")):
        pytest.skip("policies missing (scripts/fetch_policies.sh)")
    from copush.env import CoPushEnv
    base = {"env": {"layout": "steer"}}
    if not central:
        base["controller"] = {"mode": "decentral", "include_partner": True}
    cfg = load_config(overrides=base)
    for k, v in over.items():
        cfg[k].update(v)
    return CoPushEnv(cfg)


def math_isclose_in(x, lo, hi):
    return lo - 1e-12 <= x <= hi + 1e-12


# ── box.mass_range ─────────────────────────────────────────────────────────────────────────────────────────────
def test_mass_range_is_off_by_default():
    assert load_config()["box"]["mass_range"] is None
    env = _env()
    for seed in (1, 2, 3):
        env.reset(seed=seed)
        assert env.cfg["box"]["mass"] == env.box0["mass"] == 0.15


def test_mass_range_draws_a_different_mass_each_episode_inside_the_range():
    env = _env(box={"mass_range": [0.10, 0.25]})
    masses = []
    for seed in range(12):
        env.reset(seed=seed)
        masses.append(env.cfg["box"]["mass"])
        assert math_isclose_in(masses[-1], 0.10, 0.25)
        assert env.sim.m.body_mass[env.sim.box_body] == pytest.approx(masses[-1])      # the physics got it
    assert max(masses) - min(masses) > 0.04
    again = _env(box={"mass_range": [0.10, 0.25]})
    again.reset(seed=5)
    env.reset(seed=5)
    assert again.cfg["box"]["mass"] == env.cfg["box"]["mass"]                            # reproducible per seed


def test_bad_mass_range_is_rejected():
    for bad in ([0.2, 0.1], [0.0, 0.2], [-0.1, 0.2]):
        with pytest.raises(ValueError):
            _env(box={"mass_range": bad})
