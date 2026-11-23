"""copush.rendezvous and the env changes it needs: docking spots identical to the old placement, the push phase after a
rendezvous, box avoidance, spot assignment, the training env's per-duck rewards, and the eval set."""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import pytest

from copush.config import load_config, policy_path

pytest.importorskip("gymnasium")
pytest.importorskip("mujoco")
if not all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush")):
    pytest.skip("policies missing (scripts/fetch_policies.sh)", allow_module_level=True)

from copush.env import docking_spots  # noqa: E402
from copush.experiments import load_stage, repo_path  # noqa: E402
from copush.rendezvous import (Rendezvous, RendezvousPairEnv, RendezvousVecEnv, ScriptedRendezvous,  # noqa: E402
                               approach_reward, assign_spots, dock_payout, plan_path, sample_start, segment_hits_box,
                               settings)

CONFIG = "experiments/d2-rendezvous/config.yaml"
NOISE = {"heading": {"duck_a": 7.0, "duck_b": -4.0}, "spacing": 0.03, "setback": {"duck_a": 0.02, "duck_b": -0.01}}


def _old_place(box, tg, setback, spacing, noise):
    """copush.env._place_in_contact before docking_spots was split out, verbatim."""
    b = math.radians(box["yaw"])
    t = (math.cos(b), math.sin(b))
    n = (-math.sin(b), math.cos(b))
    side = 1.0 if (tg["x"] - box["x"]) * n[0] + (tg["y"] - box["y"]) * n[1] >= 0 else -1.0
    face = (side * n[0], side * n[1])
    yaw = math.degrees(math.atan2(face[1], face[0]))
    half = (spacing + (noise["spacing"] if noise else 0.0)) / 2
    left = (-face[1], face[0])
    sgn = 1.0 if left[0] * t[0] + left[1] * t[1] >= 0 else -1.0
    out = {}
    for duck, k in (("duck_a", +1), ("duck_b", -1)):
        back = setback + (noise["setback"][duck] if noise else 0.0)
        cx, cy = box["x"] - face[0] * back, box["y"] - face[1] * back
        out[duck] = (cx + k * sgn * half * t[0], cy + k * sgn * half * t[1], yaw + (noise["heading"][duck] if noise else 0.0))
    return out


@pytest.mark.parametrize("box", [{"x": 0.35, "y": 0.0, "yaw": 90.0}, {"x": 0.45, "y": 0.12, "yaw": 131.0},
                                 {"x": 0.30, "y": -0.10, "yaw": 52.0}, {"x": 0.4, "y": 0.05, "yaw": 270.0}])
@pytest.mark.parametrize("noise", [None, NOISE])
def test_docking_spots_equal_the_old_placement_exactly(box, noise):
    tg = {"x": 0.95, "y": -0.30}
    assert docking_spots(box, tg, 0.095, 0.20, noise) == _old_place(box, tg, 0.095, 0.20, noise)


def test_docking_spots_ignore_a_half_turn_of_the_box():
    tg = {"x": 0.95, "y": -0.30}
    a = docking_spots({"x": 0.4, "y": 0.05, "yaw": 80.0}, tg, 0.095, 0.20)
    b = docking_spots({"x": 0.4, "y": 0.05, "yaw": 260.0}, tg, 0.095, 0.20)
    for d in a:
        assert a[d][:2] == pytest.approx(b[d][:2], abs=1e-12)
        assert math.cos(math.radians(a[d][2] - b[d][2])) == pytest.approx(1.0)


def test_paths_go_round_the_box():
    box = {"x": 0.35, "y": 0.0, "yaw": 90.0}               # long axis along y; push direction +x
    start, goal = (0.75, 0.02), (0.13, 0.0)                # in front of the box -> behind it
    assert segment_hits_box(start, goal, box, 0.08)
    path = plan_path(start, goal, box)
    pts = [start] + path
    assert path[-1] == goal and len(path) >= 2
    assert not any(segment_hits_box(p, q, box, 0.08) for p, q in zip(pts, pts[1:]))
    assert plan_path((0.0, 0.3), (0.13, 0.1), box) == [(0.13, 0.1)]      # clear line: straight


