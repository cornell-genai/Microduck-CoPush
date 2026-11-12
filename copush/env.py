"""Gymnasium environment for the high-level CoPush coordinator (RL plan steps 1 and 3).

The learner sets each duck's forward speed and turn rate every 0.2 s; the frozen ONNX policies
(velstand, Shoe Push) still decide the joints at 50 Hz. Run with the RL overlay:

    scripts/rl.sh -c "from copush.env import CoPushEnv; ..."      # or scripts/rl.sh my_script.py

    env = CoPushEnv()                      # configs/copush.yaml: fixed start, reward v1
    obs, info = env.reset(seed=0)
    obs, reward, terminated, truncated, info = env.step(env.action_space.sample())

Action (4, in [-1, 1]): [A vx, A vyaw, B vx, B vyaw] -> vx = 0.15 (a + 1) in [0, 0.3] m/s,
vyaw = 1.5 a in [-1.5, 1.5] rad/s. Action 0 is therefore vx 0.15 (a slow walk), not standing.

Observation (21, OBS_NAMES), all in the TARGET's frame (x along the target's yaw):
    box position - target (2), box yaw error as sin/cos of 2x (2; the box is 180-degree
    symmetric), box velocity (2), box yaw rate (1),
    per duck: position - box (2), heading sin/cos (2), touching box (1), on Shoe Push (1),
    forward speed (1)

Policy switching is automatic: velstand until the duck touches the box, Shoe Push from then on,
back to velstand after env.lose_contact_s without contact (Shoe Push falls without a box).

Episodes: env.max_steps steps (100 = 20 s), ended early by TaskReward (success, fall, box
tipped/lost). env.layout picks a start mode and target from `layouts`:
    close (default): start_mode in_contact, target 0.40 m straight ahead of the box. Both ducks
        are placed against the box's long face (the side away from the target), contact_spacing
        apart, stand for settle_s on velstand, then switch to Shoe Push; the episode clock starts
        after that.
    hard: start_mode approach, the original scene (walk 0.35 m to the box, target 0.85 m away).
Fixed box by default; env.randomize samples it from env.random using the env's np_random. Seeds in
env.heldout_seeds are refused with split="train" (keep them for eval). env.curriculum (off) moves
the target with set_curriculum_level(k), driven by copush.rl_callbacks.CurriculumCallback.

Reward: TaskReward(effective_reward(cfg)), i.e. reward.version from reward_versions. A fall counts
once a duck has been down fall_min_down_s without a break (v1: immediately).

Logging (log_dir set): env_steps.csv, one row per env step with every reward term, per-duck
contact time / push force / contact force, the balance b and the termination reason; events.log
with RewardMonitor flags, policy switches and falls.
"""
from __future__ import annotations

import copy
import csv
import math
import os
from typing import Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from copush.config import effective_reward, load_config
from copush.rewards import TERMS, RewardMonitor, StepSummary, TaskReward, balance
from copush.sim import CONTROL_DT, DUCKS, CoPushSim
from copush.state import wrap_angle

VX_MAX, VYAW_MAX = 0.3, 1.5
OBS_NAMES = (["box_x", "box_y", "box_sin2e", "box_cos2e", "box_vx", "box_vy", "box_yaw_rate"]
             + [f"{d}_{n}" for d in ("a", "b")
                for n in ("dx", "dy", "sin_h", "cos_h", "contact", "shoepush", "speed")])
LOG_COLUMNS = (["episode", "step", "t", "a_vx", "a_vyaw", "b_vx", "b_vyaw"]
               + [f"r_{k}" for k in TERMS] + ["reward", "return", "box_to_target", "yaw_error_deg",
                                              "inside", "box_tilt_deg", "b"]
               + [f"{d}_{n}" for d in ("a", "b")
                  for n in ("policy", "contact_time", "push_force", "contact_force", "fallen", "down")]
               + ["reason", "flags"])


def action_to_cmd(a) -> dict:
    a = np.clip(np.asarray(a, dtype=np.float64), -1.0, 1.0)
    return {"A": (0.5 * VX_MAX * (a[0] + 1), 0.0, VYAW_MAX * a[1]),
            "B": (0.5 * VX_MAX * (a[2] + 1), 0.0, VYAW_MAX * a[3])}


def cmd_to_action(vx_a, vyaw_a, vx_b, vyaw_b) -> np.ndarray:
    return np.array([vx_a / (0.5 * VX_MAX) - 1, vyaw_a / VYAW_MAX,
                     vx_b / (0.5 * VX_MAX) - 1, vyaw_b / VYAW_MAX], dtype=np.float32)


class CoPushEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, cfg: Optional[dict] = None, log_dir: Optional[str] = None, split: str = "train"):
        super().__init__()
        self.cfg = copy.deepcopy(cfg if cfg is not None else load_config())
        self.ecfg = self.cfg["env"]
        self.layout = self.cfg["layouts"][self.ecfg["layout"]]
        self.cfg["target"].update(self.layout["target"])
        self.start_mode = self.layout["start_mode"]
        if self.start_mode not in ("in_contact", "approach"):
            raise ValueError(f"start_mode must be in_contact or approach, got {self.start_mode!r}")
        self.rcfg = effective_reward(self.cfg)
        self.task = TaskReward(self.rcfg)
        self.sim = CoPushSim(self.cfg)                       # shares self.cfg (randomize edits its box)
        self.box0 = dict(self.cfg["box"])
        self.target0 = dict(self.cfg["target"])
        self.curriculum_level = 0
        if self.ecfg["curriculum"]["enabled"]:
            self.set_curriculum_level(0)
        self.n_ctrl = max(1, int(round(self.ecfg["step_s"] / CONTROL_DT)))
        self.dt = self.n_ctrl * CONTROL_DT
        self.split = split
        self.heldout = tuple(self.ecfg["heldout_seeds"])
        self.action_space = spaces.Box(-1.0, 1.0, shape=(4,), dtype=np.float32)
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(len(OBS_NAMES),), dtype=np.float32)
        self.monitor = RewardMonitor()
        self.episode = 0
        self.log_dir = log_dir
        self._csv = self._events = None
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            self._csv_file = open(os.path.join(log_dir, "env_steps.csv"), "w", newline="")
            self._csv = csv.DictWriter(self._csv_file, fieldnames=LOG_COLUMNS)
            self._csv.writeheader()
            self._events = open(os.path.join(log_dir, "events.log"), "w")
        self.state = None
        self.frame_hook = None          # callable(state, return_so_far) after every control step (videos)

    # ── episode ─────────────────────────────────────────────────────────────
    def set_curriculum_level(self, level: int) -> int:
        """Target = box start + distances[level] along +x, offsets[level] sideways (clamped)."""
        cur = self.ecfg["curriculum"]
        level = max(0, min(int(level), len(cur["distances"]) - 1))
        self.curriculum_level = level
        self.cfg["target"]["x"] = self.box0["x"] + cur["distances"][level]
        self.cfg["target"]["y"] = self.box0["y"] + cur["offsets"][level]
        return level

    def _place_in_contact(self) -> None:
        """Both ducks against the box's long face on the side away from the target, facing it."""
        box, tg, e = self.cfg["box"], self.cfg["target"], self.ecfg
        b = math.radians(box["yaw"])
        t = (math.cos(b), math.sin(b))                     # long (28 cm) axis
        n = (-math.sin(b), math.cos(b))                    # long-face normal
        side = 1.0 if (tg["x"] - box["x"]) * n[0] + (tg["y"] - box["y"]) * n[1] >= 0 else -1.0
        face = (side * n[0], side * n[1])                  # push direction
        yaw = math.degrees(math.atan2(face[1], face[0]))
        cx, cy = box["x"] - face[0] * e["contact_setback"], box["y"] - face[1] * e["contact_setback"]
        half = e["contact_spacing"] / 2
        # duck A on the left of the push direction, as in the approach layout
        left = (-face[1], face[0])
        sgn = 1.0 if left[0] * t[0] + left[1] * t[1] >= 0 else -1.0
        for duck, k in (("duck_a", +1), ("duck_b", -1)):
            self.cfg[duck].update({"x": cx + k * sgn * half * t[0], "y": cy + k * sgn * half * t[1], "yaw": yaw})

    def is_heldout(self, seed: int) -> bool:
        return self.heldout[0] <= seed <= self.heldout[1]

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        if seed is not None and self.split == "train" and self.is_heldout(seed):
            raise ValueError(f"seed {seed} is held out for evaluation (env.heldout_seeds); use split='eval'")
        super().reset(seed=seed)
        box = self.cfg["box"]
        if self.ecfg["randomize"]:
            r = self.ecfg["random"]
            box["x"] = float(self.np_random.uniform(*r["box_x"]))
            box["y"] = float(self.np_random.uniform(*r["box_y"]))
            box["yaw"] = float(self.np_random.uniform(*r["box_yaw"]))
            self.sim.set_box_mass(float(self.np_random.uniform(*r["box_mass"])))
        else:
            box.update({k: self.box0[k] for k in ("x", "y", "yaw")})
            self.sim.set_box_mass(self.box0["mass"])
        if self.start_mode == "in_contact":
            self._place_in_contact()
            self.sim.reset()
            self.sim.step({"A": (0, 0, 0), "B": (0, 0, 0)}, duration=self.ecfg["settle_s"])
            for d in DUCKS:
                self.sim.set_policy(d, "shoepush")
            st = self.sim.mark_start()
        else:
            st = self.sim.reset()
        self.state = st
        self.sim.pop_events()
        self.monitor.reset()
        self.episode += 1
        self.steps, self.ret = 0, 0.0
        self.no_contact = {d: 0.0 for d in DUCKS}
        self.success_held = 0.0
        self.was_down = {d: False for d in DUCKS}
        self.down_run = {d: 0.0 for d in DUCKS}
        self.fell = {d: False for d in DUCKS}             # counted falls (fall_min_down_s)
        self.stats = {"terms": {k: 0.0 for k in TERMS}, "push": {d: 0.0 for d in DUCKS},
                      "contact_time": {d: 0.0 for d in DUCKS}, "stood_up": {d: 0 for d in DUCKS},
                      "cmd_vx": {d: 0.0 for d in DUCKS},
                      "min_dist": st["box_to_target"], "start_dist": st["box_to_target"], "flags": []}
        self._event(0.0, "reset", f"episode {self.episode} box=({box['x']:.3f},{box['y']:.3f},"
                                  f"{box['yaw']:.1f}deg,{box['mass']:.3f}kg) seed={seed}")
        return self._obs(st), {"box": dict(box), "target": dict(self.cfg["target"])}

    def _auto_switch(self, st: dict) -> None:
        for d in DUCKS:
            c = st["contact"][d]["in_contact"]
            self.no_contact[d] = 0.0 if c else self.no_contact[d] + CONTROL_DT
            pol = st[d]["policy"]
            if pol == "velstand" and c:
                self.sim.set_policy(d, "shoepush")
            elif pol == "shoepush" and self.no_contact[d] >= self.ecfg["lose_contact_s"] - 1e-9:
                self.sim.set_policy(d, "velstand")

    def step(self, action):
        st0 = self.state
        cmds = action_to_cmd(action)
        push = {d: 0.0 for d in DUCKS}
        force = {d: 0.0 for d in DUCKS}
        ctime = {d: 0.0 for d in DUCKS}
        down_s, flags = 0.0, []
        rc = self.rcfg
        newly_fell = False
        tol = math.radians(rc["success_yaw_deg"])
        for k in range(self.n_ctrl):
            st = self.sim.step(cmds if k == 0 else None)
            self._auto_switch(st)
            if self.frame_hook is not None:
                self.frame_hook(st, self.ret)
            any_down = False
            for d in DUCKS:
                c = st["contact"][d]
                push[d] += c["push_force"] / self.n_ctrl
                force[d] += c["force"] / self.n_ctrl
                ctime[d] += CONTROL_DT if c["in_contact"] else 0.0
                down = st[d]["down"]
                self.down_run[d] = self.down_run[d] + CONTROL_DT if down else 0.0
                if not self.fell[d] and down and self.down_run[d] >= rc["fall_min_down_s"] - 1e-9:
                    self.fell[d] = newly_fell = True
                    self._event(st["t"], "fall", f"{d} counted as fallen (down {self.down_run[d]:.2f} s)")
                if self.was_down[d] and not down:
                    self.stats["stood_up"][d] += 1
                self.was_down[d] = down
                any_down |= down
            down_s += CONTROL_DT if any_down else 0.0
            ok = st["inside"] and st["yaw_error"] <= tol and not any_down
            self.success_held = self.success_held + CONTROL_DT if ok else 0.0
            if k < self.n_ctrl - 1:
                flags += self.monitor.update(st, reward=0.0)[1]
        box_xy = st["box"]["position"]
        lost = all(math.dist(box_xy, st[d]["position"]) > rc["box_lost_dist"] for d in DUCKS)
        summary = StepSummary(dist_before=st0["box_to_target"], dist_after=st["box_to_target"],
                              yaw_before=st0["yaw_error"], yaw_after=st["yaw_error"],
                              success_held_s=self.success_held,
                              fell=newly_fell, down_s=down_s, box_tilt_deg=st["box"]["tilt_deg"], box_lost=lost,
                              inside=st["inside"], off_box_s=dict(self.no_contact), push=push)
        terms, terminated, reason = self.task.step(summary)
        reward = float(sum(terms.values()))
        flags += self.monitor.update(st, reward=reward)[1]
        self.steps += 1
        self.ret += reward
        truncated = not terminated and self.steps >= self.ecfg["max_steps"]
        if truncated:
            reason = "timeout"
        self.state = st
        b = balance(push["duck_a"], push["duck_b"])

        s = self.stats
        for k_, v in terms.items():
            s["terms"][k_] += v
        for d, L in (("duck_a", "A"), ("duck_b", "B")):
            s["push"][d] += push[d] * self.dt
            s["contact_time"][d] += ctime[d]
            s["cmd_vx"][d] += cmds[L][0]
        s["min_dist"] = min(s["min_dist"], st["box_to_target"])
        s["flags"] += flags
        info = {"terms": terms, "b": b, "push_force": push, "contact_force": force,
                "contact_time": ctime, "reason": reason, "flags": flags,
                "box_to_target": st["box_to_target"], "yaw_error": st["yaw_error"], "inside": st["inside"]}
        for t, kind, msg in self.sim.pop_events():
            self._event(t, kind, msg)
        for f in flags:
            self._event(st["t"], "SUSPECT", f)
        if reason:
            self._event(st["t"], "end", f"{reason} after {self.steps} steps, return {self.ret:+.3f}")
        if terminated or truncated:
            tot_push = sum(s["push"].values())
            info["episode_stats"] = {
                "return": self.ret, "terms": dict(s["terms"]), "reason": reason, "steps": self.steps,
                "fell": dict(self.fell), "stood_up": dict(s["stood_up"]),
                "reward_version": self.rcfg["version"], "layout": self.ecfg["layout"],
                "push_share": {d: (s["push"][d] / tot_push if tot_push > 0 else float("nan")) for d in DUCKS},
                "contact_time": dict(s["contact_time"]), "start_dist": s["start_dist"],
                "cmd_vx_mean": {d: s["cmd_vx"][d] / self.steps for d in DUCKS},
                "final_dist": st["box_to_target"], "min_dist": s["min_dist"],
                "final_yaw_deg": math.degrees(st["yaw_error"]), "flags": list(s["flags"])}
        self._log_row(action, terms, reward, st, b, push, force, ctime, reason, flags)
        return self._obs(st), reward, terminated, truncated, info

    # ── observation ─────────────────────────────────────────────────────────
    def _obs(self, st: dict) -> np.ndarray:
        g = st["goal"]
        gx, gy = g["position"]
        c, s = math.cos(g["yaw"]), math.sin(g["yaw"])

        def tf(x, y):                                  # world vector -> target frame
            return c * x + s * y, -s * x + c * y

        bx, by = st["box"]["position"]
        e = wrap_angle(st["box"]["yaw"] - g["yaw"])
        o = [*tf(bx - gx, by - gy), math.sin(2 * e), math.cos(2 * e),
             *tf(*st["box"]["velocity"]), st["box"]["yaw_rate"]]
        for d in DUCKS:
            x, y = st[d]["position"]
            h = st[d]["yaw"] - g["yaw"]
            vx, vy = st[d]["velocity"]
            o += [*tf(x - bx, y - by), math.sin(h), math.cos(h),
                  float(st["contact"][d]["in_contact"]), float(st[d]["policy"] == "shoepush"),
                  vx * math.cos(st[d]["yaw"]) + vy * math.sin(st[d]["yaw"])]
        return np.asarray(o, dtype=np.float32)

    # ── logging ─────────────────────────────────────────────────────────────
    def _event(self, t: float, kind: str, msg: str) -> None:
        if self._events:
            self._events.write(f"ep={self.episode} t={t:7.2f}  {kind:<8} {msg}\n")

    def _log_row(self, action, terms, reward, st, b, push, force, ctime, reason, flags) -> None:
        if not self._csv:
            return
        cm = action_to_cmd(action)
        row = {"episode": self.episode, "step": self.steps, "t": f"{st['t']:.2f}",
               "a_vx": f"{cm['A'][0]:.3f}", "a_vyaw": f"{cm['A'][2]:.3f}",
               "b_vx": f"{cm['B'][0]:.3f}", "b_vyaw": f"{cm['B'][2]:.3f}",
               **{f"r_{k}": f"{v:.5f}" for k, v in terms.items()},
               "reward": f"{reward:.5f}", "return": f"{self.ret:.5f}",
               "box_to_target": f"{st['box_to_target']:.5f}", "yaw_error_deg": f"{math.degrees(st['yaw_error']):.3f}",
               "inside": int(st["inside"]), "box_tilt_deg": f"{st['box']['tilt_deg']:.3f}", "b": f"{b:.4f}",
               "reason": reason or "", "flags": " | ".join(flags)}
        for d, p in (("duck_a", "a"), ("duck_b", "b")):
            row.update({f"{p}_policy": st[d]["policy"], f"{p}_contact_time": f"{ctime[d]:.2f}",
                        f"{p}_push_force": f"{push[d]:.5f}", f"{p}_contact_force": f"{force[d]:.5f}",
                        f"{p}_fallen": int(st[d]["fallen"]), f"{p}_down": int(st[d]["down"])})
        self._csv.writerow(row)

    def close(self) -> None:
        if self._csv:
            self._csv_file.close()
            self._events.close()
            self._csv = self._events = None


