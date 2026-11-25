"""Cooperative success: a task success counts as cooperative only if both ducks contributed to the push.

Two measures of a duck's contribution over the push episode (both accumulated by copush.env):

    contact  contact impulse (N s): the magnitude of the duck's contact force on the box, integrated over time. It also
             credits a duck that holds the box as a pivot while the other turns it. The headline measure.
    push     push impulse (N s): the part of that force along the box-to-target line (clipped at 0), integrated. The
             measure behind the existing push_share numbers.

A duck's share is its measure divided by both ducks' total. An episode is cooperative if it is a task success and each
duck's share is at least the threshold (metrics.cooperative_share in configs/copush.yaml, default 0.25).
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

MEASURES = ("contact", "push")
DEFAULT_THRESHOLD = 0.25
SWEEP = (0.10, 0.20, 0.25, 0.30, 0.40)
_EPS = 1e-12                                              # a share exactly at the threshold counts
Z = 1.96


def wilson(k: int, n: int):
    """95% Wilson interval for k of n."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return c - h, c + h


def share_a(a: float, b: float) -> Optional[float]:
    """Duck A's share of a + b; None when neither duck did anything (no share to speak of)."""
    tot = a + b
    return a / tot if tot > 0 else None


def shares(per_duck: dict) -> dict:
    """{duck: its share of the total}, nan for every duck when the total is 0 (as the env's push_share)."""
    tot = sum(per_duck.values())
    return {d: (v / tot if tot > 0 else float("nan")) for d, v in per_duck.items()}


def weaker_share(a_share) -> Optional[float]:
    """The smaller of the two ducks' shares, from duck A's share (None or nan: no share)."""
    if a_share is None or a_share != a_share:
        return None
    return min(a_share, 1.0 - a_share)


def is_cooperative(success: bool, a_share, threshold: float = DEFAULT_THRESHOLD) -> bool:
    """Task success and each duck's share >= threshold. No share (nobody touched the box) is not cooperative."""
    w = weaker_share(a_share)
    return bool(success) and w is not None and w >= threshold - _EPS


def threshold_of(cfg: Optional[dict]) -> float:
    return float(((cfg or {}).get("metrics") or {}).get("cooperative_share", DEFAULT_THRESHOLD))


def summarize(episodes: Iterable[dict], threshold: float = DEFAULT_THRESHOLD, sweep=SWEEP) -> dict:
    """episodes: dicts with "success" (bool) and "contact_share_a" / "push_share_a" (duck A's share, None or nan when
    there is none). Counts with 95% Wilson intervals over all the episodes:
        task                      task successes
        cooperative[measure]      cooperative successes at the threshold
        sweep[measure][t]         cooperative successes at each threshold in sweep
        one_duck_under[measure]   task successes where one duck's share is under the threshold (or there is no share)
        disagree                  task successes that one measure calls cooperative and the other does not (ids listed)
    """
    eps = list(episodes)
    n = len(eps)
    ok = [e for e in eps if e["success"]]

    def cell(k, of=n):
        lo, hi = wilson(k, of)
        return {"k": k, "n": of, "rate": (k / of if of else float("nan")), "ci": [lo, hi]}

    key = {m: m + "_share_a" for m in MEASURES}
    coop = {m: [e for e in ok if is_cooperative(True, e.get(key[m]), threshold)] for m in MEASURES}
    dis = [e for e in ok if is_cooperative(True, e.get(key["contact"]), threshold)
           != is_cooperative(True, e.get(key["push"]), threshold)]
    return {"n": n, "threshold": threshold, "task": cell(len(ok)),
            "cooperative": {m: cell(len(coop[m])) for m in MEASURES},
            "sweep": {m: {f"{t:.2f}": cell(sum(is_cooperative(True, e.get(key[m]), t) for e in ok)) for t in sweep}
                      for m in MEASURES},
            "one_duck_under": {m: cell(len(ok) - len(coop[m]), len(ok)) for m in MEASURES},
            "disagree": {"k": len(dis), "of_successes": len(ok),
                         "contact_only": sum(is_cooperative(True, e.get(key["contact"]), threshold) for e in dis),
                         "push_only": sum(is_cooperative(True, e.get(key["push"]), threshold) for e in dis),
                         "ids": [e.get("i", e.get("id")) for e in dis]}}


def from_stats(stats: Iterable[dict]) -> list:
    """The env's episode_stats (info["episode_stats"]) as episodes for summarize()."""
    return [{"i": s.get("start", {}).get("id", i) if isinstance(s.get("start"), dict) else i,
             "success": s["reason"] == "success",
             "contact_share_a": (s.get("contact_share") or {}).get("duck_a"),
             "push_share_a": (s.get("push_share") or {}).get("duck_a")} for i, s in enumerate(stats)]


def summarize_stats(stats: Iterable[dict], threshold: Optional[float] = None, sweep=SWEEP) -> dict:
    """summarize() over the env's episode_stats; the threshold defaults to the one the env recorded (its config's)."""
    stats = list(stats)
    if threshold is None:
        threshold = stats[0].get("cooperative_threshold", DEFAULT_THRESHOLD) if stats else DEFAULT_THRESHOLD
    return summarize(from_stats(stats), threshold, sweep)


def _pc(c: dict) -> str:
    if not c["n"]:
        return "n/a"
    return f"{100 * c['rate']:.1f}% ({100 * c['ci'][0]:.1f} to {100 * c['ci'][1]:.1f})"


def report_lines(rows: dict, title: str = "Cooperative success", level: int = 2) -> list:
    """Markdown for {name: summarize(...)}: the headline table, the threshold sweep for both measures, and how often the
    two measures disagree."""
    first = next(iter(rows.values()))
    th = round(100 * first["threshold"])
    ts = list(first["sweep"]["contact"])
    L = ["#" * level + f" {title}", "",
         f"Cooperative success = task success and each duck's share of the pushing at least {th}%. Contact impulse "
         "(contact force on the box, integrated over the push) is the headline measure; the along-the-line measure "
         "counts only force toward the target. 95% Wilson intervals over all starts.", "",
         f"| | n | task success | **cooperative success (contact impulse, {th}%)** | cooperative success (along the line, {th}%) | "
         f"successes with one duck under {th}% (contact impulse) |", "|---|---|---|---|---|---|"]
    for name, s in rows.items():
        u = s["one_duck_under"]["contact"]
        L.append(f"| {name} | {s['n']} | {_pc(s['task'])} | **{_pc(s['cooperative']['contact'])}** | {_pc(s['cooperative']['push'])} | "
                 + (f"{u['k']} of {u['n']} ({100 * u['rate']:.1f}%)" if u["n"] else "n/a") + " |")
    for m, label in (("contact", "contact impulse"), ("push", "along the line")):
        L += ["", f"Threshold sweep, {label} (cooperative successes of n, each duck's share at least the threshold):", "",
              "| | " + " | ".join(f"{round(100 * float(t))}%" for t in ts) + " |", "|---|" + "---|" * len(ts)]
        for name, s in rows.items():
            L.append(f"| {name} | " + " | ".join(f"{s['sweep'][m][t]['k']} ({100 * s['sweep'][m][t]['rate']:.1f}%)" for t in ts) + " |")
    L += ["", f"The two measures disagree at {th}% (task successes that only one of them calls cooperative):", "",
          "| | disagree | cooperative by contact impulse only | cooperative along the line only |", "|---|---|---|---|"]
    for name, s in rows.items():
        d = s["disagree"]
        L.append(f"| {name} | {d['k']} of {d['of_successes']} successes | {d['contact_only']} | {d['push_only']} |")
    return L
