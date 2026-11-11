"""Two MicroDucks, one box, one target: the CoPush world on the B0 harness path.

Same physics path as scripts/b0 (CPU MuJoCo, 200 Hz physics, 50 Hz ONNX policy, BAM M6 XL330
actuators), with two ducks instead of one. Not duck-sim / robotd: that runs in wall-clock time,
Shoe Push misbehaves under it, and its second duck is a different robot (WEEK1_STATUS.md §2-3).

World (built with MjSpec, nothing installed into microduck_rl):
  * scenes/copush_base.xml: floor, light, visuals (as scenes/scene_box.xml)
  * robot_groundcontact_backlash.xml attached twice, prefixes `a_` and `b_`, so both ducks are the
    robot velstand and Shoe Push were run on in B0
  * box: free joint `box_free`, 28 x 10 x 9 cm, mass from the config
  * target: flat geom `target`, contype = conaffinity = 0 (visual only)

Ducks spawn in DEFAULT_POSE with the trunk at z 0.125 and the configured yaw, like
b0lib.Rollout.reset: the heading is exact and there is no stand-up phase. (The SIT keyframe fix in
WEEK1_STATUS.md is only needed on the duck-sim path.)

    sim = CoPushSim(load_config())
    sim.reset()
    sim.set_policy("A", "shoepush")
    state = sim.step({"A": (0.2, 0, 0), "B": (0.2, 0, 0)})        # one 0.02 s control step
    state = sim.step({"A": (0.2, 0, 0)}, duration=1.0)             # B keeps its last command

`get_state()` follows copush.state (duck_a / duck_b / box / goal, positions (x, y), yaw in rad)
with extras; see its docstring.
"""
from __future__ import annotations

import contextlib
import io
import math
import os
from typing import Dict, List, Optional, Tuple

import mujoco
import numpy as np

from copush.config import policy_path
from copush.duck_policy import DuckPolicy, load_sessions
from copush.metrics import orientation_error, position_error
from copush.upstream import ROOT, b0lib

_B0 = b0lib()
_IP = _B0.infer_policy()
CONTROL_DT, SIM_DT, DECIMATION = _B0.CONTROL_DT, _B0.SIM_DT, _B0.DECIMATION
SPAWN_Z, BOX_HALF_Z = _B0.SPAWN_Z, _B0.BOX_HALF_Z
FALL_TILT_DEG, FALL_Z = _B0.FALL_TILT_DEG, _B0.FALL_Z
BOX_HALF = (0.14, 0.05, BOX_HALF_Z)
ROBOT_XML = os.path.join(_B0.SCENE_DIR, "robot_groundcontact_backlash.xml")
BASE_XML = os.path.join(ROOT, "scenes", "copush_base.xml")
PREFIX = {"duck_a": "a_", "duck_b": "b_"}
DUCKS = tuple(PREFIX)
GROUPS = tuple(g for _, g in _B0.BODY_GROUPS)          # feet, thighs, hips, trunk, head
TARGET_RGBA = (0.1, 1.0, 0.3, 0.45)


def duck_key(name: str) -> str:
    """'A' / 'a' / 'duck_a' -> 'duck_a'."""
    k = name.lower()
    k = k if k.startswith("duck_") else "duck_" + k
    if k not in PREFIX:
        raise KeyError(f"unknown duck {name!r} (use A or B)")
    return k


def _quat_yaw(yaw: float):
    return [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]


