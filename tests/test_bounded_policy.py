"""copush.bounded_policy: the soft mean bound, the std cap, and that a warm start keeps its deterministic actions."""
from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("gymnasium")
th = pytest.importorskip("torch")
pytest.importorskip("stable_baselines3")

from copush.bounded_policy import BoundedActorCriticPolicy, load_bounded, soft_bound  # noqa: E402


def test_soft_bound_is_identity_inside_and_bounded_outside():
    x = th.linspace(-1, 1, 201)
    assert th.equal(soft_bound(x), x)
    big = th.tensor([-100.0, -8.0, -3.0, 3.0, 8.0, 100.0])
    y = soft_bound(big)
    assert (y.abs() <= 1.5).all() and (y.abs() > 1.0).all()
    assert th.equal(th.sign(y), th.sign(big))


def test_soft_bound_is_continuous_with_slope_one_at_the_edge():
    e = 1e-4
    for s in (1.0, -1.0):
        x = th.tensor([s * (1 - e), s * (1 + e)], dtype=th.float64)
        y = soft_bound(x)
        assert abs(float(y[1] - y[0]) / float(x[1] - x[0]) - 1.0) < 1e-3


def _model(tmp_path):
    import gymnasium as gym
    from stable_baselines3 import PPO
    env = gym.make("Pendulum-v1")
    m = PPO("MlpPolicy", env, n_steps=64, batch_size=64, device="cpu", seed=0)
    with th.no_grad():
        m.policy.action_net.weight.mul_(2000.0)           # push some raw means beyond +-1
        m.policy.log_std.fill_(1.0)                       # std e = 2.7, like the night 2 policies
    p = str(tmp_path / "m.zip")
    m.save(p)
    return m, p, env


def test_load_bounded_keeps_weights_sets_std_and_ent_coef(tmp_path):
    m, p, env = _model(tmp_path)
    b = load_bounded(p, mean_bound=1.5, std_cap=0.5, init_std=0.5, ent_coef=0.0)
    assert isinstance(b.policy, BoundedActorCriticPolicy)
    assert m.ent_coef == 0.0 and b.ent_coef == 0.0       # SB3's default; the override path is checked below
    assert load_bounded(p, ent_coef=0.25).ent_coef == 0.25
    assert np.allclose(b.policy.effective_std(), 0.5)
    obs = th.as_tensor(np.stack([env.observation_space.sample() for _ in range(256)]))
    with th.no_grad():
        raw = m.policy.get_distribution(obs).distribution.mean
        mean = b.policy.get_distribution(obs).distribution.mean
    assert th.allclose(mean, soft_bound(raw))
    inside = raw.abs() <= 1
    assert inside.any() and (~inside).any()
    assert th.equal(mean[inside], raw[inside])
    assert th.equal(th.clamp(mean, -1, 1), th.clamp(raw, -1, 1))   # the clipped (env) action is unchanged


def test_std_cap_holds_even_if_log_std_drifts_up(tmp_path):
    _, p, env = _model(tmp_path)
    b = load_bounded(p, std_cap=0.5, init_std=0.5)
    with th.no_grad():
        b.policy.log_std.fill_(2.0)
    obs = th.as_tensor(np.stack([env.observation_space.sample() for _ in range(4)]))
    std = b.policy.get_distribution(obs).distribution.stddev
    assert th.allclose(std, th.full_like(std, 0.5))
    assert np.allclose(b.policy.effective_std(), 0.5)
    assert math.isclose(b.policy.std_cap, 0.5)
