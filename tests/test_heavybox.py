"""The heavy box is the default task; every earlier experiment config pins the light box; h1 is the heavy fine-tune."""
from __future__ import annotations

import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "rl"))

from copush.config import effective_reward, load_config
from copush.experiments import copy_box_task, load_stage, load_test_set, repo_path, target_entry_m

H1 = "experiments/d2-heavybox/h1-heavy-finetune.yaml"
RUN_L2 = "experiments/d2-steering/night5/run-l2/config.yaml"
LIGHT = {"clean": "stage1_large", "noisy": "stage1_noisy_large", "L1": "stage1_L1_large", "L2": "stage1_L2_large"}


HEAVY_CONFIGS = {H1}        # the configs that are meant to be the heavy box; every other config on disk must be the light box
LIGHT_TIME_PENALTY = {"experiments/stage1b-turn-direction-fix/b-lower-time-penalty/config.yaml": 0.01}   # its ONE change (reward v1.3)
LIGHT_BOX = {"box.mass": 0.15, "env.max_steps": 100, "reward.time_penalty": 0.03, "env.random.box_mass": [0.10, 0.25]}


def _box_task(c):
    return {"box.mass": c["box"]["mass"], "env.max_steps": c["env"]["max_steps"],
            "reward.time_penalty": effective_reward(c)["time_penalty"], "env.random.box_mass": c["env"]["random"]["box_mass"]}


def test_default_config_is_the_heavy_box_task():
    c = load_config()
    assert c["box"]["mass"] == 0.60
    assert c["env"]["max_steps"] == 130
    assert c["env"]["random"]["box_mass"] == [0.40, 1.00]
    assert c["env"]["randomize"] is False
    assert c["reward"]["version"] == "v1.1-t130"
    tp = effective_reward(c)["time_penalty"]
    assert tp == pytest.approx(3 / 130, abs=1e-6)
    assert tp * c["env"]["max_steps"] == pytest.approx(3.0, abs=1e-3)       # a full-length episode costs 3 in time penalty
    assert sorted(c["reward_versions"]) == ["v1", "v1.1", "v1.1-t130", "v1.2", "v1.3", "v1.4"]
    assert c["reward_versions"]["v1.1"]["time_penalty"] == 0.03             # the old versions keep their definitions
    # the same terms as v1.1, only the time penalty differs
    assert {k: v for k, v in effective_reward(c).items() if k not in ("time_penalty", "version")} == \
           {k: v for k, v in effective_reward(c, "v1.1").items() if k not in ("time_penalty", "version")}


def test_python_defaults_and_yaml_agree():
    from copush.config import DEFAULTS, DEFAULT_PATH
    c = load_config(None)                                                   # built-in DEFAULTS only
    y = load_config(DEFAULT_PATH)
    assert c["reward"]["version"] == y["reward"]["version"]
    assert _box_task(c) == _box_task(y)
    assert c["reward_versions"] == y["reward_versions"]
    assert DEFAULTS["env"]["max_steps"] == 130


def test_light_box_config_is_the_old_task():
    from copush.config import LIGHT_BOX_PATH
    c = load_config(LIGHT_BOX_PATH)
    assert _box_task(c) == LIGHT_BOX and c["reward"]["version"] == "v1.1" and "extends" not in c
    d = load_config()
    for sec in d:                                                           # nothing else differs from the default
        if sec not in ("box", "env", "reward"):
            assert c[sec] == d[sec], sec
    assert {k: v for k, v in c["env"].items() if k not in ("max_steps", "random")} == \
           {k: v for k, v in d["env"].items() if k not in ("max_steps", "random")}


from check_config_pins import resolve_all  # noqa: E402

_RES = resolve_all()                                                        # every YAML under configs/ and experiments/
_BOX_CONFIGS = sorted(k for k, r in _RES.items() if r.get("summary") and r["kind"] != "default")


def test_config_discovery_finds_the_configs():
    assert any(r["kind"] == "stage" for r in _RES.values()) and any(r["kind"] == "queue" for r in _RES.values())
    assert len(_BOX_CONFIGS) >= 40 and HEAVY_CONFIGS <= set(_BOX_CONFIGS)


@pytest.mark.parametrize("label", _BOX_CONFIGS)
def test_config_chooses_its_box_task(label):
    """Every stage / queue config under configs/ and experiments/ is the light box, except the heavy ones listed above.
    A new config that does not say `base: configs/copush-light-box.yaml` resolves to the heavy box and fails here."""
    s = _RES[label]["summary"]
    got = {"box.mass": s["box.mass"], "env.max_steps": s["env.max_steps"],
           "reward.time_penalty": s["reward"]["time_penalty"], "env.random.box_mass": s["env.random.box_mass"]}
    if label.split("::")[0] in HEAVY_CONFIGS:
        assert got["box.mass"] == 0.60 and got["env.max_steps"] == 130, label
    else:
        want = dict(LIGHT_BOX, **{"reward.time_penalty": LIGHT_TIME_PENALTY.get(label, 0.03)})
        assert got == want, f"{label} is not the light box: add `base: configs/copush-light-box.yaml` ({got})"
    assert s["env.randomize"] is False