def _bam_convert(spec: mujoco.MjSpec, bam_model) -> List[str]:
    """infer_policy.load_mujoco_with_bam's actuator conversion, applied to an in-memory spec.

    Position actuators -> torque motors with the voltage-bounded forcerange; their joints'
    damping/frictionloss zeroed (BAM rewrites them every step) and the stiff friction constraint.
    Returns the converted actuator names (both ducks, prefixed).
    """
    force_limit = bam_model.actuator.vin * bam_model.kt.value / bam_model.R.value
    joints = {j.name: j for j in spec.joints}
    names = []
    for act in spec.actuators:
        tgt = act.target
        tgt_name = tgt.name if hasattr(tgt, "name") else str(tgt)
        if "passive_" in tgt_name:          # upstream: startswith("passive_"); ours carry a prefix
            continue
        act.set_to_motor()
        act.forcelimited = True
        act.forcerange = (-force_limit, force_limit)
        act.ctrllimited = False
        act.gear = [1.0, 0, 0, 0, 0, 0]
        names.append(act.name)
        joint = joints.get(tgt_name)
        if joint is not None:
            joint.damping = np.zeros((3, 1))
            joint.frictionloss = 0.0
            joint.solref_friction = _IP.BAM_STIFF_SOLREF_FRICTION
            joint.solimp_friction = _IP.BAM_STIFF_SOLIMP_FRICTION
    return names


def build_spec(cfg: dict) -> mujoco.MjSpec:
    """The two-duck world as an MjSpec (actuators still MJCF position servos)."""
    spec = mujoco.MjSpec.from_file(BASE_XML)
    for duck, prefix in PREFIX.items():
        # a fresh spec per attach: attach renames the child spec it is given
        child = mujoco.MjSpec.from_file(ROBOT_XML)
        frame = spec.worldbody.add_frame()
        spec.attach(child, frame=frame, prefix=prefix)
    b = cfg["box"]
    body = spec.worldbody.add_body(name="box", pos=[b["x"], b["y"], BOX_HALF_Z],
                                   quat=_quat_yaw(math.radians(b["yaw"])))
    body.add_freejoint(name="box_free")
    body.add_geom(name="box_geom", type=mujoco.mjtGeom.mjGEOM_BOX, size=list(BOX_HALF),
                  mass=float(b["mass"]), rgba=[0.75, 0.45, 0.2, 1])
    t = cfg["target"]
    spec.worldbody.add_geom(name="target", type=mujoco.mjtGeom.mjGEOM_BOX,
                            size=[t["size"][0] / 2, t["size"][1] / 2, 0.0005],
                            pos=[t["x"], t["y"], 0.0006], quat=_quat_yaw(math.radians(t["yaw"])),
                            contype=0, conaffinity=0, rgba=list(TARGET_RGBA))
    return spec


