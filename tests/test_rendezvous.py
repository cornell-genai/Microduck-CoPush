"""copush.rendezvous and the env changes it needs: docking spots identical to the old placement, the push phase after a
rendezvous, box avoidance, spot assignment, the training env's per-duck rewards, and the eval set."""
from __future__ import annotations

import json
import math
import os

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
                               assign_spots, plan_path, sample_start, segment_hits_box, settings)

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
