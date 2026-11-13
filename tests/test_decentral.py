"""copush.decentral: per-duck views, the shared-policy action, the two-agent vec env. Needs the RL overlay."""
from __future__ import annotations

import copy
import math
import os

import pytest

pytest.importorskip("gymnasium")
pytest.importorskip("mujoco")
pytest.importorskip("stable_baselines3")

import numpy as np  # noqa: E402

from copush.config import load_config, policy_path  # noqa: E402

if not all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush")):
    pytest.skip("policies missing (scripts/fetch_policies.sh)", allow_module_level=True)

from copush.decentral import (DuckPairEnv, DuckVecEnv, decentral_action, local_names, local_obs,  # noqa: E402
                              pair_obs)


def _cfg():
    cfg = load_config(overrides={"env": {"layout": "steer"}})
    cfg["env"]["box_start"].update(enabled=True, dx=0.15, dy=0.15, dyaw=45.0)
    return cfg


def _state(seed=3):
    env = DuckPairEnv(_cfg())
    env.reset(seed=seed)
    for _ in range(3):
        env.step(np.zeros((2, 2), dtype=np.float32))
    return copy.deepcopy(env.env.state)


def _move_partner(st, duck="duck_b", dx=0.07, dy=-0.05, dyaw=0.6):
    st = copy.deepcopy(st)
    x, y = st[duck]["position"]
    st[duck]["position"] = (x + dx, y + dy)
    st[duck]["yaw"] += dyaw
    st[duck]["velocity"] = (0.3, -0.2)
    return st


def _rotate(st, th):
    """The whole scene rotated by th about the origin."""
    c, s = math.cos(th), math.sin(th)
    r = lambda v: (c * v[0] - s * v[1], s * v[0] + c * v[1])          # noqa: E731
    st = copy.deepcopy(st)
    for k in ("duck_a", "duck_b", "box", "goal"):
        st[k]["position"] = r(st[k]["position"])
        st[k]["yaw"] += th
        if "velocity" in st[k]:
            st[k]["velocity"] = r(st[k]["velocity"])
    return st


class LinearModel:
    """A stand-in policy: action = W @ obs, row by row (like model.predict on a batch)."""

    def __init__(self, n, seed=0):
        self.w = np.random.default_rng(seed).normal(size=(2, n)) * 0.3

    def predict(self, obs, deterministic=True):
        return np.tanh(np.asarray(obs) @ self.w.T), None


def test_local_obs_is_in_the_ducks_own_frame():
    st = _state()
    for partner in (False, True):
        for d in ("duck_a", "duck_b"):
            o = local_obs(st, d, partner)
            assert o.shape == (len(local_names(partner)),)
            assert np.allclose(o, local_obs(_rotate(st, 1.1), d, partner), atol=1e-5)


def test_d1_view_ignores_the_partner_and_d2_sees_it():
    st = _state()
    moved = _move_partner(st)
    assert np.array_equal(local_obs(st, "duck_a", False), local_obs(moved, "duck_a", False))
    assert not np.array_equal(local_obs(st, "duck_a", True), local_obs(moved, "duck_a", True))


def test_each_ducks_action_depends_only_on_its_own_observation():
    st, model = _state(), LinearModel(len(local_names(False)))
    a = decentral_action(model, st, False)
    per = [model.predict(local_obs(st, d, False))[0] for d in ("duck_a", "duck_b")]
    assert np.allclose(a, np.concatenate(per), atol=1e-6)
    b = decentral_action(model, _move_partner(st), False)       # only duck B moved
    assert np.allclose(a[:2], b[:2]) and not np.allclose(a[2:], b[2:])


def test_ppo_shared_policy_acts_per_row():
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv
    vec = DuckVecEnv(DummyVecEnv([lambda: DuckPairEnv(_cfg(), True)]))
    model = PPO("MlpPolicy", vec, n_steps=8, batch_size=8, seed=0, device="cpu")
    obs = pair_obs(_state(), True)
    both = model.predict(obs, deterministic=True)[0]
    one = [model.predict(obs[k], deterministic=True)[0] for k in range(2)]
    assert np.allclose(both, np.stack(one), atol=1e-6)
    model.learn(16)                                              # the 2-entry vec env trains


def test_duck_vec_env_layout_and_shared_reward():
    from stable_baselines3.common.vec_env import DummyVecEnv
    vec = DuckVecEnv(DummyVecEnv([lambda: DuckPairEnv(_cfg(), False) for _ in range(2)]))
    assert vec.num_envs == 4 and vec.observation_space.shape == (len(local_names(False)),)
    seen = []
    for k, pe in enumerate(vec.venv.envs):
        orig = pe.env.step
        pe.env.step = lambda a, orig=orig, k=k: (seen.append((k, np.array(a))), orig(a))[1]
    vec.seed(5)
    obs = vec.reset()
    assert obs.shape == (4, len(local_names(False)))
    acts = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8]], dtype=np.float32)
    obs, rew, done, infos = vec.step(acts)
    assert np.allclose(seen[0][1], [0.1, 0.2, 0.3, 0.4]) and np.allclose(seen[1][1], [0.5, 0.6, 0.7, 0.8])
    assert rew[0] == rew[1] and rew[2] == rew[3] and len(infos) == 4
    st = vec.venv.envs[1].env.state
    assert np.allclose(obs[3], local_obs(st, "duck_b", False), atol=1e-6)


def test_default_controller_is_central_and_d2_stays_selectable():
    from copush.decentral import partner_view
    from copush.experiments import load_stage
    assert partner_view(load_config()) is None                                   # central by default
    assert partner_view(load_config(overrides={"controller": {"mode": "decentral"}})) is True   # D2
    for path, want in (("experiments/stage1-random-box-pose/config.yaml", None),
                       ("experiments/stage1b-turn-direction-fix/a-oversample-hard/config.yaml", None),
                       ("experiments/decentralized-control/p2-d1/config.yaml", False),
                       ("experiments/decentralized-control/p2-d2/config.yaml", True)):
        assert partner_view(load_stage(path)[1]) is want, path
    with pytest.raises(ValueError):
        partner_view({"controller": {"mode": "both"}})


def test_policy_action_follows_the_controller():
    from copush.decentral import policy_action
    st, model = _state(), LinearModel(len(local_names(True)))
    env = type("E", (), {"state": st})()
    cfg = load_config(overrides={"controller": {"mode": "decentral", "include_partner": True}})
    assert np.allclose(policy_action(model, env, cfg, None), decentral_action(model, st, True))
    central = LinearModel(4)
    obs = np.ones(4, dtype=np.float32)
    cfg_c = load_config()                                                         # central by default
    assert np.allclose(policy_action(central, env, cfg_c, obs), central.predict(obs)[0])
