"""copush.env.CoPushEnv, copush.video episode videos. Needs the RL overlay: scripts/rl.sh -m pytest"""
from __future__ import annotations

import copy
import csv
import math
import os

import pytest

pytest.importorskip("gymnasium")
pytest.importorskip("mujoco")
pytest.importorskip("bam")

import mujoco  # noqa: E402
import numpy as np  # noqa: E402

from copush.config import load_config, policy_path  # noqa: E402

if not all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush")):
    pytest.skip("policies missing (scripts/fetch_policies.sh)", allow_module_level=True)

from copush.env import LOG_COLUMNS, OBS_NAMES, CoPushEnv, action_to_cmd, baseline, cmd_to_action  # noqa: E402
from copush.rewards import TERMS  # noqa: E402


def cfg_with(**sections):
    c = load_config()
    for sec, over in sections.items():
        c[sec].update(over)
    return c


@pytest.fixture(scope="module")
def env():
    return CoPushEnv()


def run(env, act, seed=0, max_steps=None):
    obs, _ = env.reset(seed=seed)
    infos, ret, k = [], 0.0, 0
    while True:
        obs, r, te, tr, info = env.step(act(obs))
        infos.append(info)
        ret += r
        k += 1
        if te or tr or (max_steps and k >= max_steps):
            return ret, infos


def test_spaces_and_check_env(env):
    from gymnasium.utils.env_checker import check_env
    assert env.action_space.shape == (4,) and env.observation_space.shape == (len(OBS_NAMES),) == (21,)
    check_env(env, skip_render_check=True)


def test_action_scaling():
    assert action_to_cmd([-1, -1, 1, 1]) == {"A": (0.0, 0.0, -1.5), "B": (0.3, 0.0, 1.5)}
    np.testing.assert_allclose(cmd_to_action(0.2, 0.0, 0.0, 1.5), [1 / 3, 0, -1, 1], atol=1e-6)


def test_resets_are_exact(env):
    a = cmd_to_action(0.2, 0, 0.2, 0)
    r1, _ = run(env, lambda o: a, max_steps=30)
    r2, _ = run(env, lambda o: a, max_steps=30)
    fresh = CoPushEnv()
    r3, _ = run(fresh, lambda o: a, max_steps=30)
    assert r1 == r2 == r3


def test_heldout_seeds_refused_in_train_split(env):
    with pytest.raises(ValueError):
        env.reset(seed=10000)
    CoPushEnv(split="eval").reset(seed=10000)


def test_fixed_start_by_default_and_randomized_option(env):
    _, info = env.reset(seed=3)
    assert (info["box"]["x"], info["box"]["y"], info["box"]["yaw"]) == (0.35, 0.0, 90)
    renv = CoPushEnv(cfg_with(env={"randomize": True}))
    boxes = [renv.reset(seed=s)[1]["box"] for s in (1, 2, 1)]
    assert boxes[0] == boxes[2] and boxes[0] != boxes[1]
    r = renv.ecfg["random"]
    for b in boxes:
        assert r["box_x"][0] <= b["x"] <= r["box_x"][1] and r["box_mass"][0] <= b["mass"] <= r["box_mass"][1]
    bid = renv.sim.box_body
    assert renv.sim.m.body_mass[bid] == pytest.approx(boxes[2]["mass"])


def test_policy_switches_on_contact_and_not_without():
    env = CoPushEnv(cfg_with(env={"layout": "hard"}))                    # approach start
    assert env.state is None and env.start_mode == "approach" and env.cfg["target"]["x"] == 1.20
    _, infos = run(env, baseline("push_forward", env), max_steps=25)       # 5 s: contact at ~3.4 s
    assert env.state["duck_a"]["policy"] == "shoepush" and env.state["duck_b"]["policy"] == "shoepush"
    run(env, baseline("stand", env), max_steps=10)
    assert env.state["duck_a"]["policy"] == "velstand"


def test_in_contact_start_is_the_default(env):
    obs, info = env.reset(seed=0)
    st = env.state
    assert env.start_mode == "in_contact" and info["target"]["x"] == pytest.approx(0.75) and st["t"] == 0.0
    for d, y in (("duck_a", 0.10), ("duck_b", -0.10)):
        assert st[d]["policy"] == "shoepush" and not st[d]["fallen"]
        assert st[d]["position"][0] == pytest.approx(0.35 - 0.095, abs=0.01)    # behind the box's face
        assert st[d]["position"][1] == pytest.approx(y, abs=0.01)
        assert abs(math.degrees(st[d]["yaw"])) < 3
    assert st["box"]["position"] == pytest.approx((0.35, 0.0), abs=0.002)        # settling did not shove it
    _, _, _, _, i = env.step(baseline("push_forward", env)(obs))
    assert i["contact_time"]["duck_a"] > 0 and i["contact_time"]["duck_b"] > 0