def test_assignment_breaks_near_ties_toward_the_spot_farther_from_the_target():
    st = {"duck_a": {"position": (-0.3, 0.0)}, "duck_b": {"position": (-0.5, 0.0)}, "goal": {"position": (0.95, -0.30)}}
    spots = {"left": (0.255, 0.1, 0.0), "right": (0.255, -0.1, 0.0)}   # both ducks on the axis between the spots
    a = assign_spots(st, spots, 0.05)
    assert a["duck_a"] == "left" and a["duck_b"] == "right"            # the left spot is farther from a target on the right
    st["duck_a"]["position"], st["duck_b"]["position"] = (0.1, 0.4), (0.1, -0.4)
    assert assign_spots(st, spots, 0.05) == {"duck_a": "left", "duck_b": "right"}
    st["duck_a"]["position"], st["duck_b"]["position"] = (0.1, -0.4), (0.1, 0.4)
    assert assign_spots(st, spots, 0.05) == {"duck_a": "right", "duck_b": "left"}


def test_scripted_rendezvous_then_push_phase():
    from copush.env import CoPushEnv
    _, cfg = load_stage(CONFIG)
    env = CoPushEnv(cfg, split="eval")
    rv = Rendezvous(env)
    start = json.load(open(repo_path("experiments/test_sets/rendezvous_large.json")))["starts"][4]
    rv.reset(start, seed=10004)
    assert all(env.sim.pol[d].policy == "velstand" for d in ("duck_a", "duck_b"))
    act = ScriptedRendezvous(rv)
    for _ in range(5):
        _, info = rv.step(act())
        assert all(env.sim.pol[d].policy == "velstand" for d in ("duck_a", "duck_b"))
    assert rv.steps == 5 and set(info) >= {"hit_box", "hit_ducks", "arrived", "errors"}
    obs, _ = env.begin_push_phase()
    assert obs.shape == env.observation_space.shape and env.steps == 0 and env.state["t"] == 0.0
    assert all(env.sim.pol[d].policy == "shoepush" for d in ("duck_a", "duck_b"))
    env.step(np.zeros(4, dtype=np.float32))
    assert env.steps == 1


def test_pair_env_gives_each_duck_its_own_reward():
    _, cfg = load_stage(CONFIG)
    env = RendezvousPairEnv(cfg)
    obs, info = env.reset(seed=3)
    assert obs.shape == (2, 14) and info["start"]["kind"] in ("uniform", "near_symmetric", "wrong_side")
    walk_a = np.array([[1.0, 0.0], [-1.0, 0.0]], dtype=np.float32)     # duck A walks, duck B stands
    rs = []
    for _ in range(4):
        obs, r, te, tr, info = env.step(walk_a)
        rs.append(r)
    rs = np.array(rs)
    assert rs.shape == (4, 2) and not np.allclose(rs[:, 0], rs[:, 1])


def test_reward_is_absolute_distance_and_heading_not_their_improvement():
    """r2: a duck that stands still still gets a nonzero (negative) reward every step, since the term is its
    current distance/heading, not whether it improved -- r1's reward vanished once a duck stopped moving."""
    _, cfg = load_stage(CONFIG)
    env = RendezvousPairEnv(cfg)
    obs, info = env.reset(seed=7)
    env._partial_given = {"duck_a": True, "duck_b": True}     # isolate the per-step term from the one-off bonus
    stand = np.array([[-1.0, 0.0], [-1.0, 0.0]], dtype=np.float32)
    rw = env.rw
    for _ in range(3):
        obs, r, te, tr, enfo = env.step(stand)
        for k, d in enumerate(("duck_a", "duck_b")):
            err = enfo["errors"][d]
            expected = -rw["w_dist"] * (err[0] / env.max_start_dist) - rw["w_yaw"] * (err[1] / math.pi) - rw["time"]
            assert r[k] == pytest.approx(expected, abs=1e-5)
            assert r[k] < 0                      # standing still still costs something (no collision, no bonus)
        if te or tr:
            break


def test_partial_arrival_bonus_is_given_once_per_duck_per_episode():
    """Drive with the scripted controller (real motion toward the spots, not blind forward walking in a random
    heading) over several starts: _partial_given flips at most once per duck per episode, and fires at least once."""
    _, cfg = load_stage(CONFIG)
    env = RendezvousPairEnv(cfg)
    any_bonus = False
    for seed in range(5):
        env.reset(seed=seed)
        act = ScriptedRendezvous(env.rv)
        seen = {"duck_a": 0, "duck_b": 0}
        for _ in range(50):
            before = dict(env._partial_given)
            _, r, te, tr, info = env.step(act(None))
            for k, d in enumerate(("duck_a", "duck_b")):
                if env._partial_given[d] and not before[d]:
                    seen[d] += 1
                    assert r[k] > env.rw["partial"] - 0.5     # the bonus dominates the reward on that step
            if te or tr:
                break
        assert all(v <= 1 for v in seen.values()), f"bonus given more than once (seed {seed}): {seen}"
        any_bonus = any_bonus or any(v == 1 for v in seen.values())
    assert any_bonus                             # at least one duck, in at least one of the 5 starts, got close


