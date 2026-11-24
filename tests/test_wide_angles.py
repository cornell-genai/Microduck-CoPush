"""The central steering wider-angle curriculum and its fixed held-out sets."""
from __future__ import annotations

from copush.experiments import load_stage, load_test_set
from copush.rl_callbacks import scale_box_start


CONFIG = "experiments/steering/wide-angles/config.yaml"


def test_wide_angle_stage_starts_at_the_solved_range_and_covers_every_unique_box_angle():
    stage, cfg = load_stage(CONFIG)
    assert cfg["controller"]["mode"] == "central"
    assert cfg["env"]["stand_still"]["enabled"] is True
    assert cfg["env"]["box_start"]["dyaw"] == 90.0
    assert stage["widen"]["levels"] == [0.5, 0.625, 0.75, 0.875, 1.0]
    assert stage["widen"]["scale_check_starts"] is True
    assert stage["steps"] == 1_000_000 and stage["early_stop"]["evals"] == 0


def test_wide_angle_test_and_check_sets_are_separate_balanced_full_range_sets():
    stage, cfg = load_stage(CONFIG)
    test = load_test_set(stage["test_set"])["starts"]
    checks = load_test_set(stage["check_set"])["starts"]
    pose = lambda row: (row["x"], row["y"], row["yaw"])  # noqa: E731
    assert len(test) == 200 and len(checks) == 50
    assert not ({pose(row) for row in test} & {pose(row) for row in checks})
    assert min(row["dyaw"] for row in test) < -89 and max(row["dyaw"] for row in test) > 89
    assert sum(row["dyaw"] > 45 for row in test) == 50
    assert sum(row["dyaw"] < -45 for row in test) == 50
    scaled = [scale_box_start(row, cfg, 0.5) for row in checks]
    assert max(abs(row["dyaw"]) for row in scaled) <= 45
