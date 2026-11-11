"""The B0 harness (scripts/b0/b0lib.py), and through it microduck_rl's infer_policy.py, as modules.

b0lib already loads `infer_policy` from $DUCK_SIM_RL or ../microduck_rl and holds the harness
constants (CONTROL_DT, SIM_DT, DECIMATION, SPAWN_Z, fall thresholds, BODY_GROUPS). copush.sim
uses the same ones instead of keeping its own copies. Both need microduck_rl's environment
(mujoco, onnxruntime, bam): `uv run --project ../microduck_rl python ...`.
"""
from __future__ import annotations

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_B0 = None


def b0lib():
    """scripts/b0/b0lib.py as a module (loaded once)."""
    global _B0
    if _B0 is None:
        path = os.path.join(ROOT, "scripts", "b0", "b0lib.py")
        spec = importlib.util.spec_from_file_location("b0lib", path)
        _B0 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_B0)
    return _B0


def infer_policy():
    """microduck_rl/scripts/infer_policy.py as a module."""
    return b0lib().infer_policy()
