"""Settings for realistic sensing, all off by default: box.mass_range, obs.history_steps, vision.
The config and unit tests need only numpy; the env tests need the RL overlay and the walking policies."""
from __future__ import annotations

import math
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


# ── vision ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _ducks(a=(0.0, 0.0, 0.0), b=(0.3, 0.0, 0.0)):
    return {"duck_a": {"position": a[:2], "yaw": a[2]}, "duck_b": {"position": b[:2], "yaw": b[2]}}


def test_vision_is_off_by_default():
    v = load_config()["vision"]
    assert v["enabled"] is False and v["fov_deg"] == 120.0 and v["range_m"] == 0.8      # fov and range: placeholders


def test_visible_needs_the_partner_in_front_and_in_range():
    from copush.vision import visible
    assert visible(_ducks(), "duck_a", 120.0, 0.8)                                       # straight ahead, 0.3 m
    assert not visible(_ducks(b=(-0.3, 0.0, 0.0)), "duck_a", 120.0, 0.8)                # behind
    assert not visible(_ducks(b=(1.2, 0.0, 0.0)), "duck_a", 120.0, 0.8)                  # too far
    assert visible(_ducks(b=(0.3, 0.3, 0.0)), "duck_a", 120.0, 0.8)                     # 45 deg to the left: inside 60
    assert not visible(_ducks(b=(-0.05, 0.3, 0.0)), "duck_a", 120.0, 0.8)               # just past 90 deg: outside 60
    assert not visible(_ducks(b=(0.3, 0.3, 0.0)), "duck_a", 60.0, 0.8)                  # 45 deg > half of 60 = 30
    assert visible(_ducks(a=(0, 0, math.pi)), "duck_a", 120.0, 0.8) is False             # facing away from B
    assert visible(_ducks(a=(0, 0, math.pi), b=(-0.3, 0.0, 0.0)), "duck_a", 120.0, 0.8)  # now B is ahead
    assert visible(_ducks(b=(0.0, 0.0, 0.0)), "duck_a", 120.0, 0.8)                      # on top of each other


def test_vision_needs_chirps_on():
    with pytest.raises(ValueError):
        _env(vision={"enabled": True})


def test_in_view_the_exact_partner_info_is_used_out_of_view_the_last_chirp():
    from copush.decentral import local_names, local_obs
    env = _env(chirp={"enabled": True, "interval_s": 4.0, "direction_noise_deg": 30.0},
               vision={"enabled": True, "fov_deg": 120.0, "range_m": 0.8})
    env.reset(seed=4)
    st = env.state
    assert set(st["vision"]) == {"duck_a", "duck_b"}
    exact = local_obs(dict(st, chirp=None, vision=None), "duck_a", True)                  # D2 with exact info
    heard = local_obs(dict(st, vision={"duck_a": False, "duck_b": False}), "duck_a", True)
    seen = local_obs(dict(st, vision={"duck_a": True, "duck_b": True}), "duck_a", True)
    assert seen.shape == heard.shape == exact.shape == (len(local_names(True)),)
    assert np.array_equal(seen, exact)                                                    # in view: exact position and heading
    assert np.allclose(heard[-4:-2], st["chirp"]["duck_a"]) and np.allclose(heard[-2:], 0.0)   # out of view: last chirp
    assert np.array_equal(heard[:-4], exact[:-4])
    assert np.array_equal(local_obs(st, "duck_a", True), seen if st["vision"]["duck_a"] else heard)
