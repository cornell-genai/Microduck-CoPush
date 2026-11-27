#!/usr/bin/env python3
"""Check set_box_floor_friction: 0.15 kg box, box-floor mu 2.5 should slide at about 2.5 * 0.15 * 9.81 = 3.68 N if it
slides at all. The force is applied at the box centre (4.5 cm up), then at 1 cm above the floor; box tilt is reported."""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import mujoco, numpy as np
from copush.env import CoPushEnv
env = CoPushEnv(C.stage_cfg(C.BASE_MASS), split="eval")
C.set_box_floor_friction(env, 2.5)
sim = env.sim; m, d = sim.m, sim.d; qb, _ = sim._box
print("box-floor mu 2.5, 0.15 kg")
for height in (0.045, 0.01):
    for f in (1.6, 2.5, 3.3, 3.68, 4.2):
        env.reset(seed=10000, options={"box": {"x": 0.35, "y": 0.0, "yaw": 90.0}})
        d.qpos[qb], d.qpos[qb + 1] = 3.0, 3.0; d.qvel[:] = 0; mujoco.mj_forward(m, d)
        for _ in range(200): mujoco.mj_step(m, d)
        x0 = float(d.qpos[qb]); tilt = 0.0
        for _ in range(200):
            d.qfrc_applied[:] = 0
            p = d.xpos[sim.box_body].copy(); p[2] = height
            mujoco.mj_applyFT(m, d, np.array([f, 0, 0.0]), np.zeros(3), p, sim.box_body, d.qfrc_applied)
            mujoco.mj_step(m, d)
            zaxis = d.xmat[sim.box_body].reshape(3, 3)[:, 2]
            tilt = max(tilt, math.degrees(math.acos(max(-1, min(1, zaxis[2])))))
        d.qfrc_applied[:] = 0
        print(f"push height {height*100:.1f} cm, force {f} N: moved {float(d.qpos[qb]) - x0:.3f} m in 1 s, max tilt {tilt:.0f} deg")