def make_env(cfg: Optional[dict] = None, log_dir: Optional[str] = None, split: str = "train"):
    """Factory for vectorized envs (stable_baselines3 SubprocVecEnv, gymnasium vector)."""
    def _thunk():
        return CoPushEnv(cfg, log_dir=log_dir, split=split)
    return _thunk


# ── baseline controllers (obs -> action), for checks and videos ──────────────

VELSTAND_TURN_MIN = 0.5    # rad/s: velstand does not turn in place below this on this harness


class PushSteer:
    """Scripted baseline: per-duck heading hold toward the target, stop while the box is inside.

    Each duck runs copush.controllers.HeadingHoldPush (PI on heading with an integrated bias, so it
    finds Shoe Push's left drift and low steering gain by itself; reference bent toward the
    box->target line by the box's cross-track error) along the line from the box's start to the
    target, once per env step (5 Hz). A turn command below VELSTAND_TURN_MIN on a duck that is on
    velstand is raised to it (dead zone). While the box centre is inside the target both ducks get
    (0, 0, 0) and the integrators are frozen; they resume if the box drifts out.
    """

    def __init__(self, env: CoPushEnv, vx: float = 0.2):
        self.env, self.vx = env, vx
        self.episode = None

    def _reset(self):
        from copush.controllers import HeadingHoldPush
        st = self.env.state
        bx, by = st["box"]["position"]
        gx, gy = st["goal"]["position"]
        line = math.atan2(gy - by, gx - bx)
        self.ctl = {d: HeadingHoldPush(vx=self.vx, duck=d, line_yaw=line, line_origin=(bx, by)) for d in DUCKS}
        self.episode = self.env.episode

    def __call__(self, obs):
        if self.episode != self.env.episode:
            self._reset()
        st = self.env.state
        if st["inside"]:
            return cmd_to_action(0.0, 0.0, 0.0, 0.0)
        cmd = []
        for d in DUCKS:
            vx, _, vyaw = self.ctl[d].get_actions(st)[d]
            if st[d]["policy"] == "velstand" and 0.0 < abs(vyaw) < VELSTAND_TURN_MIN:
                vyaw = math.copysign(VELSTAND_TURN_MIN, vyaw)
            cmd += [vx, vyaw]
        return cmd_to_action(*cmd)


def baseline(name: str, env: CoPushEnv, seed: int = 0):
    """random: uniform actions (own seeded RNG) · zero: action 0 = vx 0.15, no turning ·
    stand: vx 0 · push_forward: vx 0.2, no turning (scripts/copush_sim.py --script push_forward) ·
    push_steer: PushSteer (heading hold toward the target, stop inside)."""
    if name == "random":
        rng = np.random.default_rng(seed)
        return lambda obs: rng.uniform(-1.0, 1.0, size=4).astype(np.float32)
    if name == "push_steer":
        return PushSteer(env)
    fixed = {"zero": np.zeros(4, dtype=np.float32),
             "stand": cmd_to_action(0.0, 0.0, 0.0, 0.0),
             "push_forward": cmd_to_action(0.2, 0.0, 0.2, 0.0)}
    if name not in fixed:
        raise KeyError(f"unknown baseline {name!r}")
    a = fixed[name]
    return lambda obs: a


BASELINES = ("random", "zero", "stand", "push_forward", "push_steer")
