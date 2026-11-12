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

set_hold(duck, True) keeps a duck on velstand even while it touches the box (scripted baselines use
it to stand still: Shoe Push keeps nudging the box at zero command); the action space has no such
switch unless env.stand_still.enabled (OFF by default): then a duck whose commanded forward speed
is below env.stand_still.vx_threshold is held on velstand at zero speed (no turning) for that
step, and released as soon as its command is above it again. Every policy switch opens a SWITCH_WINDOW_S window in `switch_log`: lowest trunk z, worst
tilt, whether a fall was counted, how far the box moved.

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
SWITCH_WINDOW_S = 1.0
STUMBLE_TILT_DEG, STUMBLE_Z = 26.0, 0.095     # copush.metrics upright thresholds (gravity_z -0.90)
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
        self.hold = {d: False for d in DUCKS}
        self.stand_still = self.ecfg["stand_still"]
        self.switch_log = []            # one dict per policy switch, across episodes
        self._open_switches = []
        self._last_pol = {}

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
        self._close_switches(only_done=False)             # windows cut short by the reset
        self.hold = {d: False for d in DUCKS}
        self._last_pol = {d: self.sim.pol[d].policy for d in DUCKS}
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

    def set_hold(self, duck: str, on: bool) -> None:
        """on: keep `duck` on velstand (switching now if needed); off: automatic switching again."""
        self.hold[duck] = bool(on)
        if on and self.sim.pol[duck].policy != "velstand":
            self.sim.set_policy(duck, "velstand")

    def _track_switches(self, st: dict) -> None:
        """Open a window for every policy change since the last call; update and close windows."""
        for d in DUCKS:
            pol = self.sim.pol[d].policy
            if self._last_pol.get(d, pol) != pol:
                self._open_switches.append({"episode": self.episode, "t": st["t"], "duck": d,
                                            "from": self._last_pol[d], "to": pol, "box0": st["box"]["position"],
                                            "min_z": st[d]["trunk_z"], "max_tilt": st[d]["tilt_deg"],
                                            "fell": False, "left": round(SWITCH_WINDOW_S / CONTROL_DT),
                                            "box_moved": 0.0})
            self._last_pol[d] = pol
        for w in self._open_switches:
            d = w["duck"]
            w["min_z"] = min(w["min_z"], st[d]["trunk_z"])
            w["max_tilt"] = max(w["max_tilt"], st[d]["tilt_deg"])
            w["fell"] |= self.fell[d]
            w["box_moved"] = math.dist(w["box0"], st["box"]["position"])
            w["left"] -= 1
        self._close_switches(only_done=True)

    def _close_switches(self, only_done: bool) -> None:
        keep = []
        for w in self._open_switches:
            if only_done and w["left"] > 0:
                keep.append(w)
                continue
            w = {k: v for k, v in w.items() if k not in ("left", "box0")}
            w["stumble"] = w["max_tilt"] > STUMBLE_TILT_DEG or w["min_z"] < STUMBLE_Z
            self.switch_log.append(w)
        self._open_switches = keep

    def _auto_switch(self, st: dict) -> None:
        for d in DUCKS:
            c = st["contact"][d]["in_contact"]
            self.no_contact[d] = 0.0 if c else self.no_contact[d] + CONTROL_DT
            pol = st[d]["policy"]
            if self.hold[d]:
                if pol != "velstand":
                    self.sim.set_policy(d, "velstand")
            elif pol == "velstand" and c:
                self.sim.set_policy(d, "shoepush")
            elif pol == "shoepush" and self.no_contact[d] >= self.ecfg["lose_contact_s"] - 1e-9:
                self.sim.set_policy(d, "velstand")

    def step(self, action):
        st0 = self.state
        cmds = action_to_cmd(action)
        if self.stand_still["enabled"]:                  # commanded vx below the threshold = stand on velstand
            for d, L in (("duck_a", "A"), ("duck_b", "B")):
                still = cmds[L][0] < self.stand_still["vx_threshold"]
                if still:
                    cmds[L] = (0.0, 0.0, 0.0)
                if still != self.hold[d]:
                    self.set_hold(d, still)
        push = {d: 0.0 for d in DUCKS}
        force = {d: 0.0 for d in DUCKS}
        ctime = {d: 0.0 for d in DUCKS}
        down_s, flags = 0.0, []
        rc = self.rcfg
        newly_fell = False
        tol = math.radians(rc["success_yaw_deg"])
        self._track_switches(st0)                        # e.g. set_hold() between steps
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
            self._track_switches(st)
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
    """Scripted baseline: per-duck heading hold toward the target; square the box up; stand still.

    Pushing (box outside the target): each duck runs copush.controllers.HeadingHoldPush (PI on
    heading with an integrated bias, which finds Shoe Push's left drift and low steering gain by
    itself; reference bent toward the box->target line by the box's cross-track error) along the
    line from the box's start to the target, once per env step (5 Hz). A turn command below
    VELSTAND_TURN_MIN on a duck that is on velstand is raised to it (dead zone).
    Inside but crooked (yaw error > the success tolerance): only the duck on the side that must
    advance pushes, at CORRECT_VX, the other stays at vx 0, no turning: the box pivots.
    Inside and square: both ducks are held on velstand at zero speed (env.set_hold), since Shoe
    Push keeps nudging the box at zero command; the success timer then runs out. If the box
    drifts out (or goes crooked) the holds are released and automatic switching puts the ducks
    back on Shoe Push as soon as they touch the box.
    """

    CORRECT_VX = 0.15

    def __init__(self, env: CoPushEnv, vx: float = 0.2, diff: float = 0.0):
        """diff > 0 adds differential speed while pushing: the duck on the outside of the needed
        turn goes faster, vx * (1 + diff * e), the inside one slower, e = bearing error / 0.5 rad
        clipped to [-1, 1] (bearing error: direction box->target minus the ducks' mean heading)."""
        self.env, self.vx, self.diff = env, vx, diff
        self.episode = None
        self.mode = "push"

    def _reset(self):
        from copush.controllers import HeadingHoldPush
        st = self.env.state
        bx, by = st["box"]["position"]
        gx, gy = st["goal"]["position"]
        self.line = math.atan2(gy - by, gx - bx)
        self.ctl = {d: HeadingHoldPush(vx=self.vx, duck=d, line_yaw=self.line, line_origin=(bx, by)) for d in DUCKS}
        self.episode = self.env.episode
        self.mode = "push"

    def _release(self):
        for d in DUCKS:
            if self.env.hold[d]:
                self.env.set_hold(d, False)

    def __call__(self, obs):
        env = self.env
        if self.episode != env.episode:
            self._reset()
        st = env.state
        tol = math.radians(env.rcfg["success_yaw_deg"])
        if st["inside"] and st["yaw_error"] <= tol:
            self.mode = "hold"
            for d in DUCKS:
                env.set_hold(d, True)
            return cmd_to_action(0.0, 0.0, 0.0, 0.0)
        self._release()
        if st["inside"]:
            self.mode = "square"
            # signed box yaw error, folded to (-90, 90] deg: > 0 means turned counter-clockwise
            e = wrap_angle(st["box"]["yaw"] - st["goal"]["yaw"])
            e = (e + math.pi / 2) % math.pi - math.pi / 2
            bx, by = st["box"]["position"]
            c, s_ = math.cos(self.line), math.sin(self.line)
            left = max(DUCKS, key=lambda d: -s_ * (st[d]["position"][0] - bx) + c * (st[d]["position"][1] - by))
            right = "duck_b" if left == "duck_a" else "duck_a"
            pusher = left if e > 0 else right                # advancing the left end turns it clockwise
            v = {d: (self.CORRECT_VX if d == pusher else 0.0) for d in DUCKS}
            return cmd_to_action(v["duck_a"], 0.0, v["duck_b"], 0.0)
        self.mode = "push"
        scale = {d: 1.0 for d in DUCKS}
        if self.diff:
            bx, by = st["box"]["position"]
            gx, gy = st["goal"]["position"]
            hdg = math.atan2(sum(math.sin(st[d]["yaw"]) for d in DUCKS), sum(math.cos(st[d]["yaw"]) for d in DUCKS))
            e = max(-1.0, min(1.0, wrap_angle(math.atan2(gy - by, gx - bx) - hdg) / 0.5))
            c, s_ = math.cos(hdg), math.sin(hdg)
            left = max(DUCKS, key=lambda d: -s_ * (st[d]["position"][0] - bx) + c * (st[d]["position"][1] - by))
            for d in DUCKS:                                  # turn left (e > 0): right duck faster
                scale[d] = max(0.0, 1.0 + self.diff * e * (-1.0 if d == left else 1.0))
        cmd = []
        for d in DUCKS:
            vx, _, vyaw = self.ctl[d].get_actions(st)[d]
            if st[d]["policy"] == "velstand" and 0.0 < abs(vyaw) < VELSTAND_TURN_MIN:
                vyaw = math.copysign(VELSTAND_TURN_MIN, vyaw)
            cmd += [min(VX_MAX, vx * scale[d]), vyaw]
        return cmd_to_action(*cmd)