def test_push_steer_reaches_the_close_target(env):
    ret, infos = run(env, baseline("push_steer", env))
    assert infos[-1]["reason"] == "success" and ret > 5


def test_reward_version_is_selected_from_the_config():
    from copush.config import with_reward_version
    v1 = CoPushEnv(with_reward_version(load_config(), "v1"))
    v12 = CoPushEnv(with_reward_version(load_config(), "v1.2"))
    assert (v1.rcfg["w_yaw"], v1.rcfg["time_penalty"], v1.rcfg["fall_min_down_s"]) == (3.0, 0.01, 0.0)
    assert (v12.rcfg["w_yaw"], v12.rcfg["time_penalty"], v12.rcfg["contact_penalty"]) == (1.0, 0.03, 0.02)
    assert CoPushEnv().rcfg["version"] == "v1.1"


@pytest.mark.parametrize("version,counts", [("v1", True), ("v1.1", False)])
def test_a_brief_stumble_is_not_a_fall_from_v11(version, counts):
    from copush.config import with_reward_version
    e = CoPushEnv(with_reward_version(load_config(), version))
    e.reset(seed=0)
    calls = {"n": 0}
    real = e.sim._is_fallen

    def flicker(duck):                         # duck A "down" for the first 0.1 s only
        if duck == "duck_a":
            calls["n"] += 1
            return calls["n"] <= 5
        return real(duck)
    e.sim._is_fallen = flicker
    _, _, term, _, info = e.step(baseline("stand", e)(None))
    assert (info["reason"] == "fall") is counts and term is counts


def test_curriculum_levels_move_the_target():
    e = CoPushEnv(cfg_with(env={"curriculum": {**load_config()["env"]["curriculum"], "enabled": True}}))
    assert e.cfg["target"]["x"] == pytest.approx(0.35 + 0.40)
    assert e.set_curriculum_level(2) == 2 and e.cfg["target"]["x"] == pytest.approx(0.35 + 0.85)
    assert e.cfg["target"]["y"] == pytest.approx(0.20)
    assert e.set_curriculum_level(9) == 2


def _tip_over(env, duck="duck_a"):
    qa, _ = env.sim._free[duck]
    env.sim.d.qpos[qa + 2] = 0.05
    env.sim.d.qpos[qa + 3:qa + 7] = [math.cos(math.pi / 4), math.sin(math.pi / 4), 0, 0]   # on its side
    mujoco.mj_forward(env.sim.m, env.sim.d)


def test_fall_v1_terminates_v2_continuous_keeps_going():
    e = CoPushEnv()
    e.reset(seed=0)
    _tip_over(e)
    _, r, term, _, info = e.step(baseline("stand", e)(None))        # down the whole 0.2 s step
    assert term and info["reason"] == "fall" and info["terms"]["fall"] == -10.0

    c = CoPushEnv(cfg_with(reward={"fall_mode": "continuous", "fall_rate": 1.0}))
    c.reset(seed=0)
    _tip_over(c)
    _, r, term, trunc, info = c.step(baseline("stand", c)(None))
    assert not term and not trunc
    assert info["terms"]["fall"] < 0 and info["terms"]["fall"] >= -0.2 - 1e-9


def test_coop_bonus_in_physics_balanced_push_vs_pinch():
    coop = {"cooperation_mode": "gated_balanced", "coop_lambda": 5.0}
    both = CoPushEnv(cfg_with(reward=coop, env={"layout": "hard"}))
    _, infos = run(both, baseline("push_forward", both), max_steps=40)
    assert max(i["b"] for i in infos) > 0.3 and sum(i["terms"]["coop"] for i in infos) > 0

    pinch_cfg = cfg_with(reward=coop, env={"layout": "hard"})
    pinch_cfg["duck_a"].update({"x": 0.0, "y": 0.0})
    pinch_cfg["duck_b"].update({"x": 0.70, "y": 0.0, "yaw": 180})          # facing A across the box
    pinch = CoPushEnv(pinch_cfg)
    _, infos = run(pinch, baseline("push_forward", pinch), max_steps=30)
    touched_b = [i for i in infos if i["contact_force"]["duck_b"] > 0.1]
    assert touched_b, "B should press on the box"
    assert all(i["push_force"]["duck_b"] < 0.05 for i in touched_b)
    assert sum(i["terms"]["coop"] for i in infos) < 0.01


def test_step_log_has_every_term(tmp_path):
    e = CoPushEnv(log_dir=str(tmp_path))
    run(e, baseline("push_forward", e), max_steps=5)
    e.close()
    rows = list(csv.DictReader(open(tmp_path / "env_steps.csv")))
    assert len(rows) == 5 and set(rows[0]) == set(LOG_COLUMNS)
    assert all(f"r_{k}" in rows[0] for k in TERMS)
    assert (tmp_path / "events.log").read_text().startswith("ep=1")


