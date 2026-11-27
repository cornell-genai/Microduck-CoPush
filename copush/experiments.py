"""Stage configs and fixed test sets for the generalization plan (experiments/).

    stage, cfg = load_stage("experiments/stage1-random-box-pose/config.yaml")
    starts = make_test_set(cfg, n=50, rng_seed=20261112)      # box poses from the final env.box_start range
    stats = test_set_episodes(cfg, starts, lambda env: baseline("pivot_push", env))

A stage config names the shared configs it builds on: `base` (configs/copush.yaml = the heavy box, the default;
configs/copush-light-box.yaml = the old light box, which every earlier config names), `reference` (a
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


def copy_box_task(cfg: dict, src: dict) -> dict:
    """cfg with the box task of src (another resolved config) copied in: the box mass, the episode step limit, the mass
    randomization range and the reward version (with its definition). Used to evaluate an existing set's env config,
    or the rendezvous pipeline, on a stage's box (for example the heavy box of experiments/d2-heavybox/)."""
    v = src["reward"]["version"]
    cfg["box"]["mass"] = src["box"]["mass"]
    cfg["env"]["max_steps"] = src["env"]["max_steps"]
    cfg["env"]["random"]["box_mass"] = list(src["env"]["random"]["box_mass"])
    cfg["reward"]["version"] = v
    cfg["reward_versions"][v] = dict(src["reward_versions"][v])
    return cfg


def target_entry_m(start: dict, target: dict, size) -> float:
    """How far the box centre must travel, straight toward the target centre, before it is inside the target
    rectangle (size = length, width along the target's own x, y): the shortest push that can count as a success."""
    d = math.hypot(start["x"] - target["x"], start["y"] - target["y"])
    if d == 0:
        return 0.0
    ux, uy = (start["x"] - target["x"]) / d, (start["y"] - target["y"]) / d
    c, s = math.cos(math.radians(target["yaw"])), math.sin(math.radians(target["yaw"]))
    lx, ly = ux * c + uy * s, -ux * s + uy * c
    r = min(size[0] / 2 / abs(lx) if lx else math.inf, size[1] / 2 / abs(ly) if ly else math.inf)
    return max(0.0, d - r)


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
