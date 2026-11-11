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
}


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
    return cfg


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
