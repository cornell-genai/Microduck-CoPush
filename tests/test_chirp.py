"""copush.chirp: partner sensing by chirps. The sensor tests need only numpy; the env tests need the RL overlay."""
from __future__ import annotations

import math
import os

import numpy as np
import pytest

from copush.chirp import ChirpSensor
from copush.config import load_config, policy_path

DT = 0.2


def _ccfg(**kw):
    c = dict(load_config()["chirp"], enabled=True)
    c.update(kw)
    return c


def _fake_state(a=(0.0, 0.1, 0.4), b=(0.05, -0.12, -0.3)):
    """Ducks as (x, y, yaw); only what the sensor reads."""
    return {"duck_a": {"position": a[:2], "yaw": a[2]}, "duck_b": {"position": b[:2], "yaw": b[2]}}


def _true_vec(st, duck):
    me, mate = st[duck], st["duck_b" if duck == "duck_a" else "duck_a"]
    c, s = math.cos(me["yaw"]), math.sin(me["yaw"])
    wx, wy = mate["position"][0] - me["position"][0], mate["position"][1] - me["position"][1]
    return c * wx + s * wy, -s * wx + c * wy


def test_off_by_default():
    c = load_config()["chirp"]
    assert c["enabled"] is False and c["distance"] is False and c["interval_s"] == 2.0
    assert c["direction_noise_deg"] == 30.0 and c["distance_noise"] == 0.3


def test_bad_settings_are_rejected():
    for bad in ({"interval_s": 0}, {"direction_noise_deg": -1}, {"distance_noise": -0.1}, {"nominal_distance_m": 0},
                {"heading": "mostly"}, {"miss_prob": 1.1}, {"miss_prob": -0.1}, {"front_back_flip_prob": 2}):
        with pytest.raises(ValueError):
            ChirpSensor(_ccfg(**bad), DT)


def test_no_noise_every_step_is_the_exact_partner_vector():
    st = _fake_state()
    s = ChirpSensor(_ccfg(interval_s=0.2, direction_noise_deg=0, distance=True, distance_noise=0), DT)
    rng = np.random.default_rng(0)
    heard = s.reset(st, rng)
    for k in range(10):
        for d in ("duck_a", "duck_b"):
            assert np.allclose(heard[d], _true_vec(st, d), atol=1e-9)
        st["duck_a"]["position"] = (0.01 * k, 0.1)           # the partners keep moving; every step re-chirps
        st["duck_b"]["yaw"] += 0.2
        heard = s.update(st, rng)


def test_value_is_held_between_chirps():
    s = ChirpSensor(_ccfg(interval_s=1.0, direction_noise_deg=30, distance=True), DT)    # a chirp every 5 steps
    rng = np.random.default_rng(1)
    st = _fake_state()
    seq = [s.reset(st, rng)]
    for k in range(30):
        st["duck_a"]["position"] = (0.003 * k, 0.1)
        st["duck_b"]["position"] = (0.05, -0.12 - 0.002 * k)
        seq.append(s.update(st, rng))
    for d in ("duck_a", "duck_b"):
        changes = [k for k in range(1, len(seq)) if seq[k][d] != seq[k - 1][d]]
        assert 5 <= len(changes) <= 7, changes               # 30 steps = 6 s = 6 chirps (+/- the staggered phase)
        assert all(b - a == 5 for a, b in zip(changes, changes[1:])), changes   # exactly one chirp per interval


def test_chirps_per_interval_when_the_interval_is_not_a_whole_number_of_steps():
    s = ChirpSensor(_ccfg(interval_s=0.5, direction_noise_deg=30), DT)                  # 2.5 steps
    rng = np.random.default_rng(2)
    st = _fake_state()
    prev, n = s.reset(st, rng), 0
    for _ in range(100):
        now = s.update(st, rng)
        n += now["duck_a"] != prev["duck_a"]
        prev = now
    assert 38 <= n <= 41, n                                  # 20 s / 0.5 s = 40 chirps


