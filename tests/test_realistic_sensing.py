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


# ── obs.history_steps ──────────────────────────────────────────────────────────────────────────────────────────
def test_history_is_off_by_default_and_changes_nothing():
    from copush.decentral import DuckPairEnv, local_names
    from copush.env import OBS_NAMES
    assert load_config()["obs"]["history_steps"] == 1
    env = _env(central=True)
    obs, _ = env.reset(seed=1)
    assert obs.shape == (len(OBS_NAMES),) and env.observation_space.shape == (len(OBS_NAMES),) and "history" not in env.state
    pair = DuckPairEnv(load_config(overrides={"env": {"layout": "steer"}}), True)
    assert pair.observation_space.shape == (2, len(local_names(True)))


def test_central_observation_is_stacked_newest_first():
    from copush.env import OBS_NAMES
    n = len(OBS_NAMES)
    env = _env(central=True, obs={"history_steps": 3})
    assert env.observation_space.shape == (3 * n,)
    obs0, _ = env.reset(seed=2)
    assert obs0.shape == (3 * n,)
    assert np.array_equal(obs0[:n], obs0[n:2 * n]) and np.array_equal(obs0[:n], obs0[2 * n:])     # padded with the first
    rng = np.random.default_rng(0)
    seen = [obs0[:n]]
    for _ in range(4):
        obs, *_ = env.step(rng.uniform(-1, 1, 4).astype(np.float32))
        seen.append(obs[:n])
        assert np.array_equal(obs[n:2 * n], seen[-2])                                           # the step before
        if len(seen) >= 3:
            assert np.array_equal(obs[2 * n:], seen[-3])                                        # two steps before


def test_decentral_views_are_stacked_newest_first():
    from copush.decentral import DuckPairEnv, local_names, local_obs
    n = len(local_names(True))
    cfg = load_config(overrides={"env": {"layout": "steer"}, "controller": {"mode": "decentral", "include_partner": True}})
    cfg["obs"]["history_steps"] = 3
    pair = DuckPairEnv(cfg, True)
    assert pair.observation_space.shape == (2, 3 * n)
    obs, _ = pair.reset(seed=3)
    assert obs.shape == (2, 3 * n) and np.array_equal(obs[0, :n], obs[0, 2 * n:])
    rng = np.random.default_rng(1)
    singles = [obs[:, :n]]
    for _ in range(4):
        obs, *_ = pair.step(rng.uniform(-1, 1, (2, 2)).astype(np.float32))
        singles.append(obs[:, :n])
        assert np.array_equal(obs[:, n:2 * n], singles[-2])
        if len(singles) >= 3:
            assert np.array_equal(obs[:, 2 * n:], singles[-3])
    st = pair.env.state                                                                          # eval path: env.state
    assert np.array_equal(local_obs(st, "duck_b", True), obs[1])
    assert "history" not in st["history"][0]                                                    # no chain of histories


def test_history_must_be_at_least_one():
    with pytest.raises(ValueError):
        _env(obs={"history_steps": 0})
