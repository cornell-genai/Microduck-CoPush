#!/usr/bin/env python3
"""Cooperative success for the rendezvous pipeline and the L2-s2 push policy (evaluation only; copush.cooperation).

    scripts/rl.sh scripts/rl/cooperation_report.py push                 # L2-s2 on the clean, noisy, L1 and L2 sets
    scripts/rl.sh scripts/rl/cooperation_report.py report               # tables and paired comparisons

push    reruns the night 5 L2-s2 push policy on its four 200-start sets exactly as scripts/rl/docking_sweep.py's baseline
        (same starts, seeds 10000 + i, deterministic) and records each duck's contact impulse and push impulse. Every
        episode is checked (ending, steps, push share) against the saved night 5 evaluation.
report  reads the rendezvous pipeline evaluations in --runs (scripts/rl/rendezvous_eval.py eval on rendezvous_large.json,
        rerun with the contact impulse recorded), checks each against the original per-episode results (docked, push
        ending, push steps, push share), and writes cooperative.json / cooperative.md to --out: task success and
        cooperative success for both measures, the threshold sweep, how often the measures disagree (with examples),
        and paired comparisons on the same starts (seeds averaged per start; 95% interval of the mean difference).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts", "rl")]
os.chdir(ROOT)

from copush import cooperation as C  # noqa: E402

OUT = "experiments/d2-rendezvous/cooperative-success"
RUNS = "runs/coop-recompute"
# name: (rerun folder under --runs, the original per-episode results it must reproduce, label)
PIPELINES = {
    "scripted": ("scripted", "experiments/d2-rendezvous/scripted-baseline/results.json", "scripted rendezvous"),
    "r6_s1": ("r6_s1", "runs/d2-rendezvous-r6-dock-payout/reselect/test_s1_final/results.json", "r6 seed 1 (official)"),
    "r6_s2": ("r6_s2", "runs/d2-rendezvous-r6-dock-payout/reselect/test_s2_final/results.json", "r6 seed 2"),
    "r7_s1": ("r7_s1_pick", "runs/d2-rendezvous-r7-long-payout/eval_s1_pick/results.json", "r7 seed 1 (check-set pick)"),
    "r7_s2": ("r7_s2_pick", "runs/d2-rendezvous-r7-long-payout/eval_s2_pick/results.json", "r7 seed 2 (check-set pick)"),
}
PAIRS = (("r6", ("r6_s1", "r6_s2"), "scripted", ("scripted",)), ("r6", ("r6_s1", "r6_s2"), "r7", ("r7_s1", "r7_s2")),
         ("r7", ("r7_s1", "r7_s2"), "scripted", ("scripted",)))
EARLIER_PUSH_20 = {"scripted": 0.365, "r6_s1": 0.480, "r6_s2": 0.460}     # along the line, 20% cutoff (reported before)


def cmd_push(a) -> int:
    import docking_sweep as D
    jobs = [("baseline", s, i) for s in D.SETS for i in range(a.starts)]
    with Pool(a.workers, initializer=D._init) as p:
        eps = p.map(D._episode, jobs, chunksize=4)
    res = {s: sorted((e for e in eps if e["set"] == s), key=lambda e: e["i"]) for s in D.SETS}
    ver = D.verify_baseline({"baseline": res}, a.starts)
    out = os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)
    doc = {"policy": D.POLICY, "sets": {s: D.SETS[s][0] for s in D.SETS}, "starts_per_set": a.starts,
           "night5_check": ver,
           "episodes": {s: [{"i": e["i"], "reason": e["reason"], "success": e["reason"] == "success", "steps": e["steps"],
                             "push_share_a": None if e["push_a"] is None else round(e["push_a"], 4),
                             "contact_share_a": None if e["contact_a"] is None else round(e["contact_a"], 4),
                             "contact_impulse": {d: round(v, 4) for d, v in e["contact_impulse"].items()},
                             "push_impulse": {d: round(v, 4) for d, v in e["push_impulse"].items()},
                             "cooperative_threshold": e["cooperative_threshold"]} for e in res[s]] for s in D.SETS}}
    json.dump(doc, open(os.path.join(out, "push_l2s2.json"), "w"), separators=(",", ":"))
    for s, v in ver.items():
        print(f"{s}: {v['checked'] - len(v['different'])}/{v['checked']} episodes identical to the saved night 5 evaluation")
    return 1 if any(v["different"] for v in ver.values()) else 0


def _coop(e: dict, measure: str, t: float) -> float:
    return float(C.is_cooperative(e["success"], e.get(measure + "_share_a"), t))


def paired(eps: dict, a: tuple, b: tuple, value) -> dict:
    """Mean over starts of (mean over a's seeds - mean over b's seeds) of value(episode), 95% interval of that mean,
    and each a-seed minus each b-seed (matched by position when both have two seeds, else against b's only one)."""
    from ci_report import mean_ci
    n = len(eps[a[0]])
    d = [sum(value(eps[k][i]) for k in a) / len(a) - sum(value(eps[k][i]) for k in b) / len(b) for i in range(n)]
    m, h = mean_ci(d)
    per = []
    for j, k in enumerate(a):
        kb = b[j] if len(b) == len(a) else b[0]
        dj = [value(eps[k][i]) - value(eps[kb][i]) for i in range(n)]
        mj, hj = mean_ci(dj)
        per.append({"a": k, "b": kb, "diff": mj, "ci": [mj - hj, mj + hj]})
    excl = (m - h > 0) or (m + h < 0)
    same = all((p["diff"] > 0) == (m > 0) and p["diff"] != 0 for p in per)
    return {"diff": m, "ci": [m - h, m + h], "per_seed": per, "interval_excludes_0": excl, "seeds_same_side": same,
            "measurable": bool(excl and same)}


def _pp(p: dict) -> str:
    return (f"{100 * p['diff']:+.1f} ({100 * p['ci'][0]:+.1f} to {100 * p['ci'][1]:+.1f}); seeds "
            + ", ".join(f"{100 * s['diff']:+.1f}" for s in p["per_seed"])
            + ("; **measurable**" if p["measurable"] else "; no measurable difference"))


def cmd_report(a) -> int:
    out = os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)
    eps, repro, labels = {}, {}, {}
    for name, (sub, orig, label) in PIPELINES.items():
        new = json.load(open(os.path.join(ROOT, a.runs, sub, "results.json")))
        old = json.load(open(os.path.join(ROOT, orig)))["episodes"]
        e = [dict(x, success=x["push_success"]) for x in new["episodes"]]
        keys = ("arrived", "push_reason", "push_steps", "push_share_a")
        bad = [x["i"] for x, y in zip(e, old) if any(x[k] != y[k] for k in keys)]
        repro[name] = {"original": orig, "rendezvous": new["rendezvous"], "checked": len(old), "fields": list(keys), "different": bad}
        eps[name], labels[name] = e, label
        json.dump({"rendezvous": new["rendezvous"], "push": new["push"], "set": new["set"], "n": new["n"],
                   "episodes": [{k: x[k] for k in ("i", "id", "kind", "arrived", "push_reason", "push_success", "push_steps",
                                                    "push_share_a", "contact_share_a", "contact_impulse", "push_impulse")}
                                for x in e]},
                  open(os.path.join(out, f"pipeline_{name}.json"), "w"), separators=(",", ":"))
    push = json.load(open(os.path.join(out, "push_l2s2.json")))
    th = C.threshold_of(__import__("copush.config", fromlist=["load_config"]).load_config())
    for s, v in push["episodes"].items():
        eps["l2s2_" + s], labels["l2s2_" + s] = v, f"L2-s2 push policy, {s} set"
    summ = {k: C.summarize(v, th) for k, v in eps.items()}
    earlier = {k: {"reported": r, "now": summ[k]["sweep"]["push"]["0.20"]["rate"],
                   "same": abs(summ[k]["sweep"]["push"]["0.20"]["rate"] - r) < 5e-4} for k, r in EARLIER_PUSH_20.items()}
    pairs = {}
    for an, ak, bn, bk in PAIRS:
        key = f"{an} minus {bn}"
        pairs[key] = {"task": paired(eps, ak, bk, lambda e: float(e["success"]))}
        for m in C.MEASURES:
            for t in C.SWEEP:
                pairs[key][f"{m}@{t:.2f}"] = paired(eps, ak, bk, lambda e, m=m, t=t: _coop(e, m, t))
    examples = {}
    for k, v in eps.items():
        dis = [e for e in v if e["success"] and _coop(e, "contact", th) != _coop(e, "push", th)]
        examples[k] = [{"i": e["i"], "contact_share_a": e["contact_share_a"], "push_share_a": e["push_share_a"],
                        "contact_impulse": e["contact_impulse"], "push_impulse": e["push_impulse"]} for e in dis]
    doc = {"threshold": th, "summary": summ, "reproduction": repro, "night5_check": push["night5_check"],
           "earlier_along_the_line_20": earlier, "paired": pairs, "disagreements": examples}
    json.dump(doc, open(os.path.join(out, "cooperative.json"), "w"), indent=1)

    L = ["# Cooperative success: the rendezvous pipeline and the L2-s2 push policy", "",
         "Written by `scripts/rl/cooperation_report.py report`. 200 starts per row, deterministic, per-start seeds 10000 + i. "
         "Pipeline rows: `experiments/test_sets/rendezvous_large.json`, rendezvous then the frozen L2-s2 push policy. "
         "L2-s2 rows: the ducks start in contact with the box.", ""]
    L += C.report_lines({labels[k]: s for k, s in summ.items()})
    L += ["", "## Reproduction", "",
          "Each pipeline was rerun on its original starts and seeds because the saved results did not hold the contact "
          "impulse. Episodes identical to the original results (docked, push ending, push steps, push share):", ""]
    L += [f"- {labels[k]}: {r['checked'] - len(r['different'])} of {r['checked']} (`{r['original']}`)" for k, r in repro.items()]
    L += [f"- L2-s2, {s} set: {v['checked'] - len(v['different'])} of {v['checked']} identical to the saved night 5 evaluation "
          "(ending, steps, push share)" for s, v in push["night5_check"].items()]
    L += ["", "Along-the-line measure at a 20% cutoff, against the numbers reported earlier:", ""]
    L += [f"- {labels[k]}: {100 * v['now']:.1f}% now, {100 * v['reported']:.1f}% before ({'same' if v['same'] else 'DIFFERENT'})"
          for k, v in earlier.items()]
    L += ["", "## Paired comparisons (same 200 starts, seeds averaged per start, percentage points)", "",
          "Mean per-start difference with a 95% interval; then each seed's own difference. Measurable = the interval "
          "excludes 0 and both seeds are on the same side.", ""]
    for key, p in pairs.items():
        L += [f"**{key}**", "", "| | difference |", "|---|---|", f"| task success | {_pp(p['task'])} |"]
        for m, lab in (("contact", "contact impulse"), ("push", "along the line")):
            L += [f"| cooperative success, {lab}, {round(100 * t)}% | {_pp(p[f'{m}@{t:.2f}'])} |" for t in C.SWEEP]
        L += [""]
    L += ["## Where the two measures disagree", "",
          f"Task successes that one measure calls cooperative at {round(100 * th)}% and the other does not "
          "(duck A's share by each measure; impulses in N s as A / B):", "",
          "| | start | contact share A | along-the-line share A | contact impulse A / B | push impulse A / B |", "|---|---|---|---|---|---|"]
    for k, ex in examples.items():
        for e in ex[:a.examples]:
            ci, pi = e["contact_impulse"], e["push_impulse"]
            L.append(f"| {labels[k]} | {e['i']} | {100 * e['contact_share_a']:.0f}% | {100 * e['push_share_a']:.0f}% | "
                     f"{ci['duck_a']:.1f} / {ci['duck_b']:.1f} | {pi['duck_a']:.1f} / {pi['duck_b']:.1f} |")
    open(os.path.join(out, "cooperative.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("push")
    p.add_argument("--starts", type=int, default=200)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--out", default=OUT)
    r = sub.add_parser("report")
    r.add_argument("--runs", default=RUNS)
    r.add_argument("--out", default=OUT)
    r.add_argument("--examples", type=int, default=4)
    a = ap.parse_args()
    return cmd_push(a) if a.cmd == "push" else cmd_report(a)


if __name__ == "__main__":
    sys.exit(main())
