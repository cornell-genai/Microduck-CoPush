#!/usr/bin/env python3
"""Box and duck physics from the compiled MuJoCo model, and open-loop push-force measurements.

    scripts/rl.sh experiments/d2-heavybox/h0-mass-investigation/physics.py

1. Parameters: box mass / size / friction, floor friction, duck mass and foot friction, friction mixing options.
2. Slide test: a horizontal force on the box is ramped up until the box moves (ducks parked far away).
3. Wall test: the box is made 100 kg (cannot move) and one duck, then both, push at full command; the contact
   force on the box along the push direction is recorded.
4. Open-loop mass ladder: at each box mass, duck A alone / B alone / both walk forward at full command for 10 s.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

START = {"x": 0.35, "y": 0.0, "yaw": 90.0}


def params():
    import mujoco
    from copush.env import CoPushEnv
    from copush.sim import PREFIX
    env = CoPushEnv(C.stage_cfg(C.BASE_MASS), split="eval")
    m, sim = env.sim.m, env.sim
    name = lambda t, i: mujoco.mj_id2name(m, t, i) or ""   # noqa: E731
    g = sim.box_geom
    out = {"box": {"mass": float(m.body_mass[sim.box_body]), "size_m": [float(2 * x) for x in m.geom_size[g]],
                   "friction": m.geom_friction[g].tolist(), "condim": int(m.geom_condim[g]), "priority": int(m.geom_priority[g])},
           "gravity": m.opt.gravity.tolist(), "cone": int(m.opt.cone), "impratio": float(m.opt.impratio), "timestep": float(m.opt.timestep)}
    planes = [i for i in range(m.ngeom) if m.geom_type[i] == mujoco.mjtGeom.mjGEOM_PLANE]
    out["floor"] = [{"name": name(mujoco.mjtObj.mjOBJ_GEOM, i), "friction": m.geom_friction[i].tolist(), "condim": int(m.geom_condim[i]),
                     "priority": int(m.geom_priority[i])} for i in planes]
    for duck, prefix in PREFIX.items():
        bodies = [b for b in range(m.nbody) if name(mujoco.mjtObj.mjOBJ_BODY, b).startswith(prefix)]
        geoms = [i for i in range(m.ngeom) if int(m.geom_bodyid[i]) in bodies and (m.geom_contype[i] or m.geom_conaffinity[i])]
        fr = {}
        for i in geoms:
            fr.setdefault(tuple(round(float(x), 5) for x in m.geom_friction[i]), []).append(
                name(mujoco.mjtObj.mjOBJ_BODY, int(m.geom_bodyid[i]))[len(prefix):])
        out[duck] = {"mass": float(sum(m.body_mass[b] for b in bodies)), "colliding_geoms": len(geoms),
                     "friction_groups": [{"friction": list(k), "n": len(v), "bodies": sorted(set(v))} for k, v in fr.items()]}
    mu = max(out["box"]["friction"][0], out["floor"][0]["friction"][0]) if out["floor"] else None
    out["box_floor_mu_effective"] = mu
    out["slide_force_N_formula"] = None if mu is None else mu * out["box"]["mass"] * abs(out["gravity"][2])
    return out


def slide_test(mass):
    """Ducks parked 1 m behind the box (approach layout not needed: they are just moved away and held); a force along
    +x on the box rises 0.05 N per control step until the box has moved 5 mm."""
    import mujoco
    from copush.env import CoPushEnv
    cfg = C.stage_cfg(mass)
    env = CoPushEnv(cfg, split="eval")
    env.reset(seed=10000, options={"box": {"x": 1.5, "y": 1.0, "yaw": 90.0}})   # ducks are placed behind it; move the box away instead
    sim = env.sim
    m, d = sim.m, sim.d
    qb, _ = sim._box
    d.qpos[qb], d.qpos[qb + 1] = 3.0, 3.0                                       # far from both ducks
    d.qvel[:] = 0
    mujoco.mj_forward(m, d)
    for _ in range(200):
        mujoco.mj_step(m, d)                                                   # let the box settle
    x0 = float(d.qpos[qb])
    f = 0.0
    while f < 200:
        f += 0.01
        d.xfrc_applied[sim.box_body, 0] = f
        for _ in range(10):
            mujoco.mj_step(m, d)
        if abs(float(d.qpos[qb]) - x0) > 0.005:
            break
    d.xfrc_applied[sim.box_body, 0] = 0
    return f


def open_loop(mass, mode, seconds=10.0, mu=None, vx_action=1.0):
    """Both ducks start in contact at the nominal start; the pushing duck(s) get a constant forward command
    (action +1 = 0.30 m/s, no turn), idle ducks stand still. Returns forces and how far the box went."""
    from copush.env import CoPushEnv
    env = CoPushEnv(C.stage_cfg(mass), split="eval")
    C.set_box_friction(env, mu)
    env.reset(seed=10000, options={"box": START})
    p0 = C.box_xy(env)
    per_ctrl = {"duck_a": [], "duck_b": []}
    env.frame_hook = lambda st, _: [per_ctrl[d].append(st["contact"][d]["push_force"]) for d in per_ctrl]
    steps, reason = [], None
    for _ in range(int(round(seconds / env.dt))):
        a = C.force_idle(np.array([vx_action, 0.0, vx_action, 0.0], dtype=np.float32), mode)
        _, _, te, tr, info = env.step(a)
        steps.append({d: info["push_force"][d] for d in per_ctrl})
        if te or tr:
            reason = info["episode_stats"]["reason"]
            break
    moved = C.dist(C.box_xy(env), p0)
    out = {"mass": mass, "mode": mode, "mu": mu, "moved_m": moved, "speed_m_s": moved / (len(steps) * env.dt), "ended": reason,
           "steps": len(steps)}
    for d in per_ctrl:
        s = [x[d] for x in steps]
        late = s[5:] or s
        out[d] = {"mean_N": float(np.mean(late)), "max_step_mean_N": float(np.max(s)), "p95_step_N": float(np.percentile(s, 95)),
                  "peak_ctrl_N": float(np.max(per_ctrl[d])) if per_ctrl[d] else 0.0}
    return out


def main() -> int:
    os.makedirs(C.OUT, exist_ok=True)
    doc = {"params": params()}
    print(json.dumps(doc["params"], indent=1))
    doc["slide"] = {str(mult): slide_test(C.BASE_MASS * mult) for mult in (1, 2, 4)}
    print("slide force (N) by mass multiple:", doc["slide"])
    doc["wall"] = [open_loop(100.0, mode, seconds=10.0) for mode in ("B_idle", "A_idle", "both")]
    for r in doc["wall"]:
        print("WALL", json.dumps(r))
    doc["ladder"] = []
    for mult in (1, 1.5, 2, 3, 4, 6, 8, 12):
        for mode in ("B_idle", "A_idle", "both"):
            r = open_loop(C.BASE_MASS * mult, mode)
            r["mult"] = mult
            doc["ladder"].append(r)
            print(f"LADDER {mult}x {mode}: moved {r['moved_m']:.2f} m, ended {r['ended']} after {r['steps']} steps, "
                  f"A {r['duck_a']['mean_N']:.2f} N, B {r['duck_b']['mean_N']:.2f} N")
    json.dump(doc, open(os.path.join(C.OUT, "physics.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