def test_episode_video_and_index(tmp_path):
    from copush.video import VideoLog
    c = cfg_with(env={"max_steps": 5})
    e = CoPushEnv(c)
    vlog = VideoLog(str(tmp_path), c["video"])
    stats = vlog.record(e, baseline("zero", e), training_step=0, reason="baseline", seed=0, label="zero")
    mp4 = tmp_path / "videos" / "step_0_baseline_zero.mp4"
    assert mp4.exists() and 0 < mp4.stat().st_size < 3_000_000
    index = (tmp_path / "videos" / "index.md").read_text()
    assert "step_0_baseline_zero.mp4" in index and "timeout (5 steps)" in index and stats["steps"] == 5


def test_push_steer_squares_up_and_holds_on_velstand():
    c = load_config()
    c["layouts"]["close"]["target"].update({"y": 0.15})            # last round's failing case
    e = CoPushEnv(c, split="eval")
    act = baseline("push_steer", e)
    ret, infos = run(e, act, seed=10000)
    assert infos[-1]["reason"] == "success" and act.mode == "hold"
    assert e.state["duck_a"]["policy"] == "velstand" and e.state["duck_b"]["policy"] == "velstand"


def test_hold_keeps_velstand_on_contact_and_switches_are_logged(env):
    obs, _ = env.reset(seed=0)
    env.step(baseline("push_forward", env)(obs))                   # touching the box on Shoe Push
    env.set_hold("duck_a", True)
    env.step(baseline("stand", env)(obs))
    assert env.state["duck_a"]["policy"] == "velstand" and env.state["contact"]["duck_a"]["impulse"] >= 0
    env.set_hold("duck_a", False)
    for _ in range(6):
        env.step(baseline("push_forward", env)(obs))
    assert env.state["duck_a"]["policy"] == "shoepush"             # back on contact
    env.reset(seed=0)                                              # closes open windows
    kinds = [(w["from"], w["to"]) for w in env.switch_log if w["duck"] == "duck_a"]
    assert ("shoepush", "velstand") in kinds and ("velstand", "shoepush") in kinds
    assert all({"min_z", "max_tilt", "fell", "box_moved", "stumble"} <= set(w) for w in env.switch_log)


def test_steer_layout_puts_the_target_beyond_a_straight_push():
    e = CoPushEnv(cfg_with(env={"layout": "steer"}))
    _, info = e.reset(seed=0)
    t = info["target"]
    assert e.start_mode == "in_contact" and abs(t["y"] - e.cfg["box"]["y"]) > t["size"][0] / 2


def test_stand_still_action_is_off_by_default_and_holds_on_velstand_when_on():
    stand, go = baseline("stand", None), baseline("push_forward", None)
    off = CoPushEnv()
    off.reset(seed=0)
    off.step(stand(None))
    assert off.stand_still["enabled"] is False
    assert off.state["duck_a"]["policy"] == "shoepush" and not any(off.hold.values())
    on = CoPushEnv(cfg_with(env={"stand_still": {"enabled": True, "vx_threshold": 0.02}}))
    on.reset(seed=0)
    on.step(stand(None))
    assert all(on.hold.values())
    assert on.state["duck_a"]["policy"] == "velstand" and on.state["duck_b"]["policy"] == "velstand"
    on.step(cmd_to_action(0.2, 0.0, 0.0, 0.0))                 # only duck A walks again
    assert on.hold == {"duck_a": False, "duck_b": True}
    for _ in range(5):
        on.step(go(None))
    assert not any(on.hold.values()) and on.state["duck_a"]["policy"] == "shoepush"


def test_pivot_push_pivots_with_one_duck_held_then_succeeds():
    from copush.env import PivotThenPush
    c = load_config()
    c["layouts"]["close"]["target"] = {"x": 0.75, "y": -0.15, "yaw": 90}       # 0.15 m to the right
    e = CoPushEnv(c, split="eval")
    act = baseline("pivot_push", e)
    assert isinstance(act, PivotThenPush)
    obs, _ = e.reset(seed=10000)
    obs, *_ = e.step(act(obs))
    assert act.mode == "pivot" and e.hold == {"duck_a": False, "duck_b": True}  # right duck stops: box turns right
    assert e.state["duck_b"]["policy"] == "velstand"
    while True:
        obs, _, term, trunc, info = e.step(act(obs))
        if term or trunc:
            break
    assert info["reason"] == "success" and act.phase == "push"


