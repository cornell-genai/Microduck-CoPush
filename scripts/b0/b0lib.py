"""Shared code for the B0 (one duck + Shoe Push) scripts in scripts/b0/.

Runs a Microduck ONNX policy on CPU MuJoCo with the SAME observation builder and BAM M6 actuator
model as microduck_rl/scripts/infer_policy.py: `PolicyInference`, `load_bam_model` and
`load_mujoco_with_bam` are imported from that file, not copied, so the rollouts here and the
infer_policy viewer are one code path. (A headless run of infer_policy's own main() matched this
to the millimetre.)

This is NOT the robotd path that duck-sim / copush.runner use: duck-sim's body server runs the
MJCF position actuators under robotd, this runs BAM under infer_policy's loop. Check findings that
matter on both (scripts/b0/duck_sim_drive.py drives a duck-sim duck).

Run every script in scripts/b0/ with microduck_rl's environment (mujoco, onnxruntime, bam):

    uv run --project ../microduck_rl python scripts/b0/<script>.py ...

Paths: microduck_rl = $DUCK_SIM_RL or ../microduck_rl (as scripts/sim.sh); policies from
scripts/fetch_policies.sh in data/policies/; scenes from scripts/install_scene.sh.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import math
import os
import re
import subprocess
import sys

import mujoco
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)                     # for `import copush`
RL = os.path.abspath(os.environ.get("DUCK_SIM_RL") or os.path.join(os.path.dirname(ROOT), "microduck_rl"))
SCENE_DIR = os.path.join(RL, "src/mjlab_microduck/robot/microduck")
POLICIES = os.path.join(ROOT, "data/policies")

POLICY = {
    "forward": os.path.join(POLICIES, "robert/shoe_push/forward/policy.onnx"),
    "backward": os.path.join(POLICIES, "robert/shoe_push/backward/policy.onnx"),
    "velstand v6": os.path.join(POLICIES, "velstand_v6/velstand.onnx"),
    "velstand v8": os.path.join(POLICIES, "velstand_v8/velstand.onnx"),
}

CONTROL_DT = 0.02          # 50 Hz policy
SIM_DT = 0.005             # infer_policy timestep
DECIMATION = 4
SPAWN_Z = 0.125            # infer_policy trunk spawn height
BOX_HALF_Z = 0.045
BOX_OFFSET = 0.20
BOX_NOMINAL_MASS = 0.15
FALL_TILT_DEG = 60.0
FALL_Z = 0.07
LOST_DIST = 0.40

BODY_GROUPS = [            # robot body name -> contact group
    (r"^ankle_", "feet"),
    (r"^leg", "thighs"),
    (r"^hip_", "hips"),
    (r"^trunk_base$", "trunk"),
    (r"^(jaw|head|bottom_head|neck)", "head"),
]


def scene(direction: str | None, robot: str = "backlash") -> str:
    """Path of an installed scene. direction None = the box-less floor for that robot."""
    if direction is None:
        name = "scene_backlash.xml" if robot == "backlash" else "scene.xml"
    else:
        name = f"scene_copush_b0_{direction}{'' if robot == 'backlash' else '_nobacklash'}.xml"
    path = os.path.join(SCENE_DIR, name)
    if not os.path.exists(path):
        subprocess.run(["sh", os.path.join(ROOT, "scripts/install_scene.sh")], check=True)
    return path


def check_policies():
    missing = [p for p in POLICY.values() if not os.path.exists(p)]
    if missing:
        sys.exit("missing policies (run scripts/fetch_policies.sh):\n  " + "\n  ".join(missing))


_IP = None


def infer_policy():
    """microduck_rl/scripts/infer_policy.py as a module (loaded once)."""
    global _IP
    if _IP is None:
        path = os.path.join(RL, "scripts", "infer_policy.py")
        spec = importlib.util.spec_from_file_location("infer_policy", path)
        _IP = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_IP)
    return _IP


def yaw_of(q):
    w, x, y, z = q
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def body_group(name):
    for pat, g in BODY_GROUPS:
        if re.match(pat, name or ""):
            return g
    return f"other:{name}"


class Rollout:
    """One (policy, scene) pair: model compiled once, data reset per trial."""

    def __init__(self, scene_xml, onnx_path, vin=7.4, vin_drop_gain=0.1):
        ip = self.ip = infer_policy()
        with contextlib.redirect_stdout(io.StringIO()):
            bam_model = ip.load_bam_model(ip.BAM_KP_FW, vin, None)
            self.m, self.d, self.bam, _ = ip.load_mujoco_with_bam(
                scene_xml, bam_model, SIM_DT, vin_drop_gain if vin_drop_gain > 0 else None, ip.BAM_VIN_MIN)
            self.pol = ip.PolicyInference(self.m, self.d, bam_ctrl=self.bam,
                                          walking_onnx_path=onnx_path, new_cmd_obs=True,
                                          use_projected_gravity=True)
        m = self.m
        jt = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "trunk_base_freejoint")
        self.t_q, self.t_v = int(m.jnt_qposadr[jt]), int(m.jnt_dofadr[jt])
        jb = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "box_free")
        self.has_box = jb >= 0
        if self.has_box:
            self.b_q, self.b_v = int(m.jnt_qposadr[jb]), int(m.jnt_dofadr[jb])
            self.box_body = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "box")
            self.box_geom = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "box_geom")
            self.inertia0 = m.body_inertia[self.box_body].copy()
            self.mass0 = float(m.body_mass[self.box_body])
        robot_root = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "trunk_base")
        self.robot_geom_group = {}
        for g in range(m.ngeom):
            b = int(m.geom_bodyid[g])
            if m.body_rootid[b] == robot_root:
                self.robot_geom_group[g] = body_group(mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, b))

    def reset(self, box_x, box_mass, box_yaw):
        m, d = self.m, self.d
        mujoco.mj_resetData(m, d)
        d.qpos[self.t_q:self.t_q + 7] = [0, 0, SPAWN_Z, 1, 0, 0, 0]
        for i, qi in enumerate(self.pol.joint_qpos_indices):
            d.qpos[qi] = self.pol.default_pose[i]
        if self.has_box:
            m.body_mass[self.box_body] = box_mass
            m.body_inertia[self.box_body] = self.inertia0 * (box_mass / self.mass0)
            h = 0.5 * box_yaw
            d.qpos[self.b_q:self.b_q + 7] = [box_x, 0.0, BOX_HALF_Z, math.cos(h), 0, 0, math.sin(h)]
            mujoco.mj_setConst(m, d)
        self.bam.reset(d.qpos)
        self.pol.last_action[:] = 0.0
        self.pol.set_position_targets(self.pol.default_pose)
        mujoco.mj_forward(m, d)

    def _set_cmd(self, cmd):
        with contextlib.redirect_stdout(io.StringIO()):
            self.pol.set_vel_cmd(*(float(c) for c in cmd))

    def state(self, t):
        """copush.state-shaped dict (duck_b absent: one duck)."""
        d = self.d
        q = d.qpos[self.t_q + 3:self.t_q + 7]
        st = {"t": t,
              "duck_a": {"position": (float(d.qpos[self.t_q]), float(d.qpos[self.t_q + 1])),
                         "yaw": yaw_of(q),
                         "velocity": (float(d.qvel[self.t_v]), float(d.qvel[self.t_v + 1]))},
              "box": None, "goal": None}
        if self.has_box:
            bq = d.qpos[self.b_q + 3:self.b_q + 7]
            st["box"] = {"position": (float(d.qpos[self.b_q]), float(d.qpos[self.b_q + 1])),
                         "yaw": yaw_of(bq),
                         "velocity": (float(d.qvel[self.b_v]), float(d.qvel[self.b_v + 1]))}
        return st

    def run(self, cmd, duration, push_sign=+1, box_x=0.0, box_mass=BOX_NOMINAL_MASS,
            box_yaw=math.pi / 2, trace=None, controller=None, ctrl_period=0.1, stop_when=None):
        """One trial.

        cmd:        (vx, vy, vyaw) held for the whole trial (a bare float means (vx, 0, 0)), or
        controller: a copush.state.Controller; get_actions(state)["duck_a"] is applied every
                    ctrl_period seconds (cmd is then only the command before its first call).
        stop_when:  optional callable(state) -> bool, checked every control step (e.g. "box went 1 m").
        trace:      optional list; one (t, trunk_x, trunk_y, box_x, box_y, heading_deg, cmd_vyaw) row
                    is appended per control step (box_x/box_y NaN on a box-less scene).
        """
        if not isinstance(cmd, (tuple, list)):
            cmd = (float(cmd), 0.0, 0.0)
        m, d, pol = self.m, self.d, self.pol
        self.reset(box_x, box_mass, box_yaw)
        if controller is not None:
            controller.reset()
        self._set_cmd(cmd)
        current = tuple(cmd)
        yaw0 = yaw_of(d.qpos[self.t_q + 3:self.t_q + 7])
        u = push_sign * np.array([math.cos(yaw0), math.sin(yaw0)])
        r0 = d.qpos[self.t_q:self.t_q + 2].copy()
        b0 = d.qpos[self.b_q:self.b_q + 2].copy() if self.has_box else None
        fell, fall_t, lost, stopped_t = False, None, False, None
        force = {}
        f6 = np.zeros(6)
        cos_fall = math.cos(math.radians(FALL_TILT_DEG))
        every = max(1, int(round(ctrl_period / CONTROL_DT)))
        n_ctrl = int(round(duration / CONTROL_DT))
        for k in range(n_ctrl):
            t = k * CONTROL_DT
            if controller is not None and k % every == 0:
                current = tuple(controller.get_actions(self.state(t))["duck_a"])
                self._set_cmd(current)
            pol.apply_action(pol.infer())
            for _ in range(DECIMATION):
                self.bam.update()
                mujoco.mj_step(m, d)
                if self.has_box:
                    for ci in range(d.ncon):
                        c = d.contact[ci]
                        g1, g2 = c.geom1, c.geom2
                        if g1 == self.box_geom and g2 in self.robot_geom_group:
                            grp = self.robot_geom_group[g2]
                        elif g2 == self.box_geom and g1 in self.robot_geom_group:
                            grp = self.robot_geom_group[g1]
                        else:
                            continue
                        mujoco.mj_contactForce(m, d, ci, f6)
                        force[grp] = force.get(grp, 0.0) + abs(f6[0]) * SIM_DT
            q = d.qpos[self.t_q + 3:self.t_q + 7]
            if trace is not None:
                bxy = d.qpos[self.b_q:self.b_q + 2] if self.has_box else (np.nan, np.nan)
                trace.append(((k + 1) * CONTROL_DT, float(d.qpos[self.t_q]), float(d.qpos[self.t_q + 1]),
                              float(bxy[0]), float(bxy[1]), math.degrees(wrap(yaw_of(q) - yaw0)), current[2]))
            up_z = 1 - 2 * (q[1] ** 2 + q[2] ** 2)     # world-z of trunk z-axis
            if up_z < cos_fall or d.qpos[self.t_q + 2] < FALL_Z:
                fell, fall_t = True, (k + 1) * CONTROL_DT
                break
            if self.has_box and not lost:
                if np.linalg.norm(d.qpos[self.b_q:self.b_q + 2] - d.qpos[self.t_q:self.t_q + 2]) > LOST_DIST:
                    lost = True
            if stop_when is not None and stop_when(self.state((k + 1) * CONTROL_DT)):
                stopped_t = (k + 1) * CONTROL_DT
                break
        r1 = d.qpos[self.t_q:self.t_q + 2]
        out = dict(
            robot_travel=float((r1 - r0) @ u),
            robot_dxy=[float(x) for x in (r1 - r0)],
            heading_deg=math.degrees(wrap(yaw_of(d.qpos[self.t_q + 3:self.t_q + 7]) - yaw0)),
            fell=fell, fall_t=fall_t, lost=lost, stopped_t=stopped_t, contact_impulse=force,
            box_mass=box_mass, box_yaw_deg=math.degrees(box_yaw - math.pi / 2),
        )
        if self.has_box:
            b1 = d.qpos[self.b_q:self.b_q + 2]
            out["box_travel"] = float((b1 - b0) @ u)
            out["box_lateral"] = float((b1 - b0) @ np.array([-u[1], u[0]]))
            out["box_dxy"] = [float(x) for x in (b1 - b0)]
            out["box_yaw_change_deg"] = math.degrees(wrap(yaw_of(d.qpos[self.b_q + 3:self.b_q + 7]) - box_yaw))
        return out


def paired_boxes(trials, seed=0, mass_range=(0.05, 0.30), yaw_range_deg=45.0, fixed=False):
    """(mass, yaw) per trial; trial i uses seed+i, so every condition sees the same boxes."""
    out = []
    yr = math.radians(yaw_range_deg)
    for i in range(trials):
        rng = np.random.default_rng(seed + i)
        if fixed:
            out.append((BOX_NOMINAL_MASS, math.pi / 2))
        else:
            out.append((float(rng.uniform(*mass_range)), math.pi / 2 + float(rng.uniform(-yr, yr))))
    return out
