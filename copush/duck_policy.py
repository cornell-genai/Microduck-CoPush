"""One duck's ONNX walking policy in a multi-duck MuJoCo model.

infer_policy.PolicyInference is single-robot: it looks up unprefixed `trunk_base` / `imu_ang_vel`,
takes n_joints = model.nu and writes all of ctrl. DuckPolicy is the same observation -> action
loop for the duck whose names start with `prefix` (e.g. "a_"), writing only that duck's BAM
targets. The 61-D observation, in infer_policy's order (`use_projected_gravity=True`,
`new_cmd_obs=True`):

    gyro imu_ang_vel (3) | projected gravity (3) | joint pos - DEFAULT_POSE (14)
    | joint vel (14) | last action (14) | command [vx, vy, vyaw, 0 x 10] (13)

Action (14) -> joint targets DEFAULT_POSE + action (action_scale 1). The caller runs `step()` once
per control step (every DECIMATION physics steps); BAM turns targets into torques at physics rate.

Policies are switched live with `set_policy(name)`; the last action carries over, since it is what
the joints were actually last told.
"""
from __future__ import annotations

from typing import Dict

import mujoco
import numpy as np
import onnxruntime as ort

from copush.upstream import infer_policy

_IP = infer_policy()
DEFAULT_POSE = _IP.DEFAULT_POSE
N_JOINTS = len(DEFAULT_POSE)
N_CMD = 13
OBS_DIM = 3 + 3 + 3 * N_JOINTS + N_CMD          # 61
_GRAVITY = np.array([0.0, 0.0, -1.0], dtype=np.float32)


def load_sessions(paths: Dict[str, str]) -> Dict[str, ort.InferenceSession]:
    """name -> InferenceSession. One session can be shared by every duck (run() is stateless)."""
    out = {}
    for name, path in paths.items():
        s = ort.InferenceSession(path)
        if list(s.get_inputs()[0].shape)[-1] != OBS_DIM or list(s.get_outputs()[0].shape)[-1] != N_JOINTS:
            raise ValueError(f"{path}: expected obs[{OBS_DIM}] -> actions[{N_JOINTS}]")
        out[name] = s
    return out


class DuckPolicy:
    def __init__(self, model: mujoco.MjModel, data: mujoco.MjData, prefix: str, bam_ctrl,
                 sessions: Dict[str, ort.InferenceSession], policy: str = "velstand"):
        self.m, self.d, self.prefix, self.bam = model, data, prefix, bam_ctrl
        self.sessions = sessions
        self.actuators = [i for i in range(model.nu) if model.actuator(i).name.startswith(prefix)]
        if len(self.actuators) != N_JOINTS:
            raise ValueError(f"{prefix!r}: {len(self.actuators)} actuators, expected {N_JOINTS}")
        # same index rule as PolicyInference (actuator -> joint -> qpos/dof address)
        self.qpos_idx = [int(model.jnt_qposadr[model.actuator_trnid[i, 0]]) for i in self.actuators]
        self.qvel_idx = [int(model.jnt_dofadr[model.actuator_trnid[i, 0]]) for i in self.actuators]
        self.trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, prefix + "trunk_base")
        gyro = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, prefix + "imu_ang_vel")
        if self.trunk_id < 0 or gyro < 0:
            raise ValueError(f"{prefix!r}: trunk_base / imu_ang_vel not found")
        self.gyro_adr = int(model.sensor_adr[gyro])
        self.default_pose = DEFAULT_POSE
        self.last_action = np.zeros(N_JOINTS, dtype=np.float32)
        self.command = np.zeros(N_CMD, dtype=np.float32)
        self.set_policy(policy)

    # ── commands ────────────────────────────────────────────────────────────
    def set_policy(self, name: str) -> None:
        if name not in self.sessions:
            raise KeyError(f"unknown policy {name!r} (have {sorted(self.sessions)})")
        self.policy = name
        s = self.sessions[name]
        self._session, self._in, self._out = s, s.get_inputs()[0].name, s.get_outputs()[0].name

    def set_cmd(self, vx: float, vy: float, vyaw: float) -> None:
        self.command[:] = 0.0
        self.command[0:3] = (vx, vy, vyaw)

    @property
    def cmd(self):
        return tuple(float(c) for c in self.command[0:3])

    def reset(self) -> None:
        """Call after the duck's qpos is set (and bam_ctrl.reset): zero memory, hold DEFAULT_POSE."""
        self.last_action[:] = 0.0
        self.command[:] = 0.0
        self.bam.q_target[:] = self.default_pose

    # ── observation -> action ───────────────────────────────────────────────
    def projected_gravity(self) -> np.ndarray:
        quat = self.d.xquat[self.trunk_id].copy().astype(np.float32)
        # PolicyInference.quat_rotate_inverse does not use `self`; call it so the math is upstream's
        return _IP.PolicyInference.quat_rotate_inverse(None, quat, _GRAVITY)

    def observation(self) -> np.ndarray:
        d = self.d
        obs = [
            d.sensordata[self.gyro_adr:self.gyro_adr + 3].copy().astype(np.float32),
            self.projected_gravity(),
            d.qpos[self.qpos_idx].copy().astype(np.float32) - self.default_pose,
            d.qvel[self.qvel_idx].copy().astype(np.float32),
            self.last_action,
            self.command,
        ]
        return np.concatenate(obs).astype(np.float32)

    def step(self) -> np.ndarray:
        """Infer once and set this duck's joint targets. Returns the action."""
        obs = self.observation().reshape(1, -1)
        action = self._session.run([self._out], {self._in: obs})[0].squeeze(0).astype(np.float32)
        self.last_action = action.copy()
        self.bam.q_target[:] = self.default_pose + action
        return action
