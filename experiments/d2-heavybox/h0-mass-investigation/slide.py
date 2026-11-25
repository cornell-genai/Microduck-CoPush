#!/usr/bin/env python3
"""Force needed to slide the box: a constant horizontal force for 1 s, box far from the ducks; how far it went."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import mujoco
from copush.env import CoPushEnv
from copush.config import effective_reward
from copush.experiments import load_stage

out = {}
for mult in (1, 2, 4):
    mass = C.BASE_MASS * mult
    env = CoPushEnv(C.stage_cfg(mass), split="eval")
    sim = env.sim; m, d = sim.m, sim.d; qb, _ = sim._box
    rows = []
    for frac in (0.5, 0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.25, 1.5):
        env.reset(seed=10000, options={"box": {"x": 0.35, "y": 0.0, "yaw": 90.0}})
        d.qpos[qb], d.qpos[qb + 1] = 3.0, 3.0
        d.qvel[:] = 0; mujoco.mj_forward(m, d)
        for _ in range(200): mujoco.mj_step(m, d)
        x0 = float(d.qpos[qb]); f = frac * mass * 9.81
        d.xfrc_applied[sim.box_body, 0] = f
        for _ in range(200): mujoco.mj_step(m, d)      # 1 s
        d.xfrc_applied[sim.box_body, 0] = 0
        rows.append((frac, round(f, 3), round(float(d.qpos[qb]) - x0, 4)))
    out[mult] = rows
    print(f"{mult}x ({mass} kg): (fraction of m*g, force N, metres moved in 1 s)", rows)
for name, path in (("stage1", "experiments/stage1-random-box-pose/config.yaml"), ("night5 run-l2", "experiments/d2-steering/night5/run-l2/config.yaml")):
    _, cfg = load_stage(path)
    r = effective_reward(cfg)
    print(name, {k: r[k] for k in ("version", "w_pos", "w_yaw", "time_penalty", "success_bonus", "fall_penalty", "fall_mode", "box_fail_penalty", "cooperation_mode", "contact_penalty")}, "both_held", r.get("both_held_penalty", 0), "controller", cfg.get("controller"), "stand_still", cfg["env"]["stand_still"]["enabled"], "box mass", cfg["box"]["mass"], cfg["box"].get("mass_range"), "randomize", cfg["env"]["randomize"])
