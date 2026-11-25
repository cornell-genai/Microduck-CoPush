#!/usr/bin/env python3
"""Docking-spot sweep (evaluation only, no training): the night 5 L2-s2 push policy under different duck placements.

    scripts/rl.sh scripts/rl/docking_sweep.py                       # all configs x 4 sets x 200 starts
    scripts/rl.sh scripts/rl/docking_sweep.py --starts 10 --out runs/docking-dry     # quick check, writes elsewhere

Each placement config sets, per duck, its sideways offset from the box centre along the box's long axis (A on the left of
the push direction, B on the right) and its setback (distance behind the box centre on the push side). The start noise of
the eval set (heading, spacing, setback) is added on top exactly as copush.env does: the spacing noise is split half to each
duck's offset, the setback noise is per duck. copush/env.py is untouched: the env is subclassed here.

Evaluation as in the night 5 evaluation: policy runs per duck with @partner and the stand-still action, deterministic, 100-step
limit, per-start seed heldout_seeds[0] + i (10000 + i), the set's own env config. Success is the env's: box centre inside the
target, yaw error <= 15 deg, both ducks up, held 1 s. The baseline config is checked episode by episode (reason, steps,
push share) against the saved night 5 evaluation of the same policy; any difference stops the run.

Writes results.json (per-episode arrays and summaries) and results.md to --out.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts", "rl")]
os.chdir(ROOT)

POLICY = "runs/d2-steering-night5/l2-s2/model.zip"
SETS = {"clean": ("experiments/test_sets/stage1_large.json", "experiments/stage1-random-box-pose/config.yaml"),
        "noisy": ("experiments/test_sets/stage1_noisy_large.json", "experiments/d2-steering/noisy-sets/config.yaml"),
        "L1": ("experiments/test_sets/stage1_L1_large.json", "experiments/d2-steering/night5/sets/L1/config.yaml"),
        "L2": ("experiments/test_sets/stage1_L2_large.json", "experiments/d2-steering/night5/sets/L2/config.yaml")}
REF = {"clean": "eval_clean", "noisy": "eval_noisy", "L1": "eval_L1", "L2": "eval_L2"}
REF_DIR, REF_POLICY = "runs/d2-steering/night5/results", "l2_s2"
# a_off / b_off: sideways offset from the box centre (m); a_back / b_back: setback (m). Spacing = a_off + b_off = 0.20 in all.
CONFIGS = {
    "baseline": dict(a_off=0.10, b_off=0.10, a_back=0.095, b_back=0.095,
                     label="BASELINE: symmetric, spacing 0.10 each side, setback 0.095"),
    "B-closer": dict(a_off=0.13, b_off=0.07, a_back=0.095, b_back=0.095,
                     label="B-closer: B 0.07, A 0.13, setback 0.095"),
    "B-closer+A-back": dict(a_off=0.13, b_off=0.07, a_back=0.11, b_back=0.08,
                            label="B-closer + A further back: B 0.07 / setback 0.08, A 0.13 / setback 0.11"),
    "B-tight": dict(a_off=0.15, b_off=0.05, a_back=0.095, b_back=0.095,
                    label="B-tight: B 0.05, A 0.15, setback 0.095"),
    "A-back": dict(a_off=0.10, b_off=0.10, a_back=0.11, b_back=0.08,
                   label="A further back only: spacing 0.10 each side, A setback 0.11, B setback 0.08"),
}
FAILS = ("timeout", "fall", "box_lost", "box_tipped")
_W: dict = {}


def make_env_class():
    from copush.env import DUCKS, CoPushEnv
    return make_env_subclass(CoPushEnv, DUCKS)


def placed_spots(placement: dict, box: dict, target: dict, noise=None) -> dict:
    """Per-duck docking spots {duck: (x, y, yaw_deg)} from copush.env.docking_spots. docking_spots places both ducks
    symmetrically (offset spacing/2 each side, one setback), so each duck is taken from its own call: duck A from
    spacing 2 * a_off and setback a_back, duck B from 2 * b_off and b_back. The eval set's start noise goes in unchanged
    (spacing noise split half to each duck, per-duck setback and heading noise), as copush.env applies it."""
    from copush.env import docking_spots
    out = {}
    for duck, key in (("duck_a", "a"), ("duck_b", "b")):
        spots = docking_spots(box, target, placement[key + "_back"], 2 * placement[key + "_off"], noise)
        out[duck] = spots[duck]
    return out


def make_env_subclass(base, ducks):
    class DockEnv(base):
        placement = None

        def _place_in_contact(self, noise=None):
            """copush.env's own placement (docking_spots) with per-duck sideways offsets and setbacks (placement dict)."""
            for duck, (x, y, yaw) in placed_spots(self.placement, self.cfg["box"], self.cfg["target"], noise).items():
                self.cfg[duck].update({"x": x, "y": y, "yaw": yaw})
    assert ducks
    return DockEnv


