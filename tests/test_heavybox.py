"""experiments/d2-heavybox/h1-heavy-finetune.yaml: the heavy box is a config, and the default config is unchanged."""
from __future__ import annotations

import json
import math
import os

import pytest

from copush.config import effective_reward, load_config
from copush.experiments import copy_box_task, load_stage, load_test_set, repo_path, target_entry_m

H1 = "experiments/d2-heavybox/h1-heavy-finetune.yaml"
RUN_L2 = "experiments/d2-steering/night5/run-l2/config.yaml"
LIGHT = {"clean": "stage1_large", "noisy": "stage1_noisy_large", "L1": "stage1_L1_large", "L2": "stage1_L2_large"}


def test_default_config_still_has_the_light_box_task():
    c = load_config()
    assert c["box"]["mass"] == 0.15
    assert c["env"]["max_steps"] == 100
    assert c["env"]["random"]["box_mass"] == [0.10, 0.25]
    assert c["env"]["randomize"] is False
    assert c["reward"]["version"] == "v1.1"
    assert effective_reward(c)["time_penalty"] == 0.03
    assert sorted(c["reward_versions"]) == ["v1", "v1.1", "v1.2", "v1.3", "v1.4"]      # the heavy version lives in h1's config


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
