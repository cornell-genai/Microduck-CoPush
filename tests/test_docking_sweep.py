"""scripts/rl/docking_sweep.py: the baseline placement equals copush.env's own, and the configs move the ducks as described."""
from __future__ import annotations

import math
import os
import sys

import pytest

from copush.config import load_config, policy_path

pytest.importorskip("gymnasium")
pytest.importorskip("mujoco")
if not all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush")):
    pytest.skip("policies missing (scripts/fetch_policies.sh)", allow_module_level=True)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "rl"))
from copush.env import CoPushEnv  # noqa: E402
from docking_sweep import CONFIGS, make_env_class  # noqa: E402

NOISE = {"heading": {"duck_a": 7.0, "duck_b": -4.0}, "spacing": 0.03, "setback": {"duck_a": 0.02, "duck_b": -0.01}}


def _cfg(box):
    cfg = load_config(overrides={"env": {"layout": "steer"}})
    cfg["env"]["box_start"].update(enabled=True, dx=0.15, dy=0.15, dyaw=45.0)
    cfg["box"].update(box)
    return cfg


def _ducks(env):
    return {d: (env.cfg[d]["x"], env.cfg[d]["y"], env.cfg[d]["yaw"]) for d in ("duck_a", "duck_b")}


@pytest.mark.parametrize("box", [{"x": 0.35, "y": 0.0, "yaw": 90.0}, {"x": 0.45, "y": 0.12, "yaw": 131.0},
                                 {"x": 0.30, "y": -0.10, "yaw": 52.0}])
@pytest.mark.parametrize("noise", [None, NOISE])
def test_baseline_placement_is_the_envs_own(box, noise):
    ref, dock = CoPushEnv(_cfg(box)), make_env_class()(_cfg(box))
    dock.placement = CONFIGS["baseline"]
    ref._place_in_contact(noise)
    dock._place_in_contact(noise)
    a, b = _ducks(ref), _ducks(dock)
    for d in a:
        assert a[d] == pytest.approx(b[d], abs=1e-12)


def test_configs_keep_the_pair_spacing_and_move_the_ducks_as_described():
    box = {"x": 0.35, "y": 0.0, "yaw": 90.0}              # long axis along y; target ahead (+x) so the ducks sit at lower x
    dock = make_env_class()(_cfg(box))
    for name, p in CONFIGS.items():
        dock.placement = p
        dock._place_in_contact(None)
        a, b = dock.cfg["duck_a"], dock.cfg["duck_b"]
        assert math.dist((a["x"], a["y"]), (b["x"], b["y"])) == pytest.approx(math.hypot(0.20, p["a_back"] - p["b_back"]), abs=1e-9), name
        assert a["x"] == pytest.approx(dock.cfg["box"]["x"] - p["a_back"], abs=1e-9) or a["x"] == pytest.approx(dock.cfg["box"]["x"] + p["a_back"], abs=1e-9)
        assert abs(abs(a["y"]) - p["a_off"]) < 1e-9 and abs(abs(b["y"]) - p["b_off"]) < 1e-9, name
        assert a["y"] * b["y"] < 0, name                    # A and B stay on opposite sides of the box centre
