"""CoPushSim (copush/sim.py), headless. Needs microduck_rl's environment and the policies:

    uv run --project ../microduck_rl --with pytest python -m pytest tests/test_copush_sim.py

Skipped (not failed) under this repo's own venv, which has no mujoco / onnxruntime / bam.
"""
from __future__ import annotations

import math
import os
import time

import pytest

pytest.importorskip("mujoco")
pytest.importorskip("onnxruntime")
pytest.importorskip("bam")
yaml = pytest.importorskip("yaml")

import mujoco  # noqa: E402

from copush.config import DEFAULT_PATH, load_config, policy_path  # noqa: E402

if not all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush")):
    pytest.skip("policies missing (scripts/fetch_policies.sh)", allow_module_level=True)

from copush.sim import CoPushSim  # noqa: E402

FAR_BOX = {"box": {"x": 3.0, "y": 0.0}}   # out of the ducks' way


@pytest.fixture(scope="module")
def idle_sim():
    return CoPushSim(load_config(overrides=FAR_BOX))


def test_yaml_and_flags_take_effect(tmp_path):
    import argparse
    from copush.config import add_config_args, config_from_args

    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(yaml.safe_dump({"duck_a": {"x": 0.05, "y": 0.25, "yaw": 30},
                                        "box": {"mass": 0.2}, "target": {"x": 1.5}}))
    p = argparse.ArgumentParser()
    add_config_args(p)
    args = p.parse_args(["--config", str(cfg_file), "--duck-b", "0,-0.3,-20", "--box", "0.5,0.1,45",
                         "--target-size", "0.5,0.3", "--policy-b", "shoepush"])
    cfg = config_from_args(args)
    st = CoPushSim(cfg).get_state()

    a, b, box = st["duck_a"], st["duck_b"], st["box"]
    assert a["position"] == pytest.approx((0.05, 0.25), abs=1e-6)            # from YAML
    assert math.degrees(a["yaw"]) == pytest.approx(30, abs=1e-6)
    assert b["position"] == pytest.approx((0.0, -0.3), abs=1e-6)             # from flags
    assert math.degrees(b["yaw"]) == pytest.approx(-20, abs=1e-6)
    assert box["position"] == pytest.approx((0.5, 0.1), abs=1e-6)
    assert math.degrees(box["yaw"]) == pytest.approx(45, abs=1e-6)
    assert st["goal"]["position"] == pytest.approx((1.5, 0.0))
    assert st["goal"]["size"] == pytest.approx((0.5, 0.3))
    assert a["policy"] == "velstand" and b["policy"] == "shoepush"
    sim_mass = CoPushSim(cfg)
    bid = mujoco.mj_name2id(sim_mass.m, mujoco.mjtObj.mjOBJ_BODY, "box")
    assert sim_mass.m.body_mass[bid] == pytest.approx(0.2)
    # untouched values keep the YAML file's defaults
    default = load_config(DEFAULT_PATH)
    assert cfg["duck_a"]["policy"] == default["duck_a"]["policy"]


def test_both_ducks_are_the_same_robot(idle_sim):
    m = idle_sim.m
    from copush.sim import ROBOT_XML
    alone = mujoco.MjSpec.from_file(ROBOT_XML).compile()

    def per_duck(prefix):
        root = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, prefix + "trunk_base")
        gs = [g for g in range(m.ngeom) if m.body_rootid[m.geom_bodyid[g]] == root]
        return {"geoms": len(gs),
                "colliding": sum(1 for g in gs if m.geom_contype[g] & 1),
                "joints": sum(1 for j in range(m.njnt) if m.jnt_bodyid[j] and m.body_rootid[m.jnt_bodyid[j]] == root),
                "actuators": sum(1 for i in range(m.nu) if m.actuator(i).name.startswith(prefix)),
                "backlash": sum(1 for j in range(m.njnt) if (m.joint(j).name or "").startswith(prefix + "passive_"))}

    a, b = per_duck("a_"), per_duck("b_")
    assert a == b
    assert a["geoms"] == alone.ngeom and a["joints"] == alone.njnt and a["actuators"] == alone.nu == 14
    assert a["colliding"] == sum(1 for g in range(alone.ngeom) if alone.geom_contype[g] & 1)
    assert a["backlash"] == 14                               # the backlash robot, both ducks


def test_target_has_no_collision():
    cfg = load_config(overrides={**FAR_BOX, "target": {"x": 0.0, "y": 0.10}})   # under duck A's feet
    sim = CoPushSim(cfg)
    g = sim.target_geom
    assert sim.m.geom_contype[g] == 0 and sim.m.geom_conaffinity[g] == 0
    for _ in range(25):
        sim.step({"A": (0.0, 0.0, 0.0), "B": (0.0, 0.0, 0.0)})
        pairs = sim.d.contact.geom[:sim.d.ncon]
        assert not (pairs == g).any()


def test_zero_command_keeps_both_ducks_standing(idle_sim):
    idle_sim.reset()
    low = {"duck_a": 1.0, "duck_b": 1.0}
    for _ in range(150):                                     # 3 s
        st = idle_sim.step({"A": (0, 0, 0), "B": (0, 0, 0)})
        for d in low:
            low[d] = min(low[d], st[d]["trunk_z"])
            assert st[d]["gravity"][2] < -0.90, (d, st["t"])
    assert not any(st["fallen"].values())
    assert min(low.values()) > 0.095                         # copush.metrics.TRUNK_Z_MIN


def test_commanding_only_a_moves_a_not_b(idle_sim):
    st0 = idle_sim.reset()
    st = idle_sim.step({"A": (0.3, 0.0, 0.0), "B": (0.0, 0.0, 0.0)}, duration=4.0)
    moved_a = math.dist(st["duck_a"]["position"], st0["duck_a"]["position"])
    moved_b = math.dist(st["duck_b"]["position"], st0["duck_b"]["position"])
    assert moved_a > 0.15, moved_a
    assert moved_b < 0.03, moved_b
    assert abs(math.degrees(st["duck_b"]["yaw"] - st0["duck_b"]["yaw"])) < 8


def test_faster_than_real_time(idle_sim):
    idle_sim.reset()
    t0 = time.perf_counter()
    idle_sim.step({"A": (0.2, 0, 0), "B": (0.2, 0, 0)}, duration=2.0)
    wall = time.perf_counter() - t0
    assert wall < 2.0, f"2 s of sim took {wall:.2f} s"


def test_policy_switch_and_contact_reporting():
    sim = CoPushSim(load_config(overrides={"box": {"x": 0.20, "y": 0.10}}))   # right in front of A
    sim.set_policy("A", "shoepush")
    st = sim.step({"A": (0.2, 0, 0)}, duration=2.0)
    assert st["duck_a"]["policy"] == "shoepush" and st["duck_b"]["policy"] == "velstand"
    assert st["contact"]["duck_a"]["total"] > 0
    assert st["contact"]["duck_b"]["total"] == 0
    assert set(st["contact"]["duck_a"]["total_by_part"]) <= {"feet", "thighs", "hips", "trunk", "head"}
    assert ("policy" in {k for _, k, _ in sim.pop_events()})
