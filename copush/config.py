"""configs/copush.yaml + command-line overrides -> one resolved config dict.

The resolved config is a plain dict with the YAML's shape (yaw in degrees, paths as written), so
it can be dumped back to `runs/<ts>/config.yaml` and reloaded unchanged:

    cfg = load_config()                                       # configs/copush.yaml
    cfg = load_config("my.yaml", {"box": {"x": 0.5}})         # YAML, then a nested override
    cfg = config_from_args(parser.parse_args())               # flags from add_config_args

Precedence: built-in defaults < YAML file < overrides (CLI flags).
"""
from __future__ import annotations

import argparse
import copy
import os
import re
from typing import Optional

import yaml

from copush.upstream import ROOT

DEFAULT_PATH = os.path.join(ROOT, "configs", "copush.yaml")
POLICY_NAMES = ("velstand", "shoepush")

DEFAULTS = {
    "duck_a": {"x": 0.0, "y": 0.10, "yaw": 0.0, "policy": "velstand"},
    "duck_b": {"x": 0.0, "y": -0.10, "yaw": 0.0, "policy": "velstand"},
    "box": {"x": 0.35, "y": 0.0, "yaw": 90.0, "mass": 0.15},
    "target": {"x": 1.20, "y": 0.0, "yaw": 90.0, "size": [0.40, 0.20]},
    "policies": {"velstand": "data/policies/velstand_v8/velstand.onnx",
                 "shoepush": "data/policies/robert/shoe_push/forward/policy.onnx"},
    "keyboard": {"vx_step": 0.05, "vyaw_step": 0.3, "vx_max": 0.3, "vx_min": -0.3, "vyaw_max": 1.5},
    "actuator": {"vin": 7.4, "vin_drop_gain": 0.1},
    "env": {"layout": "close", "settle_s": 0.3, "contact_setback": 0.095, "contact_spacing": 0.20,
            "step_s": 0.2, "max_steps": 100, "lose_contact_s": 0.5,
            "stand_still": {"enabled": False, "vx_threshold": 0.02}, "randomize": False,
            "random": {"box_x": [0.30, 0.36], "box_y": [-0.04, 0.04], "box_yaw": [75, 105],
                       "box_mass": [0.10, 0.25]},
            "heldout_seeds": [10000, 10099],
            "curriculum": {"enabled": False, "distances": [0.40, 0.60, 0.85], "offsets": [0.0, 0.10, 0.20],
                           "success_threshold": 0.8, "eval_episodes": 5}},
    "layouts": {"close": {"start_mode": "in_contact", "target": {"x": 0.75, "y": 0.0, "yaw": 90}},
                "steer": {"start_mode": "in_contact", "target": {"x": 0.75, "y": -0.30, "yaw": 90}},
                "hard": {"start_mode": "approach", "target": {"x": 1.20, "y": 0.0, "yaw": 90}}},
    "reward": {"version": "v1.1", "w_pos": 10.0, "w_yaw": 3.0, "success_bonus": 10.0, "success_yaw_deg": 15.0,
               "success_hold_s": 1.0, "time_penalty": 0.01, "fall_mode": "terminate",
               "fall_penalty": 10.0, "fall_min_down_s": 0.0, "fall_rate": 1.0, "box_fail_penalty": 5.0,
               "box_tilt_deg": 30.0, "box_lost_dist": 0.40, "cooperation_mode": "none", "coop_lambda": 5.0,
               "contact_penalty": 0.0, "contact_off_s": 0.3},
    "reward_versions": {"v1": {},
                        "v1.1": {"fall_min_down_s": 0.2, "w_yaw": 1.0, "box_fail_penalty": 10.0,
                                 "time_penalty": 0.03},
                        "v1.2": {"fall_min_down_s": 0.2, "w_yaw": 1.0, "box_fail_penalty": 10.0,
                                 "time_penalty": 0.03, "contact_penalty": 0.02}},
    "ppo": {"n_envs": 8, "total_steps": 300000, "n_steps": 256, "batch_size": 256, "n_epochs": 10,
            "learning_rate": 0.0003, "gamma": 0.99, "gae_lambda": 0.95, "clip_range": 0.2,
            "ent_coef": 0.01, "seed": 0},
    "video": {"width": 480, "height": 270, "fps": 25, "speedup": 2},
    "rl": {"eval_every": 10000, "eval_seed": 10000, "improve_margin": 2.0},
}
FALL_MODES = ("terminate", "continuous")
COOPERATION_MODES = ("none", "gated_balanced")


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(path: Optional[str] = DEFAULT_PATH, overrides: Optional[dict] = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        with open(path) as f:
            cfg = _merge(cfg, yaml.safe_load(f) or {})
    cfg = _merge(cfg, overrides or {})
    for duck in ("duck_a", "duck_b"):
        if cfg[duck]["policy"] not in POLICY_NAMES:
            raise ValueError(f"{duck}.policy must be one of {POLICY_NAMES}, got {cfg[duck]['policy']!r}")
    if cfg["reward"]["version"] not in cfg["reward_versions"]:
        raise ValueError(f"reward.version {cfg['reward']['version']!r} not in reward_versions {sorted(cfg['reward_versions'])}")
    if cfg["env"]["layout"] not in cfg["layouts"]:
        raise ValueError(f"env.layout {cfg['env']['layout']!r} not in layouts {sorted(cfg['layouts'])}")
    if cfg["reward"]["fall_mode"] not in FALL_MODES:
        raise ValueError(f"reward.fall_mode must be one of {FALL_MODES}, got {cfg['reward']['fall_mode']!r}")
    if cfg["reward"]["cooperation_mode"] not in COOPERATION_MODES:
        raise ValueError(f"reward.cooperation_mode must be one of {COOPERATION_MODES}, "
                         f"got {cfg['reward']['cooperation_mode']!r}")
    return cfg


def effective_reward(cfg: dict, version: Optional[str] = None) -> dict:
    """cfg["reward"] with reward_versions[version] (default: reward.version) applied on top."""
    v = version or cfg["reward"]["version"]
    if v not in cfg["reward_versions"]:
        raise ValueError(f"unknown reward version {v!r} (have {sorted(cfg['reward_versions'])})")
    out = _merge(cfg["reward"], cfg["reward_versions"][v])
    out["version"] = v
    return out


def with_reward_version(cfg: dict, version: str) -> dict:
    """A copy of cfg whose reward.version is `version`."""
    out = copy.deepcopy(cfg)
    effective_reward(out, version)                  # validates
    out["reward"]["version"] = version
    return out


def policy_path(cfg: dict, name: str) -> str:
    p = cfg["policies"][name]
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def dump_config(cfg: dict, path: str) -> None:
    with open(path, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


# ── CLI ──────────────────────────────────────────────────────────────────────

def _pose(text: str):
    """'x,y,yaw_deg' (yaw optional) -> dict."""
    parts = [float(p) for p in text.split(",")]
    if len(parts) not in (2, 3):
        raise argparse.ArgumentTypeError(f"expected x,y[,yaw_deg], got {text!r}")
    out = {"x": parts[0], "y": parts[1]}
    if len(parts) == 3:
        out["yaw"] = parts[2]
    return out


def _pair(text: str):
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"expected length,width, got {text!r}")
    return parts


def add_config_args(parser: argparse.ArgumentParser) -> None:
    g = parser.add_argument_group("scene (override configs/copush.yaml)")
    g.add_argument("--config", default=DEFAULT_PATH, help="YAML config (default: configs/copush.yaml)")
    g.add_argument("--duck-a", type=_pose, metavar="X,Y[,YAW]", help="duck A start (m, m, deg)")
    g.add_argument("--duck-b", type=_pose, metavar="X,Y[,YAW]", help="duck B start")
    g.add_argument("--box", type=_pose, metavar="X,Y[,YAW]", help="box start")
    g.add_argument("--target", type=_pose, metavar="X,Y[,YAW]", help="target centre")
    g.add_argument("--box-mass", type=float, metavar="KG")
    g.add_argument("--target-size", type=_pair, metavar="L,W", help="target length,width (m)")
    g.add_argument("--policy-a", choices=POLICY_NAMES, help="duck A's policy at reset")
    g.add_argument("--policy-b", choices=POLICY_NAMES, help="duck B's policy at reset")


_VALUE_FLAGS = ("--duck-a", "--duck-b", "--box", "--target", "--target-size")


def join_negative_values(argv):
    """['--duck-b', '-0.05,-0.1,15'] -> ['--duck-b=-0.05,-0.1,15'].

    argparse takes a value starting with '-' for an option unless it is a plain number, so
    `--duck-b -0.05,-0.1` would fail without this. Call it on argv before parse_args.
    """
    out, it = [], iter(list(argv))
    for a in it:
        if a in _VALUE_FLAGS:
            nxt = next(it, None)
            if nxt is not None and re.match(r"-\.?\d", nxt):
                out.append(f"{a}={nxt}")
                continue
            out.append(a)
            if nxt is not None:
                out.append(nxt)
        else:
            out.append(a)
    return out


def overrides_from_args(args: argparse.Namespace) -> dict:
    over: dict = {}
    for key, flag in (("duck_a", "duck_a"), ("duck_b", "duck_b"), ("box", "box"), ("target", "target")):
        if getattr(args, flag, None):
            over.setdefault(key, {}).update(getattr(args, flag))
    if getattr(args, "box_mass", None) is not None:
        over.setdefault("box", {})["mass"] = args.box_mass
    if getattr(args, "target_size", None):
        over.setdefault("target", {})["size"] = args.target_size
    if getattr(args, "policy_a", None):
        over.setdefault("duck_a", {})["policy"] = args.policy_a
    if getattr(args, "policy_b", None):
        over.setdefault("duck_b", {})["policy"] = args.policy_b
    return over


def config_from_args(args: argparse.Namespace) -> dict:
    return load_config(args.config, overrides_from_args(args))
