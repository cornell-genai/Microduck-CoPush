"""The central steering experiment keeps a strict matched control."""
from __future__ import annotations

import copy

from copush.experiments import load_stage


CONTROL = "experiments/steering/control/config.yaml"
STAND = "experiments/steering/stand-still/config.yaml"


def test_central_steering_configs_differ_only_by_the_stand_still_switch():
    control_stage, control = load_stage(CONTROL)
    stand_stage, stand = load_stage(STAND)
    assert control["controller"]["mode"] == stand["controller"]["mode"] == "central"
    assert control["env"]["stand_still"]["enabled"] is False
    assert stand["env"]["stand_still"]["enabled"] is True

    matched = copy.deepcopy(stand)
    matched["env"]["stand_still"]["enabled"] = False
    assert matched == control
    assert control_stage["warm_start"] == stand_stage["warm_start"]
    assert control_stage["steps"] == stand_stage["steps"] == 1_000_000
    assert control_stage["early_stop"]["evals"] == stand_stage["early_stop"]["evals"] == 0