def test_box_start_offsets_the_box_within_the_scaled_range_and_keeps_the_ducks_on_it():
    cfg = load_config()
    cfg["env"]["box_start"].update(enabled=True, dx=0.15, dy=0.15, dyaw=45.0)
    env = CoPushEnv(cfg)
    b0 = env.box0
    for scale in (0.2, 1.0):
        env.set_box_range(scale)
        seen = []
        for seed in range(6):
            _, info = env.reset(seed=seed)
            box = info["box"]
            seen.append(box["yaw"])
            assert abs(box["x"] - b0["x"]) <= 0.15 * scale + 1e-9 and abs(box["y"] - b0["y"]) <= 0.15 * scale + 1e-9
            assert abs(box["yaw"] - b0["yaw"]) <= 45 * scale + 1e-9 and box["mass"] == b0["mass"]
            st = env.state
            for d in ("duck_a", "duck_b"):                 # both ducks behind the box's long face, facing it
                assert st[d]["policy"] == "shoepush" and not st[d]["fallen"]
                assert math.dist(st[d]["position"], st["box"]["position"]) < 0.16
        assert len(set(seen)) == 6
    assert env.set_box_range(3.0) == 1.0


def test_reset_option_box_pose_overrides_sampling():
    cfg = load_config()
    cfg["env"]["box_start"]["enabled"] = True
    env = CoPushEnv(cfg, split="eval")
    pose = {"x": 0.40, "y": 0.05, "yaw": 120.0}
    _, info = env.reset(seed=10000, options={"box": pose})
    assert {k: info["box"][k] for k in pose} == pose
    assert env.state["box"]["position"] == pytest.approx((0.40, 0.05), abs=0.005)
    assert math.degrees(env.state["box"]["yaw"]) % 180 == pytest.approx(120.0 % 180, abs=1.0)


def test_test_sets_are_deterministic_and_cover_the_full_range():
    from copush.experiments import make_test_set
    cfg = load_config()
    cfg["env"]["box_start"].update(enabled=True, dx=0.15, dy=0.15, dyaw=45.0, scale=0.2)
    a, b = make_test_set(cfg, 50, 7), make_test_set(cfg, 50, 7)
    assert a == b and a != make_test_set(cfg, 50, 8)
    assert max(abs(s["dyaw"]) for s in a) > 0.2 * 45                # scale ignored: the final range
    assert all(s["x"] == pytest.approx(cfg["box"]["x"] + s["dx"]) for s in a)
    for k, m in (("dx", 0.15), ("dyaw", 45.0)):                     # one start per 1/50 slice of each axis
        assert sorted(int((s[k] + m) / (2 * m) * 50) for s in a) == list(range(50))


def test_box_start_hard_frac_oversamples_the_long_turn_side_and_off_keeps_the_old_draws():
    cfg = load_config()
    cfg["env"]["box_start"].update(enabled=True, dx=0.15, dy=0.15, dyaw=45.0)
    plain = CoPushEnv(cfg)
    before = [plain.reset(seed=s)[1]["box"]["yaw"] for s in range(3)]
    cfg0 = copy.deepcopy(cfg)
    cfg0["env"]["box_start"]["hard_frac"] = 0.0                     # explicit off: same draws as before
    assert [CoPushEnv(cfg0).reset(seed=s)[1]["box"]["yaw"] for s in range(3)] == before
    cfg["env"]["box_start"].update(hard_frac=0.5, hard_min_dyaw=15.0)
    env = CoPushEnv(cfg)
    d = [env.reset(seed=s)[1]["box"]["yaw"] - env.box0["yaw"] for s in range(40)]
    assert all(-45.0 - 1e-9 <= x <= 45.0 + 1e-9 for x in d)
    hard = sum(x >= 15.0 for x in d)
    assert 12 <= hard <= 28                                          # about half (uniform would give ~13)


def test_reward_v13_is_v11_with_a_lower_time_penalty():
    from copush.config import effective_reward
    v11 = effective_reward(load_config(overrides={"reward": {"version": "v1.1"}}))
    v13 = effective_reward(load_config(overrides={"reward": {"version": "v1.3"}}))
    assert v11["time_penalty"] == 0.03 and v13["time_penalty"] == 0.01
    assert {k: v for k, v in v13.items() if k not in ("time_penalty", "version")} == \
        {k: v for k, v in v11.items() if k not in ("time_penalty", "version")}


def test_stage1_check_set_is_separate_from_the_test_set():
    from copush.experiments import load_test_set
    pose = lambda s: (s["x"], s["y"], s["yaw"])                      # noqa: E731
    test = load_test_set("experiments/test_sets/stage1.json")
    checks = load_test_set("experiments/test_sets/stage1_checks.json")
    assert len(checks["starts"]) == 50 and checks["rng_seed"] != test["rng_seed"]
    assert not {pose(s) for s in checks["starts"]} & {pose(s) for s in test["starts"]}