class CoPushSim:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        ip = _IP
        act = cfg["actuator"]
        vdg = act["vin_drop_gain"] if act["vin_drop_gain"] > 0 else None
        self.bam_model = ip.load_bam_model(ip.BAM_KP_FW, act["vin"], None)
        self.spec = build_spec(cfg)
        names = _bam_convert(self.spec, self.bam_model)
        self.m = m = self.spec.compile()
        m.opt.timestep = SIM_DT
        self.d = d = mujoco.MjData(m)

        from bam.mujoco import MujocoController
        paths = {n: policy_path(cfg, n) for n in cfg["policies"]}
        missing = [p for p in paths.values() if not os.path.exists(p)]
        if missing:
            raise FileNotFoundError("policy file(s) missing, run scripts/fetch_policies.sh:\n  " + "\n  ".join(missing))
        sessions = load_sessions(paths)
        self.bam: Dict[str, object] = {}
        self.pol: Dict[str, DuckPolicy] = {}
        self._free: Dict[str, Tuple[int, int]] = {}
        for duck, prefix in PREFIX.items():
            own = [n for n in names if n.startswith(prefix)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.bam[duck] = MujocoController(self.bam_model, own, m, d,
                                                  vin_drop_gain=vdg, vin_min=ip.BAM_VIN_MIN)
            self.pol[duck] = DuckPolicy(m, d, prefix, self.bam[duck], sessions, cfg[duck]["policy"])
            j = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, prefix + "trunk_base_freejoint")
            self._free[duck] = (int(m.jnt_qposadr[j]), int(m.jnt_dofadr[j]))
        jb = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "box_free")
        self._box = (int(m.jnt_qposadr[jb]), int(m.jnt_dofadr[jb]))
        self.box_geom = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "box_geom")
        self.target_geom = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "target")

        # geom -> (duck, body-part group), for robot geoms only (b0lib.BODY_GROUPS on unprefixed names)
        self.geom_owner: Dict[int, Tuple[str, str]] = {}
        for g in range(m.ngeom):
            bname = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, int(m.geom_bodyid[g])) or ""
            for duck, prefix in PREFIX.items():
                if bname.startswith(prefix):
                    self.geom_owner[g] = (duck, _B0.body_group(bname[len(prefix):]))
        self._cos_fall = math.cos(math.radians(FALL_TILT_DEG))
        self._f6 = np.zeros(6)
        self.events: List[Tuple[float, str, str]] = []
        self.reset()

    # ── episode ─────────────────────────────────────────────────────────────
    def reset(self) -> dict:
        """Put both ducks, the box and the policies back to the config's start state."""
        m, d, cfg = self.m, self.d, self.cfg
        mujoco.mj_resetData(m, d)
        for duck in DUCKS:
            qa, _ = self._free[duck]
            c = cfg[duck]
            d.qpos[qa:qa + 7] = [c["x"], c["y"], SPAWN_Z, *_quat_yaw(math.radians(c["yaw"]))]
            pol = self.pol[duck]
            d.qpos[pol.qpos_idx] = pol.default_pose
        qb, _ = self._box
        b = cfg["box"]
        d.qpos[qb:qb + 7] = [b["x"], b["y"], BOX_HALF_Z, *_quat_yaw(math.radians(b["yaw"]))]
        for duck in DUCKS:
            self.bam[duck].reset(d.qpos)
            self.bam[duck].last_ts = d.time
            self.pol[duck].reset()
            self.pol[duck].set_policy(cfg[duck]["policy"])
        mujoco.mj_forward(m, d)
        self.t = 0.0
        self.fallen = {k: False for k in DUCKS}
        self.contact_step = {k: {} for k in DUCKS}        # impulse by part, last control step
        self.contact_total = {k: {} for k in DUCKS}       # impulse by part, since reset
        self.events.append((0.0, "reset", "scene reset"))
        return self.get_state()

    def set_policy(self, duck: str, name: str) -> None:
        k = duck_key(duck)
        if self.pol[k].policy != name:
            self.pol[k].set_policy(name)
            self.events.append((self.t, "policy", f"{k} -> {name}"))

    def toggle_policy(self, duck: str) -> str:
        k = duck_key(duck)
        new = "shoepush" if self.pol[k].policy == "velstand" else "velstand"
        self.set_policy(k, new)
        return new

    def pop_events(self) -> List[Tuple[float, str, str]]:
        ev, self.events = self.events, []
        return ev

    # ── stepping ────────────────────────────────────────────────────────────
    def step(self, commands: Optional[dict] = None, duration: float = CONTROL_DT) -> dict:
        """Advance `duration` seconds (whole control steps, at least one).

        commands: {"A": (vx, vy, vyaw), "B": ...} in each duck's body frame (keys A/B or
        duck_a/duck_b). A duck left out keeps its previous command.
        """
        for name, cmd in (commands or {}).items():
            self.pol[duck_key(name)].set_cmd(*(float(c) for c in cmd))
        n = max(1, int(round(duration / CONTROL_DT)))
        for _ in range(n):
            self._control_step()
        return self.get_state()

    def _control_step(self) -> None:
        m, d = self.m, self.d
        for duck in DUCKS:
            self.pol[duck].step()
        step_imp = {k: {} for k in DUCKS}
        for _ in range(DECIMATION):
            for duck in DUCKS:
                self.bam[duck].update()
            mujoco.mj_step(m, d)
            if d.ncon:
                geoms = d.contact.geom[:d.ncon]
                for ci in np.nonzero((geoms == self.box_geom).any(axis=1))[0]:
                    g1, g2 = geoms[ci]
                    other = g2 if g1 == self.box_geom else g1
                    owner = self.geom_owner.get(int(other))
                    if owner is None:
                        continue
                    mujoco.mj_contactForce(m, d, int(ci), self._f6)
                    duck, grp = owner
                    step_imp[duck][grp] = step_imp[duck].get(grp, 0.0) + float(abs(self._f6[0])) * SIM_DT
        self.t = round(self.t + CONTROL_DT, 10)
        for duck in DUCKS:
            self.contact_step[duck] = step_imp[duck]
            tot = self.contact_total[duck]
            for grp, v in step_imp[duck].items():
                tot[grp] = tot.get(grp, 0.0) + v
            if not self.fallen[duck] and self._is_fallen(duck):
                self.fallen[duck] = True
                self.events.append((self.t, "fall", f"{duck} fell"))

    def _is_fallen(self, duck: str) -> bool:
        qa, _ = self._free[duck]
        q = self.d.qpos[qa + 3:qa + 7]
        up_z = 1 - 2 * (q[1] ** 2 + q[2] ** 2)
        return bool(up_z < self._cos_fall or self.d.qpos[qa + 2] < FALL_Z)

    # ── state ───────────────────────────────────────────────────────────────
    def get_state(self) -> dict:
        """copush.state-shaped dict plus extras.

        duck_a / duck_b: position (x, y), yaw (rad), velocity (vx, vy) world frame, trunk_z,
            gravity (projected, body frame), tilt_deg, fallen, policy, cmd (vx, vy, vyaw)
        box: position, yaw, velocity, z;  goal: position, yaw, size
        box_to_target (m), yaw_error (rad; the box is 180-degree symmetric), inside (box centre
            within the target rectangle)
        contact[duck]: impulse / by_part over the last control step (N*s), total / total_by_part
            since reset; in_contact = any impulse in the last control step
        fallen[duck]: tilt > 60 deg or trunk z < 0.07 at any point since reset (sticky)
        """
        d = self.d
        st: dict = {"t": self.t}
        for duck in DUCKS:
            qa, va = self._free[duck]
            q = d.qpos[qa + 3:qa + 7]
            pol = self.pol[duck]
            grav = pol.projected_gravity()
            st[duck] = {
                "position": (float(d.qpos[qa]), float(d.qpos[qa + 1])),
                "yaw": _B0.yaw_of(q),
                "velocity": (float(d.qvel[va]), float(d.qvel[va + 1])),
                "trunk_z": float(d.qpos[qa + 2]),
                "gravity": tuple(float(g) for g in grav),
                "tilt_deg": math.degrees(math.acos(max(-1.0, min(1.0, 1 - 2 * (q[1] ** 2 + q[2] ** 2))))),
                "fallen": self.fallen[duck],
                "policy": pol.policy,
                "cmd": pol.cmd,
            }
        qb, vb = self._box
        box_xy = (float(d.qpos[qb]), float(d.qpos[qb + 1]))
        box_yaw = _B0.yaw_of(d.qpos[qb + 3:qb + 7])
        st["box"] = {"position": box_xy, "yaw": box_yaw,
                     "velocity": (float(d.qvel[vb]), float(d.qvel[vb + 1])), "z": float(d.qpos[qb + 2])}
        t = self.cfg["target"]
        goal_xy, goal_yaw = (float(t["x"]), float(t["y"])), math.radians(t["yaw"])
        st["goal"] = {"position": goal_xy, "yaw": goal_yaw, "size": tuple(t["size"])}
        st["box_to_target"] = position_error(box_xy, goal_xy)
        st["yaw_error"] = orientation_error(box_yaw, goal_yaw, symmetric=True)
        dx, dy = box_xy[0] - goal_xy[0], box_xy[1] - goal_xy[1]
        lx = dx * math.cos(goal_yaw) + dy * math.sin(goal_yaw)
        ly = -dx * math.sin(goal_yaw) + dy * math.cos(goal_yaw)
        st["inside"] = abs(lx) <= t["size"][0] / 2 and abs(ly) <= t["size"][1] / 2
        st["contact"] = {
            duck: {"impulse": sum(self.contact_step[duck].values(), 0.0),
                   "by_part": dict(self.contact_step[duck]),
                   "in_contact": bool(self.contact_step[duck]),
                   "total": sum(self.contact_total[duck].values(), 0.0),
                   "total_by_part": dict(self.contact_total[duck])}
            for duck in DUCKS}
        st["fallen"] = dict(self.fallen)
        return st
