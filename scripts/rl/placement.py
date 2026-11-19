#!/usr/bin/env python3
"""Night 5, L2 set, L2-trained policies (l2_s1, l2_s2): per-step duck placement and box progress (no training).

Replays every episode exactly as the night 5 evaluation did (sets/L2 config, stage1_L2_large.json, seed 10000 + i,
@partner@standstill, deterministic) and records per step:
  each duck's heading error and position error against its noise-free spot on the box, i.e. where
  copush.env._place_in_contact puts it without noise (setback 0.095 m behind the box centre on the push side,
  +-spacing/2 along the long axis, facing the push direction), fixed in the box's frame at the start and moved with the box;
  the box position and its distance to the target.
Checks each replayed episode against runs/d2-steering/night5/results/eval_L2/comparison.json (reason, steps,
both_hold_steps). Writes episodes.json, stops.json and report.md to runs/d2-steering/night5/placement/ (git-ignored).

    scripts/rl.sh scripts/rl/placement.py
    scripts/rl.sh scripts/rl/placement.py --report-only    # report.md from the saved episodes.json, no replay
"""
from __future__ import annotations

import json
import math
import os
import statistics as st
import sys
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts", "rl")]
os.chdir(ROOT)

CFG = "experiments/d2-steering/night5/sets/L2/config.yaml"
TS = "experiments/test_sets/stage1_L2_large.json"
POL = {"l2_s1": "runs/d2-steering-night5/l2-s1/model.zip", "l2_s2": "runs/d2-steering-night5/l2-s2/model.zip"}
REF = "runs/d2-steering/night5/results/eval_L2/comparison.json"
OUT = os.path.join(ROOT, "runs", "d2-steering", "night5", "placement")
DUCKS = ("duck_a", "duck_b")
FIRST = 10
STOP_M = (0.002, 0.005, 0.010)      # per-step progress thresholds (m per 0.2 s step); 0.005 is the headline
BOTH_IDLE = 0.30

_W = {}