def _init():
    import torch
    torch.set_num_threads(1)
    from copush.experiments import load_stage, load_test_set
    from test_set import make_act_factory
    _W["Env"] = make_env_class()
    _W["act"] = make_act_factory("l2_s2", {"path": POLICY, "decentral": {"include_partner": True}, "standstill": True})
    _W["cfg"], _W["starts"], _W["env"] = {}, {}, {}
    for s, (ts, cp) in SETS.items():
        _, cfg = load_stage(cp)
        cfg["env"]["stand_still"] = {**cfg["env"]["stand_still"], "enabled": True}
        _W["cfg"][s] = cfg
        _W["starts"][s] = load_test_set(ts)["starts"]


def _episode(job):
    cname, sname, i = job
    if sname not in _W["env"]:
        _W["env"][sname] = _W["Env"](_W["cfg"][sname], split="eval")
    env = _W["env"][sname]
    env.placement = CONFIGS[cname]
    seed = _W["cfg"][sname]["env"]["heldout_seeds"][0] + i
    act = _W["act"](env, seed)
    d0, r0 = env.start_draws, env.start_resamples
    obs, _ = env.reset(seed=seed, options={"box": _W["starts"][sname][i]})
    draws, resamples = env.start_draws - d0, env.start_resamples - r0
    while True:
        obs, _, te, tr, info = env.step(act(obs))
        if te or tr:
            break
    es = info["episode_stats"]
    sh = es["push_share"]["duck_a"]
    return {"cfg": cname, "set": sname, "i": i, "reason": es["reason"], "steps": int(es["steps"]),
            "push_a": None if sh != sh else float(sh), "draws": draws, "resamples": resamples}


def mean(x):
    return sum(x) / len(x) if x else float("nan")