def test_h1_still_resolves_exactly_as_before():
    _, h = load_stage(H1)
    assert (h["box"]["mass"], h["env"]["max_steps"], h["env"]["random"]["box_mass"], h["env"]["randomize"]) == \
           (0.60, 130, [0.40, 1.00], False)
    assert h["reward"]["version"] == "v1.1-t130"
    assert effective_reward(h) == {"version": "v1.1-t130", "w_pos": 10.0, "w_yaw": 1.0, "success_bonus": 10.0,
                                   "success_yaw_deg": 15.0, "success_hold_s": 1.0, "time_penalty": 0.023077,
                                   "fall_mode": "terminate", "fall_penalty": 10.0, "fall_min_down_s": 0.2, "fall_rate": 1.0,
                                   "box_fail_penalty": 10.0, "box_tilt_deg": 30.0, "box_lost_dist": 0.40,
                                   "cooperation_mode": "none", "coop_lambda": 5.0, "contact_penalty": 0.0,
                                   "contact_off_s": 0.3, "both_held_penalty": 0.0}


def test_extends_chain_and_loop(tmp_path):
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_text(f"extends: {b}\nbox: {{mass: 0.3}}\n")
    b.write_text("box: {mass: 0.2, x: 0.5}\n")
    c = load_config(str(a))
    assert (c["box"]["mass"], c["box"]["x"]) == (0.3, 0.5) and "extends" not in c
    b.write_text(f"extends: {a}\n")
    with pytest.raises(ValueError, match="extends loop"):
        load_config(str(a))


def test_earlier_stage_configs_resolve_to_the_light_box():
    for path in (RUN_L2, "experiments/stage1-random-box-pose/config.yaml", "experiments/d2-rendezvous/config.yaml"):
        _, c = load_stage(path)
        assert (c["box"]["mass"], c["env"]["max_steps"], effective_reward(c)["time_penalty"]) == (0.15, 100, 0.03), path


def test_h1_changes_only_the_box_task_from_run_l2():
    _, h = load_stage(H1)
    _, l2 = load_stage(RUN_L2)
    assert h["box"]["mass"] == pytest.approx(4 * l2["box"]["mass"])
    assert h["env"]["max_steps"] == 130
    assert h["env"]["random"]["box_mass"] == pytest.approx([4 * x for x in l2["env"]["random"]["box_mass"]])
    rh, rl = effective_reward(h), effective_reward(l2)
    assert rh["time_penalty"] * h["env"]["max_steps"] == pytest.approx(rl["time_penalty"] * l2["env"]["max_steps"], abs=1e-3)
    assert {k: v for k, v in rh.items() if k not in ("time_penalty", "version")} == \
           {k: v for k, v in rl.items() if k not in ("time_penalty", "version")}
    same = copy_box_task(json.loads(json.dumps(l2)), h)            # Run L2 with h1's box task = h1
    for sec in ("box", "env", "start_noise", "controller", "ppo", "layouts", "obs", "metrics", "target"):
        assert same[sec] == h[sec], sec
    assert effective_reward(same) == rh


def test_h1_stage_settings():
    s, _ = load_stage(H1)
    assert s["warm_start"] == "runs/d2-steering-night5/l2-s2/model.zip"
    assert (s["steps"], s["checkpoint_every"], s["keep_checkpoints"]) == (2000000, 200000, True)
    assert s["h1"]["seeds"] == [1, 2, 3] and s["h1"]["early_stop_at"] == 400000


def test_copy_box_task_touches_nothing_else():
    _, h = load_stage(H1)
    _, clean = load_stage("experiments/stage1-random-box-pose/config.yaml")
    before = json.loads(json.dumps(clean))
    after = copy_box_task(clean, h)
    assert (after["box"]["mass"], after["env"]["max_steps"], after["reward"]["version"]) == (0.60, 130, "v1.1-t130")
    for sec in before:
        if sec in ("box", "env", "reward", "reward_versions"):
            continue
        assert after[sec] == before[sec], sec
    assert {k: v for k, v in after["env"].items() if k not in ("max_steps", "random")} == \
           {k: v for k, v in before["env"].items() if k not in ("max_steps", "random")}
    assert after["start_noise"] == before["start_noise"]          # the clean set keeps its (zero) start noise


