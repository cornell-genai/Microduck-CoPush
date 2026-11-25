#!/usr/bin/env python3
"""Box mass (and friction) sweep for the frozen L2-s2 push policy: both ducks, duck A idle, duck B idle.

    scripts/rl.sh experiments/d2-heavybox/h0-mass-investigation/sweep.py --name mass50 --mult 1 1.5 2 3 4 6 --starts 50
    scripts/rl.sh experiments/d2-heavybox/h0-mass-investigation/sweep.py --name solo200 --mult 1 --starts 200
    scripts/rl.sh experiments/d2-heavybox/h0-mass-investigation/sweep.py --name fric --mult 3 --friction 0.6 1.0 1.5 --starts 50

Evaluation only. Clean stage 1 test set, per-start seed 10000 + i, deterministic, 100 steps, as the night 5 evals.
Writes results/<name>.json (per episode) and prints a table.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

_W: dict = {}


def _init():
    import torch
    torch.set_num_threads(1)
    from copush.experiments import load_test_set
    from test_set import make_act_factory
    _W["act"] = make_act_factory("l2_s2", {"path": C.POLICY, "decentral": {"include_partner": True}, "standstill": True})
    _W["starts"] = load_test_set(C.SET)["starts"]
    _W["env"] = {}


def _episode(job):
    mult, mu, mode, i, depth, com = job
    from copush.env import CoPushEnv
    key = (mult, mu, depth, com)
    if key not in _W["env"]:
        if depth is not None:                             # build the model with the deeper box (no in-place resize)
            import copush.sim as S
            S.BOX_HALF = (S.BOX_HALF[0], float(depth) / 2, S.BOX_HALF[2])
        env = CoPushEnv(C.stage_cfg(C.BASE_MASS * mult, depth), split="eval")
        if depth is not None:
            assert abs(2 * float(env.sim.m.geom_size[env.sim.box_geom][1]) - depth) < 1e-9
        C.set_box_floor_friction(env, mu)
        C.set_box_shape(env, None, com)
        _W["env"][key] = env
    env = _W["env"][key]
    seed = 10000 + i
    act = _W["act"](env, seed)
    obs, _ = env.reset(seed=seed, options={"box": _W["starts"][i]})
    assert abs(float(env.sim.m.body_mass[env.sim.box_body]) - C.BASE_MASS * mult) < 1e-9
    p0 = C.box_xy(env)
    cf = {"duck_a": 0.0, "duck_b": 0.0}
    max_move = 0.0
    ever_inside = False
    max_tilt = 0.0
    clog = C.ContactLog(env)
    while True:
        obs, _, te, tr, info = env.step(C.force_idle(act(obs), mode))
        for d in cf:
            cf[d] += info["contact_force"][d] * env.dt
        max_move = max(max_move, C.dist(C.box_xy(env), p0))
        ever_inside |= bool(info["inside"])
        max_tilt = max(max_tilt, float(env.state["box"]["tilt_deg"]))
        if te or tr:
            break
    es = info["episode_stats"]
    sh = es["push_share"]["duck_a"]
    tot = cf["duck_a"] + cf["duck_b"]
    return {"mult": mult, "mu": mu, "mode": mode, "i": i, "reason": es["reason"], "steps": int(es["steps"]),
            "push_a": None if sh != sh else float(sh), "contact_a": None if tot <= 0 else cf["duck_a"] / tot,
            "depth": depth, "com": com, "ever_inside": ever_inside, "max_tilt": max_tilt, "contact_z": clog.result(), "final_yaw_deg": float(es["final_yaw_deg"]), "fell": [d for d, f in es["fell"].items() if f], "moved": C.dist(C.box_xy(env), p0), "max_moved": max_move,
            "start_dist": float(es["start_dist"]), "final_dist": float(es["final_dist"]), "min_dist": float(es["min_dist"])}


def summarize(eps, coop=0.25):
    from ci_report import wilson
    n = len(eps)
    ok = [e for e in eps if e["reason"] == "success"]
    co = [e for e in ok if e["push_a"] is not None and coop <= e["push_a"] <= 1 - coop]
    out = {"n": n, "success": len(ok), "coop": len(co), "falls": sum(1 for e in eps if e["fell"]),
           "reasons": {r: sum(1 for e in eps if e["reason"] == r) for r in sorted({e["reason"] for e in eps})},
           "moved_2cm": sum(1 for e in eps if e["max_moved"] >= 0.02), "moved_10cm": sum(1 for e in eps if e["max_moved"] >= 0.10),
           "progress_mean": sum(e["start_dist"] - e["final_dist"] for e in eps) / n,
           "start_dist_mean": sum(e["start_dist"] for e in eps) / n,
           "push_a_mean": (sum(e["push_a"] for e in eps if e["push_a"] is not None) / max(1, sum(1 for e in eps if e["push_a"] is not None)))}
    out["tipped"] = sum(1 for e in eps if e["reason"] == "box_tipped")
    zs = [e["contact_z"][d]["mean_z"] for e in eps for d in ("duck_a", "duck_b") if e.get("contact_z") and e["contact_z"][d]["mean_z"] is not None]
    zm = [e["contact_z"][d]["max_z"] for e in eps for d in ("duck_a", "duck_b") if e.get("contact_z") and e["contact_z"][d]["max_z"] is not None]
    out["contact_z_mean_cm"] = 100 * sum(zs) / len(zs) if zs else None
    out["contact_z_max_cm"] = 100 * max(zm) if zm else None
    out["contact_z_p95max_cm"] = 100 * sorted(zm)[int(0.95 * (len(zm) - 1))] if zm else None
    out["max_tilt_p95"] = sorted(e.get("max_tilt", 0.0) for e in eps)[int(0.95 * (n - 1))]
    out["steps_success_mean"] = sum(e["steps"] for e in ok) / len(ok) if ok else None
    out["steps_success_max"] = max((e["steps"] for e in ok), default=None)
    out["overshoot"] = sum(1 for e in eps if e["reason"] != "success" and (e.get("ever_inside") or e["final_dist"] - e["min_dist"] > 0.05))
    out["success_ci"], out["coop_ci"] = wilson(len(ok), n), wilson(len(co), n)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--mult", type=float, nargs="+", default=[1.0])
    ap.add_argument("--friction", type=float, nargs="*", default=[])
    ap.add_argument("--modes", nargs="+", default=list(C.MODES))
    ap.add_argument("--starts", type=int, default=50)
    ap.add_argument("--depth", type=float, default=None, help="box depth in m (0.10 now)")
    ap.add_argument("--com-drop", type=float, default=None, help="centre of mass this far below the box centre, m")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    mus = a.friction or [None]
    jobs = [(m, mu, mode, i, a.depth, a.com_drop) for m in a.mult for mu in mus for mode in a.modes for i in range(a.starts)]
    t0 = time.time()
    with Pool(a.workers, initializer=_init) as p:
        eps = p.map(_episode, jobs, chunksize=2)
    os.makedirs(C.OUT, exist_ok=True)
    rows = []
    for m in a.mult:
        for mu in mus:
            for mode in a.modes:
                e = sorted((x for x in eps if (x["mult"], x["mu"], x["mode"]) == (m, mu, mode)), key=lambda x: x["i"])
                rows.append({"mult": m, "mass_kg": C.BASE_MASS * m, "mu": mu, "mode": mode, **summarize(e)})
    json.dump({"depth": a.depth, "com_drop": a.com_drop, "policy": C.POLICY, "set": C.SET, "starts": a.starts, "wall_s": round(time.time() - t0, 1), "rows": rows, "episodes": eps},
              open(os.path.join(C.OUT, a.name + ".json"), "w"))
    pc = lambda k, n, ci: f"{100 * k / n:.1f}% ({100 * ci[0]:.1f} to {100 * ci[1]:.1f})"  # noqa: E731
    print("| mass | friction | ducks | task success | cooperative success | falls | box tip-overs | duck-box contact height cm: typical / 95% of episode maxima / max | box moved >= 2 cm | >= 10 cm | mean progress / start distance (m) | steps to success, mean (max) | overshoots (failed after reaching the target or passing it by 5 cm) | endings |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['mult']}x ({r['mass_kg']:.3f} kg) | {'default' if r['mu'] is None else r['mu']} | {r['mode']} | "
              f"{pc(r['success'], r['n'], r['success_ci'])} | {pc(r['coop'], r['n'], r['coop_ci'])} | {r['falls']}/{r['n']} | {r['tipped']}/{r['n']} | "
              + (f"{r['contact_z_mean_cm']:.1f} / {r['contact_z_p95max_cm']:.1f} / {r['contact_z_max_cm']:.1f}" if r['contact_z_mean_cm'] is not None else "-") + " | "
              + f"{r['moved_2cm']}/{r['n']} | {r['moved_10cm']}/{r['n']} | {r['progress_mean']:.2f} / {r['start_dist_mean']:.2f} | "
              + (f"{r['steps_success_mean']:.0f} ({r['steps_success_max']})" if r['success'] else "-") + f" | {r['overshoot']}/{r['n']} | {r['reasons']} |")
    print(f"wall {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
