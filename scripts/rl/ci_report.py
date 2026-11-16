#!/usr/bin/env python3
"""95% confidence intervals and paired comparisons from a compare_policies.py comparison.json.

    scripts/rl.sh scripts/rl/ci_report.py --comparison <dir>/comparison.json --out <dir>/ci_report.md \
        --pair run1_true_heading:part2_seed1 --pooled run1_true_heading:part2_seed1,run2_seed2

Per policy: success overall and per box-angle side with a Wilson 95% interval, idle share (mean, 95% interval of the
mean over episodes), overshoots and time-outs (count, Wilson interval). Every policy ran the same starts, so
differences are PAIRED: the mean per-start difference in success with a 95% interval (normal approximation on the
paired differences) and an exact McNemar p-value on the starts where exactly one of the two won. --pooled A:B,C
compares A with the mean of B and C start by start.
"""
from __future__ import annotations

import argparse
import json
import math

Z = 1.96
SIDES = ("< -15", "-15 to +15", "> +15")


def wilson(k: int, n: int):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return c - h, c + h


def pct(x):
    return f"{100 * x:.0f}%"


def ci_str(k, n):
    lo, hi = wilson(k, n)
    return f"{pct(k / n)} ({pct(lo)} to {pct(hi)})" if n else "n/a"


def mean_ci(xs):
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = Z * sd / math.sqrt(n)
    return m, h


def mcnemar_p(b, c):
    """Exact two-sided p for b vs c discordant pairs (binomial, p = 0.5)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def won(ep):
    return 1.0 if ep["reason"] == "success" else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--comparison", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pair", action="append", default=[], help="A:B, difference A - B")
    ap.add_argument("--pooled", action="append", default=[], help="A:B,C, difference A - mean(B, C)")
    a = ap.parse_args()
    eps = json.load(open(a.comparison))["episodes"]
    n = len(next(iter(eps.values())))
    md = [f"# Confidence intervals ({n} starts per policy, 95%)", "",
          "Success with a Wilson interval, overall and per box-angle side; idle share is the mean over episodes with a 95% "
          "interval of the mean.", "",
          "| policy | overall | " + " | ".join(f"{s} deg" for s in SIDES) + " | idle share | overshoots | time-outs |",
          "|---|---|---|---|---|---|---|---|"]
    for name, rows in eps.items():
        side = []
        for s in SIDES:
            r = [e for e in rows if e["side"] == s]
            side.append(ci_str(sum(e["reason"] == "success" for e in r), len(r)) + f" of {len(r)}")
        idle, ih = mean_ci([e["idle_frac"] for e in rows])
        md.append(f"| {name} | {ci_str(int(sum(map(won, rows))), n)} | " + " | ".join(side) + f" | {pct(idle)} (+-{100 * ih:.0f}) | "
                  f"{ci_str(sum(bool(e['overshoot']) for e in rows), n)} | {ci_str(sum(e['reason'] == 'timeout' for e in rows), n)} |")

    def diff_row(label, d, discordant=None):
        m, h = mean_ci(d)
        sig = "yes" if (m - h > 0 or m + h < 0) else "no"
        p = f"{mcnemar_p(*discordant):.3f}" if discordant else "n/a"
        return f"| {label} | {100 * m:+.1f} | {100 * (m - h):+.1f} to {100 * (m + h):+.1f} | {p} | {sig} |"

    rows_d = []
    for spec in a.pair:
        x, y = spec.split(":")
        d = [won(p) - won(q) for p, q in zip(eps[x], eps[y])]
        rows_d.append(diff_row(f"{x} minus {y}", d, (sum(v > 0 for v in d), sum(v < 0 for v in d))))
    for spec in a.pooled:
        x, ys = spec.split(":")
        ys = ys.split(",")
        d = [won(eps[x][i]) - sum(won(eps[y][i]) for y in ys) / len(ys) for i in range(n)]
        rows_d.append(diff_row(f"{x} minus the mean of {' and '.join(ys)}", d))
        for s in SIDES:                                                           # the same, per side
            idx = [i for i, e in enumerate(eps[x]) if e["side"] == s]
            ds = [won(eps[x][i]) - sum(won(eps[y][i]) for y in ys) / len(ys) for i in idx]
            rows_d.append(diff_row(f"&nbsp;&nbsp;side {s} deg (n={len(idx)})", ds))
    md += ["", "## Paired differences in success (percentage points, same starts)", "",
           "| comparison | mean difference | 95% interval | McNemar p (exact) | interval excludes 0 |", "|---|---|---|---|---|"] + rows_d
    open(a.out, "w").write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