def test_target_entry_distance():
    tg = {"x": 1.0, "y": 0.0, "yaw": 90.0}                         # long (0.40) side along world y, short (0.20) along x
    assert target_entry_m({"x": 0.5, "y": 0.0}, tg, [0.40, 0.20]) == pytest.approx(0.5 - 0.10)
    assert target_entry_m({"x": 1.0, "y": 0.9}, tg, [0.40, 0.20]) == pytest.approx(0.9 - 0.20)
    assert target_entry_m({"x": 1.0, "y": 0.05}, tg, [0.40, 0.20]) == 0.0


def test_heavy_sets_are_the_light_sets_without_the_shortest_targets():
    s, h = load_stage(H1)
    reach, size = s["h1"]["solo_reach_m"], h["target"]["size"]
    for k, name in LIGHT.items():
        light = load_test_set(f"experiments/test_sets/{name}.json")
        heavy = load_test_set(f"experiments/test_sets/stage1_heavy_{k}_large.json")
        assert light["n"] == len(light["starts"]) == 200           # the old file is as it was
        by_id = {x["id"]: x for x in light["starts"]}
        assert all(by_id[x["id"]] == x for x in heavy["starts"])    # same starts, same ids (so the same episode seeds)
        kept = {x["id"] for x in heavy["starts"]}
        for x in light["starts"]:
            assert (target_entry_m(x, light["target"], size) > reach) == (x["id"] in kept)
        assert heavy["n"] == len(kept) and heavy["removed"] == 200 - len(kept) and heavy["target"] == light["target"]
        assert (heavy["mass"], heavy["max_steps"]) == (0.60, 130)


def test_heavy_check_set_is_separate_from_every_test_set():
    s, h = load_stage(H1)
    chk = load_test_set("experiments/test_sets/stage1_heavy_checks.json")
    assert chk["n"] == len(chk["starts"]) == 200 and chk["episode_seed0"] == 20000
    key = lambda x: (round(x["x"], 3), round(x["y"], 3), round(x["yaw"], 1))      # noqa: E731
    mine = {key(x) for x in chk["starts"]}
    assert len(mine) == 200
    for name in list(LIGHT.values()) + ["stage1_checks", "stage1_noisy_checks", "stage1"]:
        assert not mine & {key(x) for x in load_test_set(f"experiments/test_sets/{name}.json")["starts"]}, name
    assert all(target_entry_m(x, chk["target"], h["target"]["size"]) > s["h1"]["solo_reach_m"] for x in chk["starts"])


def test_time_limit_gives_two_ducks_30_percent_margin_and_one_duck_none():
    s, h = load_stage(H1)
    t = h["env"]["max_steps"] * h["env"]["step_s"]
    targets = json.load(open(repo_path("experiments/d2-heavybox/h1-heavy-finetune/results/targets.json")))
    assert t == pytest.approx(26.0) and targets["time_limit_s"] == pytest.approx(26.0)
    assert math.isclose(s["h1"]["solo_reach_m"], targets["speed_one_m_s"] * t, abs_tol=1e-3)
    for name in LIGHT.values():
        p90 = targets["sets"][f"experiments/test_sets/{name}.json"]["entry_m"]["p90"]
        assert targets["speed_two_m_s"] * t >= 1.30 * p90
    assert os.path.exists(repo_path("experiments/d2-heavybox/h1-heavy-finetune/PLAN.md"))


def test_200_start_heavy_sets_keep_the_old_starts_and_share_no_pose_with_the_check_set():
    s, h = load_stage(H1)
    reach, size = s["h1"]["solo_reach_m"], h["target"]["size"]
    key = lambda x: (round(x["x"], 3), round(x["y"], 3), round(x["yaw"], 1))      # noqa: E731
    chk = {key(x) for x in load_test_set("experiments/test_sets/stage1_heavy_checks.json")["starts"]}
    light = set()
    for name in LIGHT.values():
        light |= {key(x) for x in load_test_set(f"experiments/test_sets/{name}.json")["starts"]}
    new_poses = {}
    for k in LIGHT:
        big = load_test_set(f"experiments/test_sets/stage1_heavy_{k}_200.json")
        old = load_test_set(f"experiments/test_sets/stage1_heavy_{k}_large.json")
        assert big["n"] == len(big["starts"]) == 200 and big["episode_seed0"] == 10000
        assert big["starts"][:len(old["starts"])] == old["starts"]            # the old starts, unchanged and first
        new = big["starts"][len(old["starts"]):]
        assert len(new) == 200 - len(old["starts"]) and all(x["id"] >= 200 for x in new)
        assert len({x["id"] for x in big["starts"]}) == 200
        assert all(target_entry_m(x, big["target"], size) > reach for x in big["starts"])
        mine = {key(x) for x in new}
        assert len(mine) == len(new)
        assert not mine & chk and not mine & light
        new_poses[k] = mine
    assert new_poses["clean"] == new_poses["L1"] == new_poses["L2"]            # they share box poses, as the originals do
    assert not new_poses["noisy"] & new_poses["clean"]