def test_the_two_ducks_chirp_at_staggered_times():
    rng = np.random.default_rng(3)
    s = ChirpSensor(_ccfg(interval_s=2.0), DT)
    off = []
    for _ in range(300):
        s.reset(_fake_state(), rng)
        off.append((s.offset["duck_a"], s.offset["duck_b"]))
    off = np.asarray(off)
    assert (off >= 0).all() and (off < 2.0).all()
    assert np.abs(off[:, 0] - off[:, 1]).mean() > 0.4        # independent offsets (uniform pairs: mean gap 2/3)
    assert abs(off[:, 0].mean() - 1.0) < 0.15 and abs(off[:, 1].mean() - 1.0) < 0.15


def test_noise_has_the_right_spread():
    st = _fake_state()
    rng = np.random.default_rng(4)
    for sigma in (10.0, 30.0, 60.0):
        s = ChirpSensor(_ccfg(interval_s=0.2, direction_noise_deg=sigma, distance=True, distance_noise=0.3), DT)
        err, rel = [], []
        s.reset(st, rng)
        for _ in range(4000):
            h = s.update(st, rng)["duck_a"]
            x, y = _true_vec(st, "duck_a")
            err.append(math.degrees(math.atan2(math.sin(math.atan2(h[1], h[0]) - math.atan2(y, x)),
                                               math.cos(math.atan2(h[1], h[0]) - math.atan2(y, x)))))
            rel.append(math.hypot(*h) / math.hypot(x, y) - 1.0)
        assert abs(np.mean(err)) < 0.08 * sigma + 0.5
        assert abs(np.std(err) - sigma) < 0.05 * sigma + 0.5, (sigma, np.std(err))
        assert abs(np.std(rel) - 0.3) < 0.03 and abs(np.mean(rel)) < 0.03


def test_without_distance_the_vector_has_the_nominal_length():
    st = _fake_state()
    s = ChirpSensor(_ccfg(interval_s=0.2, distance=False, nominal_distance_m=0.25), DT)
    rng = np.random.default_rng(5)
    s.reset(st, rng)
    for _ in range(20):
        for d, v in s.update(st, rng).items():
            assert math.isclose(math.hypot(*v), 0.25, rel_tol=1e-9)


def test_missed_chirps_and_flips_are_off_by_default():
    c = load_config()["chirp"]
    assert c["miss_prob"] == 0.0 and c["front_back_flip_prob"] == 0.0


def _ahead_state():
    """Duck B 0.2 m straight ahead of duck A and 0.1 m to its left (A faces +x), so A hears x = 0.2 > 0."""
    return _fake_state(a=(0.0, 0.0, 0.0), b=(0.2, 0.1, 0.0))


def test_a_lost_chirp_keeps_the_last_value_but_the_first_chirp_is_always_heard():
    st = _ahead_state()
    s = ChirpSensor(_ccfg(interval_s=0.2, direction_noise_deg=0, distance=True, distance_noise=0, miss_prob=1.0), DT)
    rng = np.random.default_rng(6)
    first = s.reset(st, rng)
    assert np.allclose(first["duck_a"], _true_vec(st, "duck_a"), atol=1e-9)      # heard at t = 0 even with miss_prob 1
    st["duck_b"]["position"] = (0.5, -0.3)
    for _ in range(20):
        assert s.update(st, rng) == first                    # every scheduled chirp lost: nothing changes


def test_the_share_of_lost_chirps_matches_miss_prob():
    st = _ahead_state()
    s = ChirpSensor(_ccfg(interval_s=0.2, direction_noise_deg=30, miss_prob=0.3), DT)
    rng = np.random.default_rng(7)
    prev, heard, n = s.reset(st, rng), 0, 4000
    for _ in range(n):
        now = s.update(st, rng)
        heard += now["duck_a"] != prev["duck_a"]
        prev = now
    assert abs(heard / n - 0.7) < 0.03, heard / n


def test_front_back_flip_mirrors_x_and_keeps_y():
    st = _ahead_state()
    tx, ty = _true_vec(st, "duck_a")
    rng = np.random.default_rng(8)
    always = ChirpSensor(_ccfg(interval_s=0.2, direction_noise_deg=0, distance=True, distance_noise=0,
                               front_back_flip_prob=1.0), DT)
    x, y = always.reset(st, rng)["duck_a"]
    assert math.isclose(x, -tx, abs_tol=1e-9) and math.isclose(y, ty, abs_tol=1e-9)
    some = ChirpSensor(_ccfg(interval_s=0.2, direction_noise_deg=0, distance=True, distance_noise=0,
                             front_back_flip_prob=0.25), DT)
    some.reset(st, rng)
    flipped = sum(some.update(st, rng)["duck_a"][0] < 0 for _ in range(4000))
    assert abs(flipped / 4000 - 0.25) < 0.03, flipped / 4000


