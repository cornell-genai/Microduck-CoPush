"""copush.env start noise: off by default, drawn from the episode seed, clipped, resampled when a start fails."""
from __future__ import annotations

import math
import os

import numpy as np
import pytest

from copush.config import load_config, policy_path

pytest.importorskip("gymnasium")
pytest.importorskip("mujoco")
if not all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush")):
    pytest.skip("policies missing (scripts/fetch_policies.sh)", allow_module_level=True)

from copush.env import CoPushEnv  # noqa: E402

ON = {"duck_heading_std_deg": 5.0, "duck_spacing_std_m": 0.02, "duck_setback_std_m": 0.01}


def _env(noise=None):
    cfg = load_config(overrides={"env": {"layout": "steer"}})
    cfg["env"]["box_start"].update(enabled=True, dx=0.15, dy=0.15, dyaw=45.0)
    if noise:
        cfg["start_noise"].update(noise)
    return CoPushEnv(cfg)


def _ducks(env):
    return {d: (env.cfg[d]["x"], env.cfg[d]["y"], env.cfg[d]["yaw"]) for d in ("duck_a", "duck_b")}


def test_off_by_default_and_unchanged():
    sn = load_config()["start_noise"]
    assert sn["duck_heading_std_deg"] == sn["duck_spacing_std_m"] == sn["duck_setback_std_m"] == 0.0
    a, b = _env(), _env()
    a.reset(seed=3)
    b.reset(seed=3)
    assert _ducks(a) == _ducks(b) and a.start_draws == 0
    ya, yb = a.cfg["duck_a"]["yaw"], a.cfg["duck_b"]["yaw"]
    assert ya == yb                                                         # both face the same way, as before
    assert math.isclose(math.dist(_ducks(a)["duck_a"][:2], _ducks(a)["duck_b"][:2]), a.ecfg["contact_spacing"], abs_tol=1e-9)


def test_noise_is_reproducible_per_seed_and_independent_per_duck():
    a, b = _env(ON), _env(ON)
    a.reset(seed=5)
    b.reset(seed=5)
    assert _ducks(a) == _ducks(b)
    assert a.cfg["duck_a"]["yaw"] != a.cfg["duck_b"]["yaw"]                 # each duck its own heading noise
    b.reset(seed=6)
    assert _ducks(a) != _ducks(b)


def test_draws_have_the_right_spread_and_are_clipped_at_3_std():
    env = _env(ON)
    env.reset(seed=1)
    d = [env._draw_start_noise() for _ in range(3000)]
    h = np.array([x["heading"]["duck_a"] for x in d])
    s = np.array([x["spacing"] for x in d])
    b = np.array([x["setback"]["duck_b"] for x in d])
    for arr, std in ((h, 5.0), (s, 0.02), (b, 0.01)):
        assert abs(arr.std() - std) < 0.1 * std and abs(arr.mean()) < 0.1 * std
        assert np.abs(arr).max() <= 3 * std + 1e-12
    assert np.corrcoef(h, [x["heading"]["duck_b"] for x in d])[0, 1] < 0.1   # independent per duck


def test_a_failing_start_is_redrawn_and_counted():
    env = _env(ON)
    calls = []
    real = env._start_ok
    env._start_ok = lambda st: (calls.append(1), len(calls) > 1 and real(st))[1]      # reject the first draw
    env.reset(seed=7)
    assert env.start_resamples >= 1 and env.start_draws >= 2


def test_noisy_starts_pass_the_check_most_of_the_time():
    env = _env(ON)
    for s in range(20):
        env.reset(seed=100 + s)
        st = env.state
        assert not st["duck_a"]["down"] and not st["duck_b"]["down"]
    assert env.start_resamples / env.start_draws < 0.5


# ── per-term limits (night 5) ────────────────────────────────────────────────
L2 = {"duck_heading_std_deg": 15.0, "duck_spacing_std_m": 0.04, "duck_setback_std_m": 0.02,
      "duck_heading_limit_deg": 30.0, "duck_spacing_limit_m": 0.08,
      "duck_setback_back_limit_m": 0.06, "duck_setback_forward_limit_m": 0.02}


def test_without_limits_the_draws_are_exactly_the_old_3_sigma_clip():
    env = _env(ON)
    assert all(v is None for v in env.start_noise_limits.values())
    env.reset(seed=11)
    rng = np.random.Generator(np.random.PCG64())
    rng.bit_generator.state = env.np_random.bit_generator.state           # the same RNG state, replayed by hand
    for _ in range(200):
        got = env._draw_start_noise()
        c = lambda std: float(np.clip(rng.normal(0.0, std), -3 * std, 3 * std))   # noqa: E731
        want = {"heading": {"duck_a": c(5.0), "duck_b": c(5.0)}, "spacing": c(0.02),
                "setback": {"duck_a": c(0.01), "duck_b": c(0.01)}}
        assert got == want


def test_limits_equal_to_3_sigma_give_identical_draws():
    a = _env(ON)
    b = _env({**ON, "duck_heading_limit_deg": 15.0, "duck_spacing_limit_m": 0.06,
              "duck_setback_back_limit_m": 0.03, "duck_setback_forward_limit_m": 0.03})
    a.reset(seed=4)
    b.reset(seed=4)
    assert _ducks(a) == _ducks(b)
    assert [a._draw_start_noise() for _ in range(100)] == [b._draw_start_noise() for _ in range(100)]


def test_limits_are_respected_including_the_asymmetric_setback():
    env = _env(L2)
    env.reset(seed=2)
    d = [env._draw_start_noise() for _ in range(5000)]
    h = np.array([x["heading"][k] for x in d for k in ("duck_a", "duck_b")])
    s = np.array([x["spacing"] for x in d])
    b = np.array([x["setback"][k] for x in d for k in ("duck_a", "duck_b")])
    assert np.abs(h).max() <= 30.0 and np.abs(s).max() <= 0.08
    assert b.min() >= -0.02 and b.max() <= 0.06
    assert np.isclose(b.min(), -0.02) and (b == -0.02).mean() > 0.10      # forward limit is 1 std: ~16% clipped there
    assert (b == 0.06).mean() < 0.01 and b.max() > 0.04                   # back limit is 3 std: rarely reached
    assert np.isclose(np.abs(h).max(), 30.0)                              # 2 std: some draws hit it


def test_negative_limits_are_refused():
    with pytest.raises(ValueError):
        _env({**ON, "duck_setback_forward_limit_m": -0.02})
