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