def test_zero_probabilities_draw_no_extra_random_numbers():
    """Off means off: the noise stream is the same as before these settings existed."""
    st = _ahead_state()
    a = ChirpSensor(_ccfg(interval_s=0.2, direction_noise_deg=30), DT)
    b = ChirpSensor(_ccfg(interval_s=0.2, direction_noise_deg=30, miss_prob=0.0, front_back_flip_prob=0.0), DT)
    ra, rb = np.random.default_rng(9), np.random.default_rng(9)
    a.reset(st, ra), b.reset(st, rb)
    for _ in range(50):
        assert a.update(st, ra) == b.update(st, rb)


# ── in the env (needs mujoco and the walking policies) ─────────────────────────────────────────────────────────
def _env(**chirp):
    pytest.importorskip("gymnasium")
    pytest.importorskip("mujoco")
    pytest.importorskip("stable_baselines3")
    if not all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush")):
        pytest.skip("policies missing (scripts/fetch_policies.sh)")
    from copush.env import CoPushEnv
    cfg = load_config(overrides={"env": {"layout": "steer"}, "controller": {"mode": "decentral", "include_partner": True},
                                 "chirp": chirp})
    return CoPushEnv(cfg)


def test_env_state_has_no_chirp_unless_enabled():
    env = _env(enabled=False)
    env.reset(seed=1)
    assert "chirp" not in env.state and env.chirp is None


def test_env_chirp_matches_d2_partner_info_except_heading():
    from copush.decentral import local_names, local_obs
    on = _env(enabled=True, interval_s=0.2, direction_noise_deg=0.0, distance=True, distance_noise=0.0)
    on.reset(seed=3)
    rng = np.random.default_rng(0)
    for _ in range(6):
        st = on.state
        a, b = local_obs(st, "duck_a", True), local_obs(dict(st, chirp=None), "duck_a", True)   # chirp vs exact D2
        assert a.shape == b.shape == (len(local_names(True)),)                  # same size: a D2 policy fits
        assert np.allclose(a[:-2], b[:-2], atol=1e-5)                            # own view and partner position
        assert np.allclose(a[-2:], 0.0)                                          # heading dropped
        on.step(rng.uniform(-1, 1, 4).astype(np.float32))


def test_env_heading_zero_by_default_and_true_fills_in_the_exact_heading():
    from copush.decentral import local_obs
    zero = _env(enabled=True, interval_s=0.2, direction_noise_deg=30.0)
    true = _env(enabled=True, interval_s=0.2, direction_noise_deg=30.0, heading="true")
    for env in (zero, true):
        env.reset(seed=3)
        env.step(np.zeros(4, dtype=np.float32))
    exact = local_obs(dict(true.state, chirp=None), "duck_a", True)[-2:]       # D2's exact partner heading
    assert np.allclose(local_obs(zero.state, "duck_a", True)[-2:], 0.0)
    assert np.allclose(local_obs(true.state, "duck_a", True)[-2:], exact, atol=1e-6)


def test_env_chirp_is_held_between_chirps():
    from copush.decentral import local_obs
    env = _env(enabled=True, interval_s=1.0, direction_noise_deg=30.0, distance=False)
    env.reset(seed=5)
    rng = np.random.default_rng(1)
    vals = []
    for _ in range(10):
        vals.append(local_obs(env.state, "duck_a", True)[-4:-2].copy())
        env.step(rng.uniform(-1, 1, 4).astype(np.float32))
    changes = sum(not np.array_equal(vals[i], vals[i - 1]) for i in range(1, len(vals)))
    assert 1 <= changes <= 3                                  # 10 steps = 2 s = 2 chirps; the rest held


def test_env_chirp_noise_is_reproducible_per_seed():
    def run(seed):
        env = _env(enabled=True, interval_s=0.2, direction_noise_deg=30.0)
        env.reset(seed=seed)
        out = [env.state["chirp"]["duck_a"]]
        for _ in range(4):
            env.step(np.zeros(4, dtype=np.float32))
            out.append(env.state["chirp"]["duck_a"])
        return out
    assert run(7) == run(7) and run(7) != run(8)
