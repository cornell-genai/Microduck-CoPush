#!/usr/bin/env python3
"""Rendezvous evaluation: the rendezvous phase alone, and the full pipeline (rendezvous -> handoff -> push).

    scripts/rl.sh scripts/rl/rendezvous_eval.py make                     # experiments/test_sets/rendezvous_large.json (once)
    scripts/rl.sh scripts/rl/rendezvous_eval.py eval --rendezvous scripted --out experiments/d2-rendezvous/scripted-baseline
    scripts/rl.sh scripts/rl/rendezvous_eval.py eval --rendezvous runs/d2-rendezvous-r1-delta-reward/s1/model.zip --out ...
    scripts/rl.sh scripts/rl/rendezvous_eval.py eval ... --starts 10 --no-push        # quick check

make   200 starts, one per stage1_large.json box pose (the same Latin hypercube poses as the other eval sets), duck poses
       from copush.rendezvous.sample_ducks with rng seed 20261122: 160 uniform, 20 near-symmetric, 20 wrong-side starts.
eval   per start (seed 10000 + i, deterministic): the rendezvous phase until both ducks are within 3 cm and 15 deg of
       their spots and upright (checked every 0.2 s step), at most handoff_steps (50) steps; then
       CoPushEnv.begin_push_phase and the push policy (default runs/d2-steering-night5/l2-s2/model.zip, per duck with
       its partner in view and the stand-still action) for env.max_steps (100) steps. Push success is the env's: box
       centre in the target, yaw error <= 15 deg, both ducks up, held 1 s.
       Rendezvous-only numbers (arrival within the handoff budget): arrival rate, steps to arrive, position and heading
       error at handoff, collisions during the approach (duck-box per duck, duck-duck; counted once per 0.2 s step).
       --episode-steps N runs the rendezvous alone for N steps with the training env's ending (both within tolerance
       for hold_s), the check used while training. Writes results.json and results.md to --out.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts", "rl")]
os.chdir(ROOT)

CONFIG = "experiments/d2-rendezvous/config.yaml"
SET = "experiments/test_sets/rendezvous_large.json"
BASE_SET = "experiments/test_sets/stage1_large.json"
PUSH = "runs/d2-steering-night5/l2-s2/model.zip"
SEED = 20261122
KINDS = {"uniform": 160, "near_symmetric": 20, "wrong_side": 20}
DUCKS = ("duck_a", "duck_b")
_W: dict = {}


def make(a) -> int:
    from copush.experiments import load_stage
    from copush.rendezvous import make_rendezvous_set, settings
    out = os.path.join(ROOT, SET)
    if os.path.exists(out) and not a.force:
        print(f"{SET} exists; --force to rebuild")
        return 1
    _, cfg = load_stage(CONFIG)
    base = json.load(open(os.path.join(ROOT, BASE_SET)))
    tg = {"x": base["target"]["x"], "y": base["target"]["y"]}
    if (tg["x"], tg["y"]) != (cfg["layouts"]["rendezvous"]["target"]["x"], cfg["layouts"]["rendezvous"]["target"]["y"]):
        raise SystemExit("stage1_large's target differs from the rendezvous layout's")
    e, sc = cfg["env"], settings(cfg)["start"]
    starts = make_rendezvous_set(base["starts"], tg, KINDS, SEED, sc, e["contact_setback"], e["contact_spacing"])
    doc = {"stage": "rendezvous-large-heldout", "created": f"{dt.date.today()}", "config": CONFIG, "base_set": BASE_SET,
           "n": len(starts), "rng_seed": SEED, "kinds": KINDS, "target": base["target"], "start_rules": sc,
           "note": ("one start per stage1_large box pose (same order); per start: box pose (x, y m; yaw deg) and each duck's "
                    "x, y (m) and yaw (deg). Kinds: uniform (each duck 0.2-0.8 m from the box centre, bearing and heading "
                    "uniform), near_symmetric (both ducks within 2 cm of the box's push axis, so both pairings with the spots "
                    "are about equally long), wrong_side (both ducks within 60 deg of the push direction, on the target "
                    "side). Neither duck within 8 cm of the box, ducks at least 15 cm apart. Never used in training. "
                    "Episode seed 10000 + i."),
           "starts": starts}
    with open(out, "w") as f:
        json.dump(doc, f, indent=1)
    flags = [s["flags"] for s in starts]
    print(f"wrote {SET}: {len(starts)} starts, kinds {KINDS}; pairing margin < 5 cm: "
          f"{sum(f['pairing_margin_m'] < 0.05 for f in flags)}; at least one duck on the target side: "
          f"{sum(f['ducks_on_target_side'] > 0 for f in flags)}; both: {sum(f['ducks_on_target_side'] == 2 for f in flags)}")
    return 0


def _init(rendezvous, push, no_push, episode_steps):
    import torch
    torch.set_num_threads(1)
    from copush.env import CoPushEnv
    from copush.experiments import load_stage
    from copush.rendezvous import Rendezvous
    _, cfg = load_stage(CONFIG)
    env = CoPushEnv(cfg, split="eval")
    rv = Rendezvous(env)
    _W.update(env=env, rv=rv, starts=json.load(open(os.path.join(ROOT, SET)))["starts"], no_push=no_push,
              episode_steps=episode_steps, seed0=cfg["env"]["heldout_seeds"][0])
    if rendezvous == "scripted":
        from copush.rendezvous import ScriptedRendezvous
        _W["rv_act"] = ScriptedRendezvous(rv)
    else:
        from stable_baselines3 import PPO
        from copush.rendezvous import policy_act
        _W["rv_act"] = policy_act(PPO.load(os.path.join(ROOT, rendezvous), device="cpu"), rv)
    if not no_push:
        from test_set import make_act_factory
        _W["push"] = make_act_factory("push", {"path": push, "decentral": {"include_partner": True}, "standstill": True})


def episode(i: int) -> dict:
    env, rv, act = _W["env"], _W["rv"], _W["rv_act"]
    start = _W["starts"][i]
    seed = _W["seed0"] + i
    rv.reset(start, seed=seed)
    budget = _W["episode_steps"] or rv.r["handoff_steps"]
    fell = False
    while rv.steps < budget:
        if _W["episode_steps"] is None and rv.ready():
            break
        _, info = rv.step(act(None))
        fell |= info["fell"]
        if _W["episode_steps"] is not None and (info["arrived"] or info["fell"]):
            break
    e = rv.errors()
    arrived = (rv.arrived() if _W["episode_steps"] is not None else rv.ready())
    out = {"i": i, "id": start["id"], "kind": start["kind"], "flags": start["flags"], "arrived": bool(arrived),
           "rv_steps": rv.steps, "fell_rv": bool(fell), "assign": dict(rv.assign),
           "pos_err_cm": {d: round(100 * e[d][0], 2) for d in DUCKS},
           "yaw_err_deg": {d: round(math.degrees(e[d][1]), 2) for d in DUCKS},
           "hit_box": dict(rv.collisions["box"]), "hit_ducks": rv.collisions["ducks"]}
    if _W["no_push"] or _W["episode_steps"] is not None:
        return out
    obs, _ = env.begin_push_phase()
    pact = _W["push"](env, seed)
    while True:
        obs, _, te, tr, info = env.step(pact(obs))
        if te or tr:
            break
    es = info["episode_stats"]
    sh = es["push_share"]["duck_a"]
    out.update(push_reason=es["reason"], push_success=es["reason"] == "success", push_steps=int(es["steps"]),
               push_share_a=None if sh != sh else round(float(sh), 4))
    return out


def summarize(eps: list, push: bool) -> dict:
    from ci_report import wilson
    n = len(eps)
    arr = [e for e in eps if e["arrived"]]
    lo, hi = wilson(len(arr), n)
    pe = [e["pos_err_cm"][d] for e in eps for d in DUCKS]
    ye = [e["yaw_err_deg"][d] for e in eps for d in DUCKS]
    s = {"n": n, "arrived": len(arr), "arrival_rate": len(arr) / n, "arrival_ci": [lo, hi],
         "mean_steps_to_arrive": (sum(e["rv_steps"] for e in arr) / len(arr)) if arr else None,
         "pos_err_cm_median": sorted(pe)[len(pe) // 2], "pos_err_cm_mean": sum(pe) / len(pe),
         "yaw_err_deg_median": sorted(ye)[len(ye) // 2], "yaw_err_deg_mean": sum(ye) / len(ye),
         "pos_err_cm_arrived_mean": (sum(e["pos_err_cm"][d] for e in arr for d in DUCKS) / (2 * len(arr))) if arr else None,
         "yaw_err_deg_arrived_mean": (sum(e["yaw_err_deg"][d] for e in arr for d in DUCKS) / (2 * len(arr))) if arr else None,
         "duck_box_hits": sum(e["hit_box"][d] for e in eps for d in DUCKS),
         "episodes_with_duck_box_hit": sum(1 for e in eps if any(e["hit_box"].values())),
         "duck_duck_hits": sum(e["hit_ducks"] for e in eps),
         "episodes_with_duck_duck_hit": sum(1 for e in eps if e["hit_ducks"]),
         "falls_rv": sum(e["fell_rv"] for e in eps)}
    if push:
        ok = [e for e in eps if e["push_success"]]
        lo, hi = wilson(len(ok), n)
        oka = [e for e in arr if e["push_success"]]
        s.update(end_to_end=len(ok), end_to_end_rate=len(ok) / n, end_to_end_ci=[lo, hi],
                 push_success_after_arrival=len(oka), push_success_after_arrival_rate=(len(oka) / len(arr)) if arr else None,
                 push_success_after_timeout=len(ok) - len(oka),
                 push_reasons={r: sum(e["push_reason"] == r for e in eps) for r in sorted({e["push_reason"] for e in eps})})
    return s


def pct(x):
    return "n/a" if x is None else f"{max(0.0, 100 * x):.1f}%"


def report(doc: dict) -> str:
    push = not doc["no_push"] and doc["episode_steps"] is None
    groups = ["all"] + list(KINDS) + ["target_side_1+", "pairing_margin<5cm"]
    S = doc["summary"]
    L = [f"# Rendezvous evaluation: {doc['rendezvous']}", "",
         f"{doc['n']} starts from `{SET}`, deterministic, seed 10000 + i. "
         + (f"Rendezvous alone for {doc['episode_steps']} steps (training ending)." if doc["episode_steps"] else
            f"Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at {doc['handoff_steps']} steps"
            + (f"; then the push policy `{doc['push']}` for 100 steps." if push else "; push phase skipped.")), "",
         "## Rendezvous", "",
         "| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | "
         "heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |",
         "|---|---|---|---|---|---|---|---|---|"]
    for g in groups:
        s = S.get(g)
        if not s:
            continue
        ms = "n/a" if s["mean_steps_to_arrive"] is None else f"{s['mean_steps_to_arrive']:.1f}"
        L.append(f"| {g} | {s['n']} | {pct(s['arrival_rate'])} ({pct(s['arrival_ci'][0])} to {pct(s['arrival_ci'][1])}) | {ms} | "
                 f"{s['pos_err_cm_mean']:.1f} / {s['pos_err_cm_median']:.1f} | {s['yaw_err_deg_mean']:.1f} / {s['yaw_err_deg_median']:.1f} | "
                 f"{s['duck_box_hits']} ({s['episodes_with_duck_box_hit']}) | {s['duck_duck_hits']} ({s['episodes_with_duck_duck_hit']}) | {s['falls_rv']} |")
    a = S["all"]
    if a["pos_err_cm_arrived_mean"] is not None:
        L += ["", f"Arrived episodes only: position error {a['pos_err_cm_arrived_mean']:.1f} cm, heading error "
                  f"{a['yaw_err_deg_arrived_mean']:.1f} deg (means over both ducks)."]
    if push:
        L += ["", "## End to end (rendezvous, handoff, push)", "",
              "| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |",
              "|---|---|---|---|---|"]
        for g in groups:
            s = S.get(g)
            if not s:
                continue
            L.append(f"| {g} | {s['n']} | {pct(s['end_to_end_rate'])} ({pct(s['end_to_end_ci'][0])} to {pct(s['end_to_end_ci'][1])}) | "
                     f"{s['push_success_after_arrival']} of {s['arrived']} ({pct(s['push_success_after_arrival_rate'])}) | "
                     f"{s['push_success_after_timeout']} of {s['n'] - s['arrived']} |")
        L += ["", "Push endings, all starts: " + ", ".join(f"{k} {v}" for k, v in a["push_reasons"].items()) + "."]
    L += ["", f"Wall time {doc['wall_s']} s."]
    return "\n".join(L) + "\n"


def evaluate(a) -> int:
    t0 = time.time()
    starts = json.load(open(os.path.join(ROOT, SET)))["starts"]
    n = min(a.starts or len(starts), len(starts))
    with Pool(a.workers, initializer=_init, initargs=(a.rendezvous, a.push, a.no_push, a.episode_steps)) as p:
        eps = sorted(p.map(episode, range(n), chunksize=2), key=lambda e: e["i"])
    push = not a.no_push and a.episode_steps is None
    groups = {"all": eps, **{k: [e for e in eps if e["kind"] == k] for k in KINDS},
              "target_side_1+": [e for e in eps if e["flags"]["ducks_on_target_side"] > 0],
              "pairing_margin<5cm": [e for e in eps if e["flags"]["pairing_margin_m"] < 0.05]}
    doc = {"rendezvous": a.rendezvous, "push": None if a.no_push else a.push, "set": SET, "n": n, "no_push": a.no_push,
           "episode_steps": a.episode_steps, "handoff_steps": None if a.episode_steps else 50,
           "summary": {g: summarize(v, push) for g, v in groups.items() if v}, "wall_s": round(time.time() - t0, 1),
           "episodes": eps}
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)
    json.dump(doc, open(os.path.join(out, "results.json"), "w"), indent=0)
    md = report(doc)
    open(os.path.join(out, "results.md"), "w").write(md)
    print(md)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--force", action="store_true")
    e = sub.add_parser("eval")
    e.add_argument("--rendezvous", default="scripted", help="scripted, or a rendezvous model.zip")
    e.add_argument("--push", default=PUSH)
    e.add_argument("--out", required=True)
    e.add_argument("--starts", type=int, default=0)
    e.add_argument("--workers", type=int, default=8)
    e.add_argument("--no-push", action="store_true")
    e.add_argument("--episode-steps", type=int, default=None)
    a = ap.parse_args()
    return make(a) if a.cmd == "make" else evaluate(a)


if __name__ == "__main__":
    sys.exit(main())
