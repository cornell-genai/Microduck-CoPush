#!/usr/bin/env python3
"""Old (50-start) against new (200-start) numbers, with 95% intervals, and which earlier claims hold.

    scripts/rl.sh experiments/stage1-reevaluation/make_tables.py        # reads results/comparison.json, writes results/reevaluation.md

The old numbers are the ones recorded in the READMEs from the 50-start test set (experiments/test_sets/stage1.json);
the new ones are one deterministic episode per start on experiments/test_sets/stage1_large.json (200 starts, even in
box angle). Intervals: Wilson for a rate; paired (same starts) normal interval for a difference between two policies;
a t interval across seeds for a group of seeds. A difference whose interval contains 0 is "no measurable difference".
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts", "rl"))
from ci_report import mean_ci, mcnemar_p, wilson, won  # noqa: E402

R = json.load(open(os.path.join(HERE, "results", "comparison.json")))
EP, WALL = R["episodes"], R.get("wall_s", {})
N = len(next(iter(EP.values())))

# successes out of 50 on the 50-start test set, as recorded in the READMEs (superseded by the 200-start numbers)
OLD = {"stage1_central": 30, "central_scratch_s1": 25, "stage1b_A": 36, "stage1b_B": 34, "d1": 30, "d2": 37,
       "d2_distilled_s1": 24, "d2_distilled_s2": 24, "d2_distilled_s3": 29, "pivot_push": 16, "push_steer": 9}
CENTRAL_OLD = [25, 14, 22, 20, 16, 24, 27, 26, 32, 22]          # central from scratch, seeds 1 to 10
D2_OLD = [16, 14, 19, 25, 17, 30, 20, 14, 19, 24]               # D2 from scratch, seeds 1 to 10
for i, k in enumerate(CENTRAL_OLD):
    OLD[f"central_scratch_s{i + 1}"] = k
for i, k in enumerate(D2_OLD):
    OLD[f"d2_scratch_s{i + 1}"] = k
LABEL = {"stage1_central": "stage 1, central (one network, both ducks)", "central_scratch_s1": "01_reference (central from scratch, seed 1)",
         "stage1b_A": "stage 1b A (central, hard starts oversampled)", "stage1b_B": "stage 1b B (central, smaller time penalty)",
         "d1": "D1 (decentralized, own view only)", "d2": "D2 (decentralized, own view + partner)",
         "d2_distilled_s1": "D2 distilled, seed 1 (fixed-start run)", "d2_distilled_s2": "D2 distilled, seed 2",
         "d2_distilled_s3": "D2 distilled, seed 3", "pivot_push": "pivot_push (script)", "push_steer": "push_steer (script)"}
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 12: 2.179,
       15: 2.131, 18: 2.101, 20: 2.086, 25: 2.060, 30: 2.042, 60: 2.0}


def tcrit(df):
    ks = [k for k in T95 if k <= df]
    return T95[max(ks)] if ks else 12.706


def pct(x):
    return f"{100 * x:.0f}%"


def k_of(name):
    return int(sum(map(won, EP[name])))


def new_ci(name):
    k = k_of(name)
    lo, hi = wilson(k, N)
    return f"{pct(k / N)} ({pct(lo)} to {pct(hi)})"


def old_str(name):
    return f"{pct(OLD[name] / 50)} ({OLD[name]}/50)"


def inside(name):
    lo, hi = wilson(k_of(name), N)
    return "yes" if lo <= OLD[name] / 50 <= hi else "**no**"


def paired(a, b, idx=None):
    idx = range(N) if idx is None else idx
    d = [won(EP[a][i]) - won(EP[b][i]) for i in idx]
    m, h = mean_ci(d)
    return m, h


def verdict(m, h, claim_positive=True):
    if m - h > 0:
        return "holds" if claim_positive else "reversed"
    if m + h < 0:
        return "reversed" if claim_positive else "holds"
    return "no measurable difference"


def group(prefix, n=10):
    rates = [k_of(f"{prefix}{s}") / N for s in range(1, n + 1)]
    m = sum(rates) / n
    sd = math.sqrt(sum((r - m) ** 2 for r in rates) / (n - 1))
    return rates, m, sd


md = [f"# Re-evaluation on {N} held-out starts (stage1_large) against the old 50-start numbers", "",
      "One deterministic episode per start. Old = the 50-start test-set number recorded in the READMEs (**superseded**); "
      "new = this evaluation with a Wilson 95% interval. \"Old inside new interval\" says whether the old number was "
      "within what the larger set allows.", "",
      "## 1. Named policies", "",
      "| policy | old, 50 starts (superseded) | new, 200 starts (95% interval) | old inside new interval |", "|---|---|---|---|"]
for name in OLD:
    if name.startswith(("central_scratch_s", "d2_scratch_s")) and name != "central_scratch_s1":
        continue
    md.append(f"| {LABEL.get(name, name)} | {old_str(name)} | **{new_ci(name)}** | {inside(name)} |")

sides = ("< -15", "-15 to +15", "> +15")
md += ["", "Per box-angle side on the 200 starts (successes / starts):", "",
       "| policy | " + " | ".join(f"{s} deg" for s in sides) + " |", "|---|---|---|---|"]
for name in OLD:
    if name.startswith(("central_scratch_s", "d2_scratch_s")) and name != "central_scratch_s1":
        continue
    cells = []
    for s in sides:
        rows = [e for e in EP[name] if e["side"] == s]
        k = sum(e["reason"] == "success" for e in rows)
        lo, hi = wilson(k, len(rows))
        cells.append(f"{k}/{len(rows)} ({pct(k / len(rows))}, {pct(lo)} to {pct(hi)})")
    md.append(f"| {LABEL.get(name, name)} | " + " | ".join(cells) + " |")

md += ["", "## 2. From-scratch policies, 10 seeds each (trained on the fixed start, tested on random starts)", "",
       "| seed | central, old (50) | central, new (200) | D2, old (50) | D2, new (200) |", "|---|---|---|---|---|"]
for s in range(1, 11):
    c, d = f"central_scratch_s{s}", f"d2_scratch_s{s}"
    md.append(f"| {s} | {pct(OLD[c] / 50)} | {new_ci(c)} | {pct(OLD[d] / 50)} | {new_ci(d)} |")
cr, cm, csd = group("central_scratch_s")
dr, dm, dsd = group("d2_scratch_s")
tc = tcrit(9)
ch, dh = tc * csd / math.sqrt(10), tc * dsd / math.sqrt(10)
se = math.sqrt(csd ** 2 / 10 + dsd ** 2 / 10)
dfw = (csd ** 2 / 10 + dsd ** 2 / 10) ** 2 / ((csd ** 2 / 10) ** 2 / 9 + (dsd ** 2 / 10) ** 2 / 9)
gh = tcrit(int(dfw)) * se
old_c, old_d = sum(CENTRAL_OLD) / 500, sum(D2_OLD) / 500
md += ["", "| group (10 seeds) | old mean (50-start rates) | new mean (200 starts), 95% interval across seeds | range across seeds (new) |",
       "|---|---|---|---|",
       f"| central from scratch | {pct(old_c)} | **{pct(cm)}** ({pct(cm - ch)} to {pct(cm + ch)}) | {pct(min(cr))} to {pct(max(cr))} |",
       f"| D2 from scratch | {pct(old_d)} | **{pct(dm)}** ({pct(dm - dh)} to {pct(dm + dh)}) | {pct(min(dr))} to {pct(max(dr))} |",
       "", f"Central minus D2 from scratch: old {100 * (old_c - old_d):+.0f} points; new **{100 * (cm - dm):+.1f} points** "
       f"(95% interval {100 * (cm - dm - gh):+.1f} to {100 * (cm - dm + gh):+.1f}, Welch on the seed rates): "
       f"{verdict(cm - dm, gh)}."]
kr = [k_of(f"d2_distilled_s{s}") / N for s in (1, 2, 3)]
km = sum(kr) / 3
ksd = math.sqrt(sum((r - km) ** 2 for r in kr) / 2)
kh = tcrit(2) * ksd / math.sqrt(3)
md += [f"", f"D2 distilled (3 seeds): old {pct(sum(OLD[f'd2_distilled_s{s}'] for s in (1, 2, 3)) / 150)}; new **{pct(km)}** "
       f"({pct(km - kh)} to {pct(km + kh)} across seeds, a wide interval from only 3 seeds)."]

# (claim, a, b, kind, side): kind "gt" = the old claim says a beats b; "eq" = the old claim says a matches b
claims = [
    ("PPO (stage 1) beats 01_reference (60% against 50%)", "stage1_central", "central_scratch_s1", "gt", None),
    ("PPO (stage 1) beats the best script, pivot_push (60% against 32%)", "stage1_central", "pivot_push", "gt", None),
    ("PPO (stage 1) beats push_steer (60% against 18%)", "stage1_central", "push_steer", "gt", None),
    ("Stage 1b A beats stage 1 (72% against 60%)", "stage1b_A", "stage1_central", "gt", None),
    ("Stage 1b B beats stage 1 (68% against 60%)", "stage1b_B", "stage1_central", "gt", None),
    ("D2 beats the central stage 1 policy (74% against 60%)", "d2", "stage1_central", "gt", None),
    ("Control for that: stage 1b A (central, also 1M extra steps) is as good as D2", "stage1b_A", "d2", "eq", None),
    ("D2 beats D1: seeing the partner helps (74% against 60%)", "d2", "d1", "gt", None),
    ("D1 matches the central stage 1 policy (60% against 60%)", "d1", "stage1_central", "eq", None),
    ("D2 wins the long-turn side more than D1 (5/17 against 1/17)", "d2", "d1", "gt", "> +15"),
    ("D2 wins the long-turn side more than central stage 1 (5/17 against 2/17)", "d2", "stage1_central", "gt", "> +15"),
    ("Stage 1b A did not fix the long-turn side (4/17 against 2/17)", "stage1b_A", "stage1_central", "gt", "> +15"),
    ("Stage 1b B did not fix the long-turn side (1/17 against 2/17)", "stage1b_B", "stage1_central", "gt", "> +15"),
]
md += ["", "## 3. Which earlier claims hold?", "",
       "Paired difference in success on the same 200 starts (percentage points), 95% interval, exact McNemar p. "
       "For \"beats\" claims, \"holds\" = the interval excludes 0 in the claimed direction and the exact test has p < 0.05; for \"matches\" claims, "
       "\"holds\" = the interval contains 0. For the two \"did not fix\" claims the first policy is the fix, so \"holds\" "
       "means the fix did help the long-turn side (the old claim is not supported).", "",
       "| claim (old 50-start evidence) | difference | 95% interval | McNemar p | verdict |", "|---|---|---|---|---|"]
for text, a, b, kind, side in claims:
    idx = None if side is None else [i for i, e in enumerate(EP[a]) if e["side"] == side]
    m, h = paired(a, b, idx)
    d = [won(EP[a][i]) - won(EP[b][i]) for i in (range(N) if idx is None else idx)]
    p = mcnemar_p(sum(v > 0 for v in d), sum(v < 0 for v in d))
    where = "" if side is None else f" (side {side} deg, n={len(idx)})"
    if kind == "gt":
        excl = m - h > 0 or m + h < 0
        if excl and p < 0.05:
            v = "holds" if m > 0 else "reversed"
        else:
            v = "borderline (the interval and the exact test disagree)" if (excl or p < 0.05) else "no measurable difference"
    else:
        v = "holds (no measurable difference)" if m - h <= 0 <= m + h else ("does not hold: first is higher" if m > 0 else "does not hold: first is lower")
    md.append(f"| {text}{where} | {100 * m:+.1f} | {100 * (m - h):+.1f} to {100 * (m + h):+.1f} | {p:.3f} | {v} |")

md += ["", "## 4. Wall time (8 worker processes per policy, starts dealt out round robin)", "",
       "| policy | wall time |", "|---|---|"]
for name, s in WALL.items():
    md.append(f"| {name} | {s:.0f} s |")
if WALL:
    tot = sum(WALL.values())
    md.append(f"| **total, {len(WALL)} policies** | **{tot / 60:.1f} min** |")
open(os.path.join(HERE, "results", "reevaluation.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))
