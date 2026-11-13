"""Decentralized control: each duck runs the same network on its own view.

    from copush.decentral import DuckPairEnv, DuckVecEnv, make_pair_env, decentral_action
    vec = VecMonitor(DuckVecEnv(SubprocVecEnv([make_pair_env(cfg, partner) for _ in range(8)])))
    model = PPO("MlpPolicy", vec, ...)                      # 16 entries: duck A and duck B of 8 sims
    act = lambda obs: decentral_action(model, env.state, partner)   # on a plain CoPushEnv (eval, videos)

Local observation of one duck (local_obs, LOCAL_NAMES), everything in that duck's own frame (x along
its heading, y to its left):
    box position relative to the duck (2), box yaw relative to the duck's heading as sin/cos of 2x
    (2; the box is 180-degree symmetric), target position relative to the box (2), box yaw error vs
    the target as sin/cos of 2x (2), box velocity (2) and yaw rate (1), the duck's own velocity
    (forward, left; 2), touching the box (1), on Shoe Push (1)
    partner (include_partner): partner position relative to this duck (2), partner heading
    relative to this duck's as sin/cos (2)
Action of one duck: [vx, vyaw] in [-1, 1], mapped exactly like that duck's half of the central action
(copush.env.action_to_cmd). Both ducks get the team reward and the same episode endings.

DuckPairEnv is one simulation seen as two agents: observation (2, n), action (2, 2), so one
SubprocVecEnv worker steps both ducks together. DuckVecEnv flattens N of them into 2N entries
(duck A of sim i is entry 2i, duck B is 2i + 1) so Stable-Baselines3 trains one shared policy.
"""
from __future__ import annotations

import inspect
import math
from typing import Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from stable_baselines3.common.vec_env import VecEnv, VecEnvWrapper

from copush.env import CoPushEnv
from copush.state import wrap_angle

DUCK_ORDER = ("duck_a", "duck_b")
OWN_NAMES = ["box_dx", "box_dy", "box_sin2", "box_cos2", "tgt_dx", "tgt_dy", "err_sin2", "err_cos2",
             "box_vx", "box_vy", "box_yaw_rate", "own_vx", "own_vy", "contact", "shoepush"]
PARTNER_NAMES = ["mate_dx", "mate_dy", "mate_sin", "mate_cos"]


def local_names(include_partner: bool) -> list:
    return OWN_NAMES + (PARTNER_NAMES if include_partner else [])


def local_obs(st: dict, duck: str, include_partner: bool) -> np.ndarray:
    """One duck's view of the state dict (CoPushEnv.state), in its own frame."""
    me = st[duck]
    h = me["yaw"]
    c, s = math.cos(h), math.sin(h)

    def tf(x, y):                                        # world vector -> this duck's frame
        return c * x + s * y, -s * x + c * y

    mx, my = me["position"]
    bx, by = st["box"]["position"]
    gx, gy = st["goal"]["position"]
    rel = wrap_angle(st["box"]["yaw"] - h)
    err = wrap_angle(st["box"]["yaw"] - st["goal"]["yaw"])
    o = [*tf(bx - mx, by - my), math.sin(2 * rel), math.cos(2 * rel),
         *tf(gx - bx, gy - by), math.sin(2 * err), math.cos(2 * err),
         *tf(*st["box"]["velocity"]), st["box"]["yaw_rate"],
         *tf(*me["velocity"]), float(st["contact"][duck]["in_contact"]), float(me["policy"] == "shoepush")]
    if include_partner:
        mate = st[DUCK_ORDER[1 - DUCK_ORDER.index(duck)]]
        px, py = mate["position"]
        dh = wrap_angle(mate["yaw"] - h)
        o += [*tf(px - mx, py - my), math.sin(dh), math.cos(dh)]
    return np.asarray(o, dtype=np.float32)


def pair_obs(st: dict, include_partner: bool) -> np.ndarray:
    return np.stack([local_obs(st, d, include_partner) for d in DUCK_ORDER])


def decentral_action(model, st: dict, include_partner: bool) -> np.ndarray:
    """The central 4-vector [A vx, A vyaw, B vx, B vyaw]: the shared policy run once per duck on that
    duck's own observation (deterministic)."""
    a, _ = model.predict(pair_obs(st, include_partner), deterministic=True)
    return np.clip(np.asarray(a, dtype=np.float32), -1.0, 1.0).reshape(4)


class DuckPairEnv(gym.Env):
    """A CoPushEnv seen as two agents sharing a policy: observation (2, n), action (2, 2)."""
    metadata = {"render_modes": []}

    def __init__(self, cfg: Optional[dict] = None, include_partner: bool = False, split: str = "train"):
        super().__init__()
        self.env = CoPushEnv(cfg, split=split)
        self.include_partner = include_partner
        n = len(local_names(include_partner))
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(2, n), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(2, 2), dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        _, info = self.env.reset(seed=seed, options=options)
        return pair_obs(self.env.state, self.include_partner), info

    def step(self, action):
        _, r, te, tr, info = self.env.step(np.asarray(action, dtype=np.float32).reshape(4))
        return pair_obs(self.env.state, self.include_partner), r, te, tr, info

    def set_box_range(self, scale: float) -> float:
        return self.env.set_box_range(scale)

    def close(self):
        self.env.close()


def make_pair_env(cfg: Optional[dict] = None, include_partner: bool = False, split: str = "train"):
    def _thunk():
        return DuckPairEnv(cfg, include_partner, split)
    return _thunk


class DuckVecEnv(VecEnvWrapper):
    """N DuckPairEnv workers -> 2N single-duck entries: observation (n,), action (2,). Reward,
    done and info are the sim's, repeated for both ducks; the terminal observation is split too."""

    def __init__(self, venv):
        pair_obs_space, pair_act_space = venv.observation_space, venv.action_space
        obs_space = spaces.Box(-np.inf, np.inf, shape=pair_obs_space.shape[1:], dtype=np.float32)
        act_space = spaces.Box(-1.0, 1.0, shape=pair_act_space.shape[1:], dtype=np.float32)
        self.venv = venv
        VecEnv.__init__(self, num_envs=2 * venv.num_envs, observation_space=obs_space, action_space=act_space)
        self.class_attributes = dict(inspect.getmembers(self.__class__))

    def reset(self):
        obs = self.venv.reset()
        return obs.reshape(self.num_envs, -1)

    def step_async(self, actions):
        self.venv.step_async(np.asarray(actions).reshape(self.venv.num_envs, 2, -1))

    def step_wait(self):
        obs, rew, done, infos = self.venv.step_wait()
        out = []
        for info in infos:
            for k in range(2):
                d = dict(info)
                if "terminal_observation" in info:
                    d["terminal_observation"] = info["terminal_observation"][k]
                out.append(d)
        return obs.reshape(self.num_envs, -1), np.repeat(rew, 2), np.repeat(done, 2), out

    def env_method(self, method_name, *args, indices=None, **kwargs):
        if indices is not None:                          # entry indices -> sim indices
            indices = sorted({i // 2 for i in (indices if hasattr(indices, "__iter__") else [indices])})
        return self.venv.env_method(method_name, *args, indices=indices, **kwargs)

    def seed(self, seed=None):
        return self.venv.seed(seed)
