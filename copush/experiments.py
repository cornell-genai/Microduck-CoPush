"""Stage configs and fixed test sets for the generalization plan (experiments/).

    stage, cfg = load_stage("experiments/stage1-random-box-pose/config.yaml")
    starts = make_test_set(cfg, n=50, rng_seed=20261112)      # box poses from the final env.box_start range
    stats = test_set_episodes(cfg, starts, lambda env: baseline("pivot_push", env))

A stage config names the shared configs it builds on: `base` (configs/copush.yaml), `reference` (a
queue YAML whose `reference` block is the policy being built on, e.g. configs/overnight.yaml for
01_reference) and the stage's own `overrides` on top (ONE change). Paths are relative to the repo.

A test set is a list of explicit box poses (x, y, yaw in degrees, plus the offsets they were drawn
with), so it does not depend on any RNG once written. Episodes on it use the eval split and reset
with options={"box": pose}; episode i uses seed heldout_seeds[0] + i (only `random` depends on it).
"""
from __future__ import annotations

import json
import math
import os
from typing import Callable, List

import numpy as np
import yaml

from copush.config import _merge, load_config
from copush.upstream import ROOT


def repo_path(p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def load_stage(path: str):
    """-> (stage dict as written, resolved config dict)."""
    with open(repo_path(path)) as f:
        stage = yaml.safe_load(f)
    ref = {}
    if stage.get("reference"):
        with open(repo_path(stage["reference"])) as f:
            ref = yaml.safe_load(f).get("reference") or {}
    cfg = load_config(repo_path(stage.get("base", "configs/copush.yaml")), _merge(ref, stage.get("overrides") or {}))
    return stage, cfg


def make_test_set(cfg: dict, n: int, rng_seed: int) -> List[dict]:
    """n box poses over the FULL env.box_start range (scale ignored), Latin hypercube: each axis
    is cut into n equal slices with exactly one start in each, so every difficulty bucket gets its
    share (a plain uniform draw of 50 can put half of them in the hardest third)."""
    bs, box = cfg["env"]["box_start"], cfg["box"]
    rng = np.random.default_rng(rng_seed)
    u = {k: (rng.permutation(n) + rng.uniform(size=n)) / n for k in ("dx", "dy", "dyaw")}
    out = []
    for i in range(n):
        dx, dy, dyaw = (float(bs[k] * (2 * u[k][i] - 1)) for k in ("dx", "dy", "dyaw"))
        out.append({"id": i, "dx": round(dx, 5), "dy": round(dy, 5), "dyaw": round(dyaw, 3),
                    "x": round(box["x"] + dx, 5), "y": round(box["y"] + dy, 5), "yaw": round(box["yaw"] + dyaw, 3)})
    return out


def load_test_set(path: str) -> dict:
    with open(repo_path(path)) as f:
        return json.load(f)


def test_set_episodes(cfg: dict, starts: List[dict], make_act: Callable, first_steps: int = 5) -> List[dict]:
    """One episode per start; make_act(env, seed) -> act(obs), called per episode. Each episode's
    stats get `start` (the pose) and `touch_s` (each duck's contact time over the first
    first_steps env steps, a check that the ducks really start against the box)."""
    from copush.env import CoPushEnv
    env = CoPushEnv(cfg, split="eval")
    seed0 = cfg["env"]["heldout_seeds"][0]
    out = []
    for i, s in enumerate(starts):
        act = make_act(env, seed0 + i)
        obs, _ = env.reset(seed=seed0 + i, options={"box": s})
        touch, k = {"duck_a": 0.0, "duck_b": 0.0}, 0
        while True:
            obs, _, te, tr, info = env.step(act(obs))
            k += 1
            if k <= first_steps:
                for d in touch:
                    touch[d] += info["contact_time"][d]
            if te or tr:
                out.append(dict(info["episode_stats"], start=s, touch_s=touch))
                break
    return out


def difficulty(start: dict) -> dict:
    """Bucketing keys: offset size (m) and absolute angle (deg)."""
    return {"offset": math.hypot(start["dx"], start["dy"]), "angle": abs(start["dyaw"])}