def summarize(eps):
    from ci_report import wilson
    n = len(eps)
    ok = [e for e in eps if e["reason"] == "success"]
    lo, hi = wilson(len(ok), n)
    sh = [e["push_a"] for e in eps if e["push_a"] is not None]
    shs = [e["push_a"] for e in ok if e["push_a"] is not None]
    draws = sum(e["draws"] for e in eps)
    return {"n": n, "success": len(ok), "rate": len(ok) / n, "ci": [lo, hi],
            "mean_steps_success": mean([e["steps"] for e in ok]), "median_steps_success": sorted(e["steps"] for e in ok)[len(ok) // 2] if ok else None,
            "push_share_a": mean(sh), "push_share_a_success": mean(shs),
            "one_duck_over_80_success": sum(1 for e in ok if e["push_a"] is not None and (e["push_a"] > .8 or e["push_a"] < .2)),
            "reasons": {r: sum(e["reason"] == r for e in eps) for r in sorted({e["reason"] for e in eps})},
            "redraw_rate": (sum(e["resamples"] for e in eps) / draws) if draws else 0.0}


def paired(cfg_eps, base_eps):
    """cfg minus baseline, per start: mean difference, 95% interval (normal approx on the paired differences), McNemar p."""
    from ci_report import Z, mcnemar_p, mean_ci
    d = [(c["reason"] == "success") - (b["reason"] == "success") for c, b in zip(cfg_eps, base_eps)]
    m, h = mean_ci(d)
    b_only = sum(x == -1 for x in d)
    c_only = sum(x == 1 for x in d)
    return {"diff": m, "ci": [m - h, m + h], "cfg_only": c_only, "base_only": b_only, "mcnemar_p": mcnemar_p(c_only, b_only), "n": len(d), "z": Z}


def verify_baseline(res, n):
    out = {}
    for s in SETS:
        ref = json.load(open(os.path.join(REF_DIR, REF[s], "comparison.json")))["episodes"][REF_POLICY]
        bad = []
        for e in res["baseline"][s][:n]:
            r = ref[e["i"]]
            rp, ep = r["push_share_a"], e["push_a"]
            same_push = (rp != rp and ep is None) or (ep is not None and rp == rp and math.isclose(rp, ep, rel_tol=0, abs_tol=1e-9))
            if (r["reason"], r["steps"]) != (e["reason"], e["steps"]) or not same_push:
                bad.append(e["i"])
        out[s] = {"checked": len(res["baseline"][s][:n]), "different": bad}
    return out


def pct(x):
    return f"{100 * x:.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="experiments/d2-steering/docking-sweep")
    ap.add_argument("--starts", type=int, default=200)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-verify", action="store_true")
    a = ap.parse_args()
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    jobs = [(c, s, i) for s in SETS for c in CONFIGS for i in range(a.starts)]
    with Pool(a.workers, initializer=_init) as p:
        eps = p.map(_episode, jobs, chunksize=4)
    res = {c: {s: sorted((e for e in eps if e["cfg"] == c and e["set"] == s), key=lambda e: e["i"]) for s in SETS} for c in CONFIGS}
    ver = {} if a.no_verify else verify_baseline(res, a.starts)
    bad = sum(len(v["different"]) for v in ver.values())
    summ = {c: {s: summarize(res[c][s]) for s in SETS} for c in CONFIGS}
    for c in CONFIGS:
        summ[c]["ALL"] = summarize([e for s in SETS for e in res[c][s]])
    pair = {c: {s: paired(res[c][s], res["baseline"][s]) for s in SETS} for c in CONFIGS if c != "baseline"}
    for c in pair:
        pair[c]["ALL"] = paired([e for s in SETS for e in res[c][s]], [e for s in SETS for e in res["baseline"][s]])
    best = max(CONFIGS, key=lambda c: summ[c]["ALL"]["rate"])
    doc = {"policy": POLICY, "policy_seed": 2, "starts_per_set": a.starts, "sets": {s: SETS[s] for s in SETS},
           "configs": {c: {k: v for k, v in CONFIGS[c].items()} for c in CONFIGS}, "baseline_check": ver,
           "summary": summ, "paired_vs_baseline": pair, "best_overall": best, "wall_s": round(time.time() - t0, 1),
           "episodes": {c: {s: {"success": [int(e["reason"] == "success") for e in res[c][s]],
                                "reason": [e["reason"] for e in res[c][s]], "steps": [e["steps"] for e in res[c][s]],
                                "push_share_a": [None if e["push_a"] is None else round(e["push_a"], 4) for e in res[c][s]]}
                            for s in SETS} for c in CONFIGS}}
    json.dump(doc, open(os.path.join(out, "results.json"), "w"), separators=(",", ":"))
    L = [f"# Docking sweep: {POLICY}", "",
         f"{a.starts} starts per set, deterministic, 100-step limit, per-start seeds 10000 + i; policy seed 2 only. "
         f"Baseline check against the saved night 5 evaluation (reason, steps, push share): "
         + ("skipped" if a.no_verify else ", ".join(f"{s} {v['checked'] - len(v['different'])}/{v['checked']} identical" for s, v in ver.items())) + ".", "",
         "## Configs", "", "| config | A offset | B offset | A setback | B setback |", "|---|---|---|---|---|"]
    L += [f"| {c} | {CONFIGS[c]['a_off']} | {CONFIGS[c]['b_off']} | {CONFIGS[c]['a_back']} | {CONFIGS[c]['b_back']} |" for c in CONFIGS]
    cols = list(SETS) + ["ALL"]
    L += ["", "## Success rate (95% Wilson interval)", "", "| config | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for c in CONFIGS:
        L.append(f"| {c} | " + " | ".join(f"{pct(summ[c][s]['rate'])} ({pct(summ[c][s]['ci'][0])} to {pct(summ[c][s]['ci'][1])})" for s in cols) + " |")
    L += ["", "## Paired difference from baseline, percentage points (95% interval; starts won only by the config / only by baseline)", "",
          "| config | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for c in pair:
        L.append(f"| {c} | " + " | ".join(
            f"{100 * pair[c][s]['diff']:+.1f} ({100 * pair[c][s]['ci'][0]:+.1f} to {100 * pair[c][s]['ci'][1]:+.1f}; {pair[c][s]['cfg_only']}/{pair[c][s]['base_only']})"
            for s in cols) + " |")
    for key, title in (("mean_steps_success", "Mean steps to success (successful episodes only)"),
                       ("push_share_a", "Duck A's share of the pushing (mean over episodes)"),
                       ("push_share_a_success", "Duck A's share of the pushing (mean over successful episodes)"),
                       ("redraw_rate", "Start redraw rate (draws that failed the start check; 0 when the set has no start noise)")):
        L += ["", f"## {title}", "", "| config | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        for c in CONFIGS:
            L.append(f"| {c} | " + " | ".join((f"{summ[c][s][key]:.1f}" if key == "mean_steps_success" else
                                              pct(summ[c][s][key]) if key == "redraw_rate" or key.startswith("push") else f"{summ[c][s][key]:.2f}")
                                             for s in cols) + " |")
    L += ["", "## Episode endings (count per set; success / time-out / fall / box lost or tipped)", "",
          "| config | " + " | ".join(SETS) + " |", "|---|" + "---|" * len(SETS)]
    for c in CONFIGS:
        cells = []
        for s in SETS:
            r = summ[c][s]["reasons"]
            cells.append(f"{r.get('success', 0)} / {r.get('timeout', 0)} / {r.get('fall', 0)} / {r.get('box_lost', 0) + r.get('box_tipped', 0)}")
        L.append(f"| {c} | " + " | ".join(cells) + " |")
    L += ["", f"Highest overall success (all four sets together): **{best}**. Wall time {doc['wall_s']} s."]
    open(os.path.join(out, "results.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    if bad:
        print(f"\nBASELINE CHECK FAILED: {bad} episodes differ from the saved night 5 evaluation: {ver}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