def test_holding_bonus_needs_three_consecutive_steps_under_15_degrees():
    """r3: +hold_bonus only once a duck's heading error has been under hold_yaw_deg for hold_min_steps steps in a
    row; the count resets when the error reaches hold_yaw_deg. r2's config has it off."""
    _, cfg2 = load_stage(CONFIG)
    assert RendezvousPairEnv(cfg2).rw["hold_bonus"] == 0.0
    _, cfg = load_stage("experiments/d2-rendezvous/r3-heading-bonus.yaml")
    env = RendezvousPairEnv(cfg)
    assert env.rw["w_yaw"] == 0.8 and env.rw["hold_bonus"] == 0.1
    env.rw = dict(env.rw, w_dist=0.0, w_yaw=0.0, time=0.0, collision=0.0, partial=0.0)   # isolate the holding bonus
    tol = math.radians(env.rw["hold_yaw_deg"])
    seen_bonus = False
    for seed in range(4):
        env.reset(seed=seed)
        act = ScriptedRendezvous(env.rv)
        run = {"duck_a": 0, "duck_b": 0}
        for _ in range(50):
            _, r, te, tr, info = env.step(act(None))
            if te or tr:
                break                                   # terminal steps add arrive/timeout on top
            for k, d in enumerate(("duck_a", "duck_b")):
                run[d] = run[d] + 1 if info["errors"][d][1] < tol else 0
                assert env._hold_count[d] == run[d]
                assert r[k] == pytest.approx(0.1 if run[d] >= 3 else 0.0, abs=1e-6)
                seen_bonus |= run[d] >= 3
    assert seen_bonus                                   # the scripted controller holds heading in some start


def test_approach_reward_formula_and_range():
    rw = {"approach": 0.5, "approach_m": 0.10, "approach_yaw_rad": 0.35}
    assert approach_reward(0.0, 0.0, rw) == pytest.approx(0.5)
    assert approach_reward(0.05, 0.175, rw) == pytest.approx(0.5 * 0.5 * 0.5)
    assert approach_reward(0.10, 0.0, rw) == 0.0 and approach_reward(0.3, 0.0, rw) == 0.0
    assert approach_reward(0.0, 0.35, rw) == 0.0 and approach_reward(0.0, 3.0, rw) == 0.0
    assert approach_reward(0.0, 0.0, {"approach": 0.0, "approach_m": 0.1, "approach_yaw_rad": 0.35}) == 0.0
    assert approach_reward(0.0, 0.0, {}) == 0.0                     # runs r1-r3 reward dicts have no approach key


def test_r4_reward_is_r3_plus_approach_without_partial_or_arrive():
    """r4: each non-terminal step's reward is r3's (partial 0) plus the approach term; on handoff no bonus."""
    _, cfg = load_stage("experiments/d2-rendezvous/r4-approach-bonus.yaml")
    env = RendezvousPairEnv(cfg)
    rw = env.rw
    assert (rw["w_yaw"], rw["hold_bonus"], rw["partial"], rw["arrive"], rw["approach"]) == (0.8, 0.1, 0.0, 0.0, 0.5)
    _, cfg2 = load_stage(CONFIG)
    assert RendezvousPairEnv(cfg2).rw["approach"] == 0.0               # r2's config unchanged
    seen_approach = False
    for seed in range(4):
        env.reset(seed=seed)
        act = ScriptedRendezvous(env.rv)
        hits = 0
        for _ in range(50):
            hold_before = dict(env._hold_count)
            _, r, te, tr, info = env.step(act(None))
            new_hits = sum(info["collisions"]["box"].values()) + info["collisions"]["ducks"]
            clean, hits = new_hits == hits, new_hits
            for k, d in enumerate(("duck_a", "duck_b")):
                dist, yaw = info["errors"][d]
                hold = hold_before[d] + 1 if yaw < math.radians(rw["hold_yaw_deg"]) else 0
                ap = approach_reward(dist, yaw, rw)
                exp = (-rw["w_dist"] * dist / env.max_start_dist - rw["w_yaw"] * yaw / math.pi - rw["time"]
                       + (rw["hold_bonus"] if hold >= rw["hold_min_steps"] else 0.0) + ap)
                if clean and not tr and not (te and info["reason"] != "arrived"):
                    assert r[k] == pytest.approx(exp, abs=1e-5)     # arrival adds nothing now
                seen_approach |= ap > 0
            if te or tr:
                break
    assert seen_approach