class PivotThenPush(PushSteer):
    """Scripted baseline: pivot the box toward the target with one duck, then both push (PushSteer).

    pivot    (the box's push direction is more than ALIGN_TOL off the box->target bearing) the
             duck on the inside of the turn is held on velstand at zero speed (env.set_hold) and
             the other pushes alone at pivot_vx: the box swings around its stopped end and the
             pushing duck turns with it.
    regroup  the pivot leaves the stopped duck behind. It is released and walks back to the box on
             velstand, steering to the box's push direction, while the pusher waits at vx 0 (until
             it touches the box, at most REGROUP_MAX_S).
    push     PushSteer along the line from the box's position now to the target: heading hold,
             square the box up inside the target, stand still when inside and square.

    Each phase runs once per episode. With the target straight ahead there is no pivot, so this
    is push_steer there. The box arrives turned by about the pivot angle; PushSteer's squaring
    has to take that out, which limits how far sideways this reaches (see the reachability sweep,
    scripts/rl/reachability.py).
    """

    ALIGN_TOL = math.radians(8.0)   # stopping the pivot earlier (a lead of 4-16 deg) scored worse
    PIVOT_MAX_S, REGROUP_MAX_S = 8.0, 4.0
    WALK_VX = 0.3              # velstand needs ~0.25 m/s commanded to start walking

    def __init__(self, env: CoPushEnv, vx: float = 0.2, pivot_vx: float = 0.2):
        super().__init__(env, vx=vx)
        self.pivot_vx = pivot_vx
        self.phase = "pivot"

    def _reset(self):
        super()._reset()
        self.phase, self.t0 = "pivot", self.env.state["t"]
        self.pusher = self.stopper = None

    def _geom(self, st):
        """bearing box->target, the box's push direction n (the long-face normal nearest the
        bearing), err = bearing - n (> 0: the box must turn counter-clockwise)."""
        bx, by = st["box"]["position"]
        gx, gy = st["goal"]["position"]
        bearing = math.atan2(gy - by, gx - bx)
        err = wrap_angle(bearing - (st["box"]["yaw"] + math.pi / 2))
        err = (err + math.pi / 2) % math.pi - math.pi / 2
        return bearing, bearing - err, err

    def _start_push(self, st, bearing):
        from copush.controllers import HeadingHoldPush
        self.phase, self.line = "push", bearing
        origin = tuple(st["box"]["position"])
        self.ctl = {d: HeadingHoldPush(vx=self.vx, duck=d, line_yaw=bearing, line_origin=origin) for d in DUCKS}

    def __call__(self, obs):
        env = self.env
        if self.episode != env.episode:
            self._reset()
        st = env.state
        t = st["t"] - self.t0
        bearing, n, err = self._geom(st)
        if self.phase == "pivot":
            if st["inside"] or abs(err) <= self.ALIGN_TOL or t >= self.PIVOT_MAX_S:
                self.phase, self.t0, t = ("regroup" if self.pusher else "push"), st["t"], 0.0
            else:
                self.mode = "pivot"
                if self.pusher is None:
                    bx, by = st["box"]["position"]
                    c, s_ = math.cos(n), math.sin(n)
                    left = max(DUCKS, key=lambda d: -s_ * (st[d]["position"][0] - bx) + c * (st[d]["position"][1] - by))
                    right = "duck_b" if left == "duck_a" else "duck_a"
                    self.pusher, self.stopper = (right, left) if err > 0 else (left, right)   # right end forward = turn left
                env.set_hold(self.stopper, True)
                cmd = {self.pusher: (self.pivot_vx, 0.0), self.stopper: (0.0, 0.0)}
                return cmd_to_action(*cmd["duck_a"], *cmd["duck_b"])
        if self.phase == "regroup":
            d = self.stopper
            if env.hold[d]:
                env.set_hold(d, False)
            if st["contact"][d]["in_contact"] or st["inside"] or t >= self.REGROUP_MAX_S:
                self._start_push(st, bearing)
            else:
                self.mode = "regroup"
                h = wrap_angle(n - st[d]["yaw"])
                cmd = {self.pusher: (0.0, 0.0), d: (self.WALK_VX, max(-VYAW_MAX, min(VYAW_MAX, 3.0 * h)))}
                return cmd_to_action(*cmd["duck_a"], *cmd["duck_b"])
        return super().__call__(obs)


def baseline(name: str, env: CoPushEnv, seed: int = 0):
    """random: uniform actions (own seeded RNG) · zero: action 0 = vx 0.15, no turning ·
    stand: vx 0 · push_forward: vx 0.2, no turning (scripts/copush_sim.py --script push_forward) ·
    push_steer: PushSteer (heading hold toward the target, stop inside) ·
    pivot_push: PivotThenPush (one duck stops so the box pivots toward the target, then PushSteer)."""
    if name == "random":
        rng = np.random.default_rng(seed)
        return lambda obs: rng.uniform(-1.0, 1.0, size=4).astype(np.float32)
    if name == "push_steer":
        return PushSteer(env)
    if name == "pivot_push":
        return PivotThenPush(env)
    fixed = {"zero": np.zeros(4, dtype=np.float32),
             "stand": cmd_to_action(0.0, 0.0, 0.0, 0.0),
             "push_forward": cmd_to_action(0.2, 0.0, 0.2, 0.0)}
    if name not in fixed:
        raise KeyError(f"unknown baseline {name!r}")
    a = fixed[name]
    return lambda obs: a


BASELINES = ("random", "zero", "stand", "push_forward", "push_steer")
