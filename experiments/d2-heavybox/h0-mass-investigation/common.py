"""Shared setup for the box-mass investigation (evaluation only; nothing in copush/ or configs/ is changed)."""
from __future__ import annotations

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts", "rl")]
os.chdir(ROOT)

POLICY = "runs/d2-steering-night5/l2-s2/model.zip"
SET = "experiments/test_sets/stage1_large.json"
STAGE = "experiments/stage1-random-box-pose/config.yaml"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
BASE_MASS = 0.15
MODES = ("both", "A_idle", "B_idle")


def stage_cfg(mass: float, depth=None):
    """The clean stage 1 env config with the stand-still action on (as the night 5 evals) and the given box mass."""
    from copush.experiments import load_stage
    _, cfg = load_stage(STAGE)
    cfg["env"]["stand_still"] = {**cfg["env"]["stand_still"], "enabled": True}
    cfg["box"]["mass"] = float(mass)
    if depth is not None:                                  # a deeper box: the ducks start that much further back
        cfg["env"]["contact_setback"] = cfg["env"]["contact_setback"] + (float(depth) - 0.10) / 2
    return cfg


def set_box_shape(env, depth=None, com_drop=None):
    """depth: the box's short horizontal side (m; 0.10 now), changed in the compiled model (collision size and inertia).
    com_drop: move the box's centre of mass this far down from its geometric centre (m), e.g. a weight in its base."""
    import numpy as np
    sim = env.sim
    m, g, b = sim.m, sim.box_geom, sim.box_body
    if depth is not None:
        assert np.allclose(m.body_iquat[b], [1, 0, 0, 0]), m.body_iquat[b]
        L, D, H = (2 * float(x) for x in m.geom_size[g])
        mass0 = sim._box_mass0
        old = mass0 / 12 * np.array([D * D + H * H, L * L + H * H, L * L + D * D])
        assert np.allclose(sim._box_inertia0, old, rtol=1e-6), (sim._box_inertia0, old)
        D = float(depth)
        m.geom_size[g, 1] = D / 2
        m.geom_rbound[g] = float(np.linalg.norm(m.geom_size[g]))
        sim._box_inertia0 = mass0 / 12 * np.array([D * D + H * H, L * L + H * H, L * L + D * D])
        sim.set_box_mass(float(m.body_mass[b]))
    if com_drop:
        m.body_ipos[b, 2] = -float(com_drop)
        m.body_sameframe[b] = 0                            # or MuJoCo keeps using the body frame as the inertial frame
        m.body_simple[b] = 0


class ContactLog:
    """Where each duck touches the box, sampled once per control step (env.frame_hook): the height above the floor of
    every duck-box contact point, weighted by its normal force."""

    def __init__(self, env):
        import numpy as np
        self.env, self.f6 = env, np.zeros(6)
        self.acc = {d: {"w": 0.0, "wz": 0.0, "max": 0.0, "n": 0, "groups": {}} for d in ("duck_a", "duck_b")}
        env.frame_hook = self

    def __call__(self, st, _ret):
        import mujoco
        sim = self.env.sim
        m, d = sim.m, sim.d
        for ci in range(d.ncon):
            g1, g2 = (int(x) for x in d.contact.geom[ci])
            if sim.box_geom not in (g1, g2):
                continue
            owner = sim.geom_owner.get(g2 if g1 == sim.box_geom else g1)
            if owner is None:
                continue
            mujoco.mj_contactForce(m, d, ci, self.f6)
            fn = abs(float(self.f6[0]))
            if fn <= 1e-6:
                continue
            a = self.acc[owner[0]]
            z = float(d.contact.pos[ci][2])
            a["w"] += fn
            a["wz"] += fn * z
            a["max"] = max(a["max"], z)
            a["n"] += 1
            a["groups"][owner[1]] = a["groups"].get(owner[1], 0.0) + fn

    def result(self):
        return {d: {"mean_z": (a["wz"] / a["w"] if a["w"] > 0 else None), "max_z": (a["max"] if a["n"] else None), "n": a["n"],
                    "groups": {k: round(v / a["w"], 3) for k, v in a["groups"].items()} if a["w"] > 0 else {}}
                for d, a in self.acc.items()}


def set_box_friction(env, mu):
    """Box sliding friction mu for ALL the box's contacts (floor and ducks): MuJoCo uses the larger of the two geoms'
    frictions unless one has priority, so the box geom is given priority and its own friction is then the one used."""
    if mu is None:
        return
    m, g = env.sim.m, env.sim.box_geom
    m.geom_priority[g] = 1
    m.geom_friction[g, 0] = float(mu)


def set_box_floor_friction(env, mu):
    """Box-FLOOR sliding friction mu only. MuJoCo uses the larger of two touching geoms' frictions, or the friction of the
    geom with the higher priority. Every duck geom gets priority 1, so duck-box and duck-floor contacts keep the ducks'
    own friction (1.0); the box-floor contact (both priority 0) uses the larger value, the box's mu (so mu must be >= 1)."""
    if mu is None:
        return
    assert mu >= 1.0
    m = env.sim.m
    for g in env.sim.geom_owner:
        m.geom_priority[g] = 1
    m.geom_friction[env.sim.box_geom, 0] = float(mu)


def force_idle(action, mode):
    """A_idle / B_idle: that duck's speed command is forced to the lowest value every step, which the stand-still
    action turns into standing still on the standing policy (zero speed, zero turn)."""
    if mode == "A_idle":
        action[0], action[1] = -1.0, 0.0
    elif mode == "B_idle":
        action[2], action[3] = -1.0, 0.0
    return action


def box_xy(env):
    p = env.state["box"]["position"]
    return float(p[0]), float(p[1])


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])