def test_dock_payout_formula():
    assert dock_payout(20, 50, {"dock_payout": 0.5}) == pytest.approx(15.0)   # the example: docking at step 20 pays 15
    assert dock_payout(50, 50, {"dock_payout": 0.5}) == 0.0
    assert dock_payout(60, 50, {"dock_payout": 0.5}) == 0.0                     # never negative
    assert dock_payout(10, 50, {}) == 0.0                                       # runs r1-r5 reward dicts: off


def test_r6_reward_is_r5_plus_the_docking_payout_only_on_docking():
    """r6: the same scripted episode gives r5's reward on every step, except the docking step, which adds
    0.5 x (max_steps - steps) to each duck. Timeouts and falls get nothing extra."""
    _, cfg5 = load_stage("experiments/d2-rendezvous/r5-bc-warmstart.yaml")
    _, cfg6 = load_stage("experiments/d2-rendezvous/r6-dock-payout.yaml")
    e5, e6 = RendezvousPairEnv(cfg5), RendezvousPairEnv(cfg6)
    assert e5.rw["dock_payout"] == 0.0 and e6.rw["dock_payout"] == 0.5
    assert {k: v for k, v in e6.rw.items() if k != "dock_payout"} == {k: v for k, v in e5.rw.items() if k != "dock_payout"}
    docked = 0
    for seed in range(6):
        e5.reset(seed=seed)
        e6.reset(seed=seed)
        a5, a6 = ScriptedRendezvous(e5.rv), ScriptedRendezvous(e6.rv)
        for _ in range(60):
            _, r5, te5, tr5, i5 = e5.step(a5(None))
            _, r6, te6, tr6, i6 = e6.step(a6(None))
            assert (te5, tr5, i5["reason"], i5["steps"]) == (te6, tr6, i6["reason"], i6["steps"])
            extra = 0.5 * (e6.rv.r["max_steps"] - i6["steps"]) if i6["reason"] == "arrived" else 0.0
            assert r6 == pytest.approx(r5 + extra, abs=1e-5)
            if te5 or tr5:
                docked += i6["reason"] == "arrived"
                break
    assert docked > 0                                                          # the payout path was exercised


def test_curriculum_advances_after_a_window_of_mostly_arrivals_and_not_before():
    _, cfg = load_stage(CONFIG)
    env = RendezvousPairEnv(cfg)
    env.cur_on, env.cur = True, {"levels": [[0.1, 0.1], [0.5, 0.5]], "advance_rate": 0.6, "window_steps": 100}
    env.cur_level = 0
    for arrived in (True, True, False):         # 2 of 3 arrived (67% > 60%), 3*40 = 120 duck steps >= window
        env._advance_curriculum(arrived, 40)
    assert env.cur_level == 1
    env.cur_level = 0
    env._cur_window.clear()
    env._cur_window_steps = 0
    for arrived in (False, False, True):        # 1 of 3 (33% < 60%): stays
        env._advance_curriculum(arrived, 40)
    assert env.cur_level == 0
    env.cur_level = 1                           # already at the top level: no window can push it further
    env._cur_window.clear()
    env._cur_window_steps = 0
    env._advance_curriculum(True, 1000)
    assert env.cur_level == 1


def test_early_stop_reason_fires_only_at_or_after_the_step_with_zero_arrivals():
    sys.path.insert(0, os.path.join(repo_path("scripts"), "rl"))
    from train_rendezvous import early_stop_reason
    assert early_stop_reason(step=400000, arrived=0, n=200, at_step=400000) is not None
    assert early_stop_reason(step=200000, arrived=0, n=200, at_step=400000) is None   # too early
    assert early_stop_reason(step=600000, arrived=3, n=200, at_step=400000) is None   # not zero
    assert early_stop_reason(step=600000, arrived=0, n=200, at_step=0) is None        # disabled


