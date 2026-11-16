#!/usr/bin/env python3
"""D2 steering: success with 95% intervals, pivot behavior and reward-hacking checks from results/comparison.json.

    scripts/rl.sh experiments/d2-steering/make_report.py     # writes results/steering_report.md

Two policies, one episode per start of stage1_large (200 starts): `d2_reference` (D2 stage 1, no stand-still action)
and `run1_standstill`. A "pivot" is a stretch of 3 or more steps in which exactly one duck is held on velstand (the
stand-still action) while the other keeps working; hold state is read from the env at every step.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts", "rl"))
from ci_report import mcnemar_p, mean_ci, wilson, won  # noqa: E402

R = json.load(open(os.path.join(HERE, "results", "comparison.json")))
EP, WALL = R["episodes"], R.get("wall_s", {})
REF, RUN = "d2_reference", "run1_standstill"
SIDES = ("< -15", "-15 to +15", "> +15")
N = len(EP[REF])
PIVOT_RUN = 3


def pct(x):
    return f"{100 * x:.0f}%"


def rate(k, n):
    lo, hi = wilson(k, n)
    return f"{pct(k / n)} ({pct(lo)} to {pct(hi)})" if n else "n/a"


def succ(rows):
    return sum(r["reason"] == "success" for r in rows)


def paired(idx):
    d = [won(EP[RUN][i]) - won(EP[REF][i]) for i in idx]
    m, h = mean_ci(d)
    p = mcnemar_p(sum(v > 0 for v in d), sum(v < 0 for v in d))
    verdict = "up" if (m - h > 0 and p < 0.05) else ("down" if (m + h < 0 and p < 0.05) else "no measurable difference")
    return m, h, p, verdict


md = [f"# D2 steering, run 1 (stand-still action): evaluation on {N} held-out starts (stage1_large)", "",
      "One deterministic episode per start, 95% intervals (Wilson for rates, paired normal interval and exact McNemar test "
      "for differences between the two policies on the same starts).", "",
      "## 1. Success", "", "| policy | overall | " + " | ".join(f"{s} deg" for s in SIDES) + " |", "|---|---|---|---|---|"]
for name in (REF, RUN):
    cells = []
    for s in SIDES:
        rows = [e for e in EP[name] if e["side"] == s]
        cells.append(rate(succ(rows), len(rows)) + f" of {len(rows)}")
    md.append(f"| {name} | {rate(succ(EP[name]), N)} | " + " | ".join(cells) + " |")
md += ["", "Run 1 minus the reference (percentage points, paired):", "",
       "| where | difference | 95% interval | McNemar p | verdict |", "|---|---|---|---|---|"]
for label, idx in [("overall", list(range(N)))] + [(f"side {s} deg", [i for i, e in enumerate(EP[REF]) if e["side"] == s]) for s in SIDES]:
    m, h, p, v = paired(idx)
    md.append(f"| {label} (n={len(idx)}) | {100 * m:+.1f} | {100 * (m - h):+.1f} to {100 * (m + h):+.1f} | {p:.3f} | {v} |")

# pivot behavior on the long-turn side
long_idx = [i for i, e in enumerate(EP[REF]) if e["side"] == "> +15"]
md += ["", "## 2. Pivot behavior on the long-turn starts (box turned more than +15 degrees)", "",
       f"A pivot episode has a run of at least {PIVOT_RUN} steps with exactly one duck held while the other works. "
       "Rotation is the box's turn toward the needed direction during the steps with exactly one duck held.", "",
       "| policy | episodes with a pivot | won, pivot episodes | won, no pivot | mean steps with one duck held (pivot episodes) | mean box rotation during those steps (deg) | A holds alone | B holds alone |",
       "|---|---|---|---|---|---|---|---|"]
for name in (REF, RUN):
    rows = [EP[name][i] for i in long_idx]
    piv = [r for r in rows if r["max_pivot_run"] >= PIVOT_RUN]
    non = [r for r in rows if r["max_pivot_run"] < PIVOT_RUN]
    a_alone, b_alone = sum(r["hold_a_alone"] for r in rows), sum(r["hold_b_alone"] for r in rows)
    one = sum(r["one_hold_steps"] for r in piv)
    rot = sum(r["rot_one_hold_deg"] for r in piv)
    md.append(f"| {name} | {rate(len(piv), len(rows))} of {len(rows)} | {succ(piv)}/{len(piv)} | {succ(non)}/{len(non)} | "
              f"{one / len(piv):.1f} | {rot / len(piv):+.1f} | {a_alone} steps | {b_alone} steps |" if piv else
              f"| {name} | 0 of {len(rows)} | n/a | {succ(non)}/{len(non)} | n/a | n/a | {a_alone} steps | {b_alone} steps |")
rows_all = EP[RUN]
piv_all = sum(r["max_pivot_run"] >= PIVOT_RUN for r in rows_all)
md += ["", f"On all {N} starts, run 1 has a pivot in {piv_all} episodes ({pct(piv_all / N)}); the reference in "
       f"{sum(r['max_pivot_run'] >= PIVOT_RUN for r in EP[REF])}."]

# reward hacking checks
md += ["", "## 3. Reward-hacking and behavior checks (all 200 starts)", "",
       "A duck is a *permanent holder* in an episode when it is held on 80% or more of the steps; *both idle* is an episode in which "
       "both ducks are held on 30% or more of the steps.", "",
       "| policy | permanent holder, duck A | permanent holder, duck B | both idle | idle share (commanded below 0.05 m/s) | held share, A / B | overshoots | time-outs | falls | box lost | push share A | lazy duck | mean steps |",
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for name in (REF, RUN):
    rows = EP[name]
    pa = sum(r["hold_a_frac"] >= 0.8 for r in rows)
    pb = sum(r["hold_b_frac"] >= 0.8 for r in rows)
    bi = sum(r["both_hold_steps"] / max(1, r["steps"]) >= 0.3 for r in rows)
    idle, ih = mean_ci([r["idle_frac"] for r in rows])
    ha = sum(r["hold_a_frac"] for r in rows) / N
    hb = sum(r["hold_b_frac"] for r in rows) / N
    md.append(f"| {name} | {pa} | {pb} | {bi} | {pct(idle)} (+-{100 * ih:.0f}) | {pct(ha)} / {pct(hb)} | "
              f"{rate(sum(bool(r['overshoot']) for r in rows), N)} | {rate(sum(r['reason'] == 'timeout' for r in rows), N)} | "
              f"{sum(r['fell'] for r in rows)} | {sum(r['box_lost'] for r in rows)} | "
              f"{pct(sum(r['push_share_a'] for r in rows) / N)} | {sum(r['lazy'] for r in rows)} | "
              f"{sum(r['steps'] for r in rows) / N:.0f} |")
if WALL:
    md += ["", "## 4. Wall time (8 worker processes per policy)", "", "| policy | wall time |", "|---|---|"]
    md += [f"| {n} | {s:.0f} s |" for n, s in WALL.items()]
open(os.path.join(HERE, "results", "steering_report.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))