def _init():
    from copush.experiments import load_stage, load_test_set
    from test_set import make_act_factory
    _, cfg = load_stage(CFG)
    cfg["env"]["stand_still"] = {**cfg["env"]["stand_still"], "enabled": True}
    _W.update(cfg=cfg, starts=load_test_set(TS)["starts"],
              acts={n: make_act_factory(n, {"path": p, "decentral": {"include_partner": True}, "standstill": True})
                    for n, p in POL.items()})


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def _episode(job):
    name, i = job
    from copush.env import CoPushEnv
    if "env" not in _W:
        _W["env"] = CoPushEnv(_W["cfg"], split="eval")
    env, s = _W["env"], _W["starts"][i]
    seed = _W["cfg"]["env"]["heldout_seeds"][0] + i
    act = _W["acts"][name](env, seed)
    obs, _ = env.reset(seed=seed, options={"box": s})
    # the noise-free spot, as _place_in_contact computes it, expressed in the box frame of the configured start pose
    box, tg, e = env.cfg["box"], env.cfg["target"], env.ecfg
    b = math.radians(box["yaw"])
    t, n = (math.cos(b), math.sin(b)), (-math.sin(b), math.cos(b))
    side = 1.0 if (tg["x"] - box["x"]) * n[0] + (tg["y"] - box["y"]) * n[1] >= 0 else -1.0
    face = (side * n[0], side * n[1])
    left = (-face[1], face[0])
    sgn = 1.0 if left[0] * t[0] + left[1] * t[1] >= 0 else -1.0
    half = e["contact_spacing"] / 2
    rel, yoff = {}, wrap(math.atan2(face[1], face[0]) - b)
    for d, k in (("duck_a", 1), ("duck_b", -1)):
        wx = -face[0] * e["contact_setback"] + k * sgn * half * t[0]
        wy = -face[1] * e["contact_setback"] + k * sgn * half * t[1]
        rel[d] = (wx * math.cos(b) + wy * math.sin(b), -wx * math.sin(b) + wy * math.cos(b))

    def snap():
        st_ = env.state
        bx, by = st_["box"]["position"][:2]
        by_ = st_["box"]["yaw"]
        c, s_ = math.cos(by_), math.sin(by_)
        row = {"box": [round(bx, 5), round(by, 5)], "d": round(st_["box_to_target"], 5)}
        for d in DUCKS:
            ix, iy = bx + c * rel[d][0] - s_ * rel[d][1], by + s_ * rel[d][0] + c * rel[d][1]
            px, py = st_[d]["position"][:2]
            row[d] = [round(math.degrees(wrap(st_[d]["yaw"] - (by_ + yoff))), 3), round(math.hypot(px - ix, py - iy), 5)]
        return row

    rows, holds = [snap()], []
    both = 0
    while True:
        obs, _, te, tr, info = env.step(act(obs))
        ha, hb = env.hold["duck_a"], env.hold["duck_b"]
        both += ha and hb
        r = snap()
        r["hold"] = [int(ha), int(hb)]
        rows.append(r)
        if te or tr:
            break
    es = info["episode_stats"]
    return {"policy": name, "id": s["id"], "i": i, "reason": es["reason"], "steps": es["steps"],
            "both_hold_steps": int(both), "rows": rows}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    starts = 200
    if "--report-only" in sys.argv:                                   # rebuild report.md from a saved episodes.json
        eps = json.load(open(os.path.join(OUT, "episodes.json")))["episodes"]
    else:
        jobs = [(n, i) for n in POL for i in range(starts)]
        with Pool(8, initializer=_init) as p:
            eps = p.map(_episode, jobs, chunksize=5)
    ref = json.load(open(REF))["episodes"]
    mism = []
    for e in eps:
        r = ref[e["policy"]][e["i"]]
        if (r["reason"], r["steps"], r["both_hold_steps"]) != (e["reason"], e["steps"], e["both_hold_steps"]):
            mism.append((e["policy"], e["i"], (r["reason"], r["steps"], r["both_hold_steps"]),
                         (e["reason"], e["steps"], e["both_hold_steps"])))
    json.dump({"config": CFG, "test_set": TS, "policies": POL, "mismatches": mism, "episodes": eps},
              open(os.path.join(OUT, "episodes.json"), "w"))

    L = ["# Night 5, L2 set: duck placement over the first 10 steps, and where stalled episodes stop", "",
         f"Policies l2_s1 and l2_s2 (night 5 L2 training), {starts} L2 starts each, deterministic, replayed exactly as the "
         f"night 5 evaluation. Replay check against `{REF}` (reason, steps, both-held steps): "
         f"{len(eps) - len(mism)} of {len(eps)} episodes identical.", "",
         "Errors are against each duck's noise-free spot on the box (setback 9.5 cm behind the box centre on the push side, "
         "10 cm either side along the box, facing the push direction), fixed in the box frame and moved with the box. Step 0 "
         "is the state the policy sees first (after settling, before any action); each step is 0.2 s.", ""]

    # ── first 10 steps ──
    keep = [e for e in eps if len(e["rows"]) > FIRST]
    L += [f"## Steps 0 to {FIRST} ({len(keep)} episodes that last longer than {FIRST} steps)", ""]
    for qty, k, unit, scale in (("heading error", 0, "deg", 1.0), ("position error", 1, "cm", 100.0)):
        L += [f"**{qty.capitalize()}** (absolute, mean over episodes, {unit})", "",
              "| duck | start group (by step-0 error) | n | " + " | ".join(f"s{t}" for t in range(FIRST + 1)) + " | change 0 to 10 |",
              "|---|---|---|" + "---|" * (FIRST + 2)]
        for d in DUCKS:
            e0 = sorted(keep, key=lambda e: abs(e["rows"][0][d][k]))
            m = len(e0) // 3
            for g, grp in (("large (top third)", e0[-m:]), ("middle third", e0[m:-m]), ("small (bottom third)", e0[:m])):
                c = [st.mean(abs(e["rows"][t][d][k]) * scale for e in grp) for t in range(FIRST + 1)]
                L.append(f"| {d[-1].upper()} | {g} | {len(grp)} | " + " | ".join(f"{x:.1f}" for x in c) +
                         f" | {c[-1] - c[0]:+.1f} ({100 * (c[-1] - c[0]) / c[0]:+.0f}%) |")
        L.append("")
    disp = [st.mean(100 * math.dist(e["rows"][t]["box"], e["rows"][0]["box"]) for e in keep) for t in range(FIRST + 1)]
    prog = [st.mean(100 * (e["rows"][0]["d"] - e["rows"][t]["d"]) for e in keep) for t in range(FIRST + 1)]
    d0 = st.mean(100 * e["rows"][0]["d"] for e in keep)
    hold = [st.mean(sum(e["rows"][t]["hold"]) for e in keep) for t in range(1, FIRST + 1)]
    L += ["**Box over the same steps** (mean over episodes)", "",
          "| | " + " | ".join(f"s{t}" for t in range(FIRST + 1)) + " |", "|---|" + "---|" * (FIRST + 1),
          "| box displacement from step 0 (cm) | " + " | ".join(f"{x:.1f}" for x in disp) + " |",
          "| box progress toward the target (cm) | " + " | ".join(f"{x:.1f}" for x in prog) + " |",
          "| ducks held this step (of 2) | - | " + " | ".join(f"{x:.2f}" for x in hold) + " |", "",
          f"Mean starting distance from the box centre to the target centre: {d0:.1f} cm.", ""]

    # ── stalled failures ──
    idle = [e for e in eps if e["reason"] == "timeout" and e["both_hold_steps"] / max(1, e["steps"]) >= BOTH_IDLE]
    L += [f"## Where the both-idle failures stop ({len(idle)} episodes)", "",
          "Both-idle failure: a time-out with both ducks held on 30% or more of the steps (the night 5 SUMMARY's rule). "
          "Stop step: the step after the last one with box progress toward the target of at least the threshold; from there "
          "to the end of the episode every step's progress is below it. Covered: the share of the starting distance gone "
          "by the stop step.", ""]
    rows = []
    for thr in STOP_M:
        per = []
        for e in idle:
            ds = [r["d"] for r in e["rows"]]
            last = max([t for t in range(1, len(ds)) if ds[t - 1] - ds[t] >= thr], default=0)
            per.append({"policy": e["policy"], "id": e["id"], "stop": last, "frac": last / e["steps"],
                        "d0": ds[0], "dstop": ds[last], "dend": ds[-1], "covered": 1 - ds[last] / ds[0]})
        rows.append((thr, per))
    L += ["| threshold (cm per step) | stop step, median (range) | stop as share of the episode, median | "
          "distance at start, median (cm) | distance at stop, median (cm) | share of the start distance covered, median | "
          "stopped in the first half of the episode |", "|---|---|---|---|---|---|---|"]
    for thr, per in rows:
        s_ = [p["stop"] for p in per]
        L.append(f"| {100 * thr:g} | {st.median(s_):.0f} ({min(s_)} to {max(s_)}) | {st.median(p['frac'] for p in per):.0%} | "
                 f"{100 * st.median(p['d0'] for p in per):.1f} | {100 * st.median(p['dstop'] for p in per):.1f} | "
                 f"{st.median(p['covered'] for p in per):.0%} | {sum(p['frac'] < 0.5 for p in per)} of {len(per)} |")
    per = dict(rows)[0.005]
    L += ["", "**Each episode, 0.5 cm threshold** (sorted by stop step)", "",
          "| policy | start | stop step | stop share | distance at start (cm) | at stop (cm) | at the end (cm) | covered |",
          "|---|---|---|---|---|---|---|---|"]
    for p in sorted(per, key=lambda p: p["stop"]):
        L.append(f"| {p['policy']} | {p['id']} | {p['stop']} | {p['frac']:.0%} | {100 * p['d0']:.1f} | "
                 f"{100 * p['dstop']:.1f} | {100 * p['dend']:.1f} | {p['covered']:.0%} |")
    from copush.env import CoPushEnv
    from copush.experiments import load_stage
    tg = CoPushEnv(load_stage(CFG)[1], split="eval").cfg["target"]       # after the layout override, fixed for all starts
    a = math.radians(tg["yaw"])
    outside = []
    for e in idle:
        dx, dy = e["rows"][-1]["box"][0] - tg["x"], e["rows"][-1]["box"][1] - tg["y"]
        lx, ly = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
        outside.append(100 * math.hypot(max(abs(lx) - tg["size"][0] / 2, 0), max(abs(ly) - tg["size"][1] / 2, 0)))
    cnt = lambda lo, hi: sum(lo <= x < hi for x in outside)  # noqa: E731
    L += ["", "## How far outside the target the both-idle failures end", "",
          f"Box centre at the last step against the {100 * tg['size'][0]:g} x {100 * tg['size'][1]:g} cm target rectangle "
          "(position only; the box's yaw is not recorded here, so the yaw part of the success test is not checked).", "",
          f"| box centre at the end | episodes (of {len(outside)}) |", "|---|---|",
          f"| inside the target (fails on yaw or the 1 s hold) | {cnt(0, 1e-9)} |",
          f"| outside by under 2 cm | {cnt(1e-9, 2)} |", f"| outside by 2 to 5 cm | {cnt(2, 5)} |",
          f"| outside by 5 to 10 cm | {cnt(5, 10)} |", f"| outside by 10 cm or more | {cnt(10, 1e9)} |", "",
          "Median distance outside the target, over the episodes that end outside: "
          f"{st.median([x for x in outside if x > 0]):.1f} cm."]
    hold_by_side = {}
    for e in keep:
        side = ref[e["policy"]][e["i"]]["side"]
        hold_by_side.setdefault(side, []).append(e)
    L += ["", "## Duck B's hold rate by start type (steps 1 to 10)", "",
          "| start type | n | duck A held | duck B held | B's heading error, step 0 to 10 (deg) |", "|---|---|---|---|---|"]
    for side in ("> +15", "-15 to +15", "< -15"):
        g = hold_by_side.get(side, [])
        h = [st.mean(sum(r["hold"][k] for r in e["rows"][1:FIRST + 1]) / FIRST for e in g) for k in (0, 1)]
        L.append(f"| {side} deg | {len(g)} | {h[0]:.0%} | {h[1]:.0%} | "
                 f"{st.mean(abs(e['rows'][0]['duck_b'][0]) for e in g):.1f} to "
                 f"{st.mean(abs(e['rows'][FIRST]['duck_b'][0]) for e in g):.1f} |")
    json.dump({str(t): per_ for t, per_ in rows}, open(os.path.join(OUT, "stops.json"), "w"), indent=1)
    open(os.path.join(OUT, "report.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