def test_vec_env_keeps_per_duck_rewards():
    from copush.rendezvous import make_rendezvous_vec_env
    _, cfg = load_stage(CONFIG)
    vec = make_rendezvous_vec_env(cfg, 1)                  # SubprocVecEnv, as in training
    try:
        assert isinstance(vec.venv, RendezvousVecEnv)
        vec.seed(5)
        o = vec.reset()
        assert o.shape == (2, 14)
        vec.step_async(np.array([[1.0, 0.0], [-1.0, 0.0]], dtype=np.float32))
        o, r, d, infos = vec.step_wait()
        assert o.shape == (2, 14) and r.shape == (2,) and len(infos) == 2 and r[0] != r[1]
    finally:
        vec.close()


def test_sampled_and_eval_starts_follow_the_rules():
    _, cfg = load_stage(CONFIG)
    sc = settings(cfg)["start"]
    rng = np.random.default_rng(0)
    kinds = [sample_start(rng, cfg, sc)["kind"] for _ in range(60)]
    assert set(kinds) <= {"uniform", "near_symmetric", "wrong_side"} and kinds.count("uniform") > 30
    d = json.load(open(repo_path("experiments/test_sets/rendezvous_large.json")))
    base = json.load(open(repo_path("experiments/test_sets/stage1_large.json")))["starts"]
    assert d["n"] == len(d["starts"]) == 200 and d["rng_seed"] == 20261122
    assert {k: sum(s["kind"] == k for s in d["starts"]) for k in d["kinds"]} == d["kinds"]
    for s, b in zip(d["starts"], base):
        assert (s["box"]["x"], s["box"]["y"], s["box"]["yaw"]) == pytest.approx((b["x"], b["y"], b["yaw"]), abs=1e-4)
        for duck in ("duck_a", "duck_b"):
            r = math.dist((s[duck]["x"], s[duck]["y"]), (s["box"]["x"], s["box"]["y"]))
            assert 0.2 - 0.021 <= r <= 0.8 + 0.021
        assert math.dist((s["duck_a"]["x"], s["duck_a"]["y"]), (s["duck_b"]["x"], s["duck_b"]["y"])) >= 0.15
        if s["kind"] == "wrong_side":
            assert s["flags"]["ducks_on_target_side"] == 2


def test_bc_demonstrations_are_the_scripted_actions_with_training_rewards_and_returns():
    """r5: bc_rendezvous collect records each duck's observation, the scripted action, and the discounted
    return-to-go of the training reward; r5-bc-warmstart.yaml's reward is r4's."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "rl"))
    import bc_rendezvous as bcr
    stage, cfg = load_stage("experiments/d2-rendezvous/r5-bc-warmstart.yaml")
    _, cfg4 = load_stage("experiments/d2-rendezvous/r4-approach-bonus.yaml")
    assert cfg["rendezvous"]["reward"] == cfg4["rendezvous"]["reward"]
    bc = bcr.bc_settings(stage)
    dcfg = bcr.demo_config(cfg, bc["dist_m"])
    assert dcfg["rendezvous"]["curriculum"]["enabled"] is False and cfg["rendezvous"]["curriculum"]["enabled"] is True
    obs_l, act_l, ret_l, ep_l, info_l = bcr._collect_chunk((dcfg, [5, 6], 0.99, 0.8))
    for obs, act, ret, ep, info in zip(obs_l, act_l, ret_l, ep_l, info_l):
        assert obs.shape == (2 * info["steps"], 14) and act.shape == (2 * info["steps"], 2) and ret.shape == (2 * info["steps"],)
        assert np.all(np.abs(act) <= 1.0) and np.all(ep == info["seed"])
    # replay seed 5 by hand: same observations and actions, and returns that satisfy G_t = r_t + gamma G_t+1
    env = RendezvousPairEnv(dcfg)
    env.max_start_dist = 0.8
    obs, _ = env.reset(seed=5)
    act = ScriptedRendezvous(env.rv)
    rews = []
    for t in range(info_l[0]["steps"]):
        a = np.asarray(act(None), dtype=np.float32).reshape(2, 2)
        assert np.allclose(obs_l[0][2 * t:2 * t + 2], obs) and np.allclose(act_l[0][2 * t:2 * t + 2], a)
        obs, r, te, tr, _ = env.step(a)
        rews.append(r)
    assert te or tr
    g = ret_l[0].reshape(-1, 2)
    assert np.allclose(g[-1], rews[-1], atol=1e-5)
    assert np.allclose(g[:-1], np.stack(rews[:-1]) + 0.99 * g[1:], atol=1e-4)
