"""Evaluation helpers shared by scripts/rl/*: run episodes, summarize them, reward scale tables.

    stats = episodes(cfg, "push_steer", n=5, seed0=10000, split="eval")
    summary = summarize(stats)
    rows = scale_table(effective_reward(cfg), d0=0.40); flags = scale_flags(rows)
"""
from __future__ import annotations

import math
from typing import Callable, List, Optional

import numpy as np

from copush.env import CoPushEnv, baseline
from copush.rewards import TERMS, StepSummary, TaskReward

DUCKS = ("duck_a", "duck_b")


def run_episodes(env: CoPushEnv, make_act: Callable[[int], Callable], n: int, seed0: int = 0) -> List[dict]:
    """n episodes, episode i reset with seed seed0 + i and controller make_act(seed0 + i)."""
    out = []
    for i in range(n):
        act = make_act(seed0 + i)
        obs, _ = env.reset(seed=seed0 + i)
        while True:
            obs, _, te, tr, info = env.step(act(obs))
            if te or tr:
                out.append(info["episode_stats"])
                break
    return out


def episodes(cfg: dict, name: str, n: int, seed0: int = 0, split: str = "train", switch_log=None) -> List[dict]:
    """switch_log: optional list; the env's policy-switch windows are appended to it."""
    env = CoPushEnv(cfg, split=split)
    out = run_episodes(env, lambda s: baseline(name, env, seed=s), n, seed0)
    if switch_log is not None:
        env.reset(seed=seed0)                        # closes windows still open at the last step
        switch_log += [dict(w, controller=name) for w in env.switch_log]
    return out


def switch_summary(log: List[dict]) -> dict:
    """Counts and worst cases over CoPushEnv.switch_log windows."""
    by = {}
    for w in log:
        k = f"{w['from']}->{w['to']}"
        b = by.setdefault(k, {"n": 0, "stumbles": 0, "falls": 0, "worst_tilt": 0.0, "lowest_z": 1.0,
                              "box_moved_max": 0.0})
        b["n"] += 1
        b["stumbles"] += int(w["stumble"])
        b["falls"] += int(w["fell"])
        b["worst_tilt"] = max(b["worst_tilt"], w["max_tilt"])
        b["lowest_z"] = min(b["lowest_z"], w["min_z"])
        b["box_moved_max"] = max(b["box_moved_max"], w["box_moved"])
    return by


def summarize(stats: List[dict]) -> dict:
    ret = np.array([s["return"] for s in stats])
    terms = {k: (float(np.mean([s["terms"][k] for s in stats])), float(np.std([s["terms"][k] for s in stats])))
             for k in TERMS}
    reasons = {}
    for s in stats:
        reasons[s["reason"]] = reasons.get(s["reason"], 0) + 1
    shares = [s["push_share"]["duck_a"] for s in stats if not math.isnan(s["push_share"]["duck_a"])]
    flags = {}
    for s in stats:
        for f in {f.split(":")[0] for f in s["flags"]}:
            flags[f] = flags.get(f, 0) + 1
    return {"n": len(stats), "return_mean": float(ret.mean()), "return_std": float(ret.std()),
            "return_min": float(ret.min()), "return_max": float(ret.max()), "terms": terms,
            "success_rate": reasons.get("success", 0) / len(stats),
            "episodes_with_fall": sum(any(s["fell"].values()) for s in stats),
            "box_lost": reasons.get("box_lost", 0) + reasons.get("box_tipped", 0), "reasons": reasons,
            "push_share_a_mean": float(np.mean(shares)) if shares else float("nan"),
            "pushing_episodes": len(shares),
            "contact_time_mean": {d: float(np.mean([s["contact_time"][d] for s in stats])) for d in DUCKS},
            "final_dist_mean": float(np.mean([s["final_dist"] for s in stats])),
            "min_dist_mean": float(np.mean([s["min_dist"] for s in stats])),
            "steps_mean": float(np.mean([s["steps"] for s in stats])),
            "stood_up": {d: sum(s["stood_up"][d] > 0 for s in stats) for d in DUCKS},
            "flag_episodes": flags}


def fmt_block(title: str, res: dict, terms=TERMS) -> str:
    lines = [f"### {title}", "",
             "| controller | return mean ± sd [min, max] | " + " | ".join(terms) +
             " | success | falls | box lost | ends | push share A | contact s A / B | closest m | final m | flags (episodes) |",
             "|---|---|" + "---|" * len(terms) + "---|---|---|---|---|---|---|---|---|"]
    for name, s in res.items():
        tt = " | ".join(f"{m:+.2f} ± {sd:.2f}" for m, sd in (s["terms"][k] for k in terms))
        share = "-" if math.isnan(s["push_share_a_mean"]) else f"{100 * s['push_share_a_mean']:.0f}%"
        lines.append(f"| {name} | {s['return_mean']:+.2f} ± {s['return_std']:.2f} [{s['return_min']:+.2f}, {s['return_max']:+.2f}] | "
                     f"{tt} | {100 * s['success_rate']:.0f}% | {s['episodes_with_fall']}/{s['n']} | {s['box_lost']}/{s['n']} | "
                     f"{', '.join(f'{k} {v}' for k, v in sorted(s['reasons'].items()))} | {share} | "
                     f"{s['contact_time_mean']['duck_a']:.1f} / {s['contact_time_mean']['duck_b']:.1f} | "
                     f"{s['min_dist_mean']:.2f} | {s['final_dist_mean']:.2f} | "
                     f"{', '.join(f'{k} {v}' for k, v in sorted(s['flag_episodes'].items())) or 'none'} |")
    return "\n".join(lines) + "\n"


# ── reward scale: synthetic episodes through the real TaskReward ─────────────

def _run(task: TaskReward, dists, yaws, fall_at=None, lost_at=None, success_from=None, down_after=None,
         off_after=None, inside_from=None, dt=0.2):
    total, held, steps = 0.0, 0.0, 0
    for k in range(1, len(dists)):
        if success_from is not None and k >= success_from:
            held += dt
        off = (k - off_after) * dt if off_after is not None and k > off_after else 0.0
        s = StepSummary(dists[k - 1], dists[k], yaws[k - 1], yaws[k], success_held_s=held, fell=(fall_at == k),
                        down_s=dt if (down_after is not None and k >= down_after) else 0.0, box_lost=(lost_at == k),
                        inside=inside_from is not None and k >= inside_from,
                        off_box_s={"duck_a": off, "duck_b": off})
        t, term, why = task.step(s)
        total += sum(t.values())
        steps = k
        if term:
            return total, steps, why
    return total, steps, "timeout"


def scale_table(rcfg: dict, d0: float = 0.40, n: int = 100) -> List[dict]:
    """Typical totals per outcome, start distance d0, yaw error 0 at the start. Ducks are on the box
    the whole time except in the scenarios that say otherwise (matters for contact_penalty)."""
    task = TaskReward(rcfg)
    cont = rcfg["fall_mode"] == "continuous"
    lin = lambda a, b, k: list(np.linspace(a, b, k + 1))
    y0 = [0.0] * (n + 1)
    near = 0.05
    k_s = max(5, round(n * 0.20))                              # reach the target at 20% of the episode
    sc = {
        f"success ({k_s * 0.2:.0f} s)": dict(dists=lin(d0, near, k_s) + [near] * 6,
                                             yaws=lin(0, math.radians(5), k_s) + [math.radians(5)] * 6,
                                             success_from=k_s + 1, inside_from=k_s),
        "fall early (2 s, no progress)": dict(dists=[d0] * (n + 1), yaws=y0, fall_at=10,
                                              down_after=10 if cont else None, off_after=10),
        f"fall late (15 s, after {d0 / 2:.2f} m)": dict(dists=lin(d0, d0 / 2, 75) + [d0 / 2] * 25, yaws=y0,
                                                       fall_at=75, down_after=75 if cont else None, off_after=75),
        "box lost early (walk away, 2 s)": dict(dists=[d0] * (n + 1), yaws=y0, lost_at=10, off_after=3),
        f"box lost late (10 s, after {d0 / 2:.2f} m)": dict(dists=lin(d0, d0 / 2, 50) + [d0 / 2] * 50, yaws=y0,
                                                           lost_at=50, off_after=48),
        f"timeout, partial progress ({d0 / 2:.2f} m)": dict(dists=lin(d0, d0 / 2, n), yaws=lin(0, math.radians(10), n)),
        "timeout, stand still at the box": dict(dists=[d0] * (n + 1), yaws=y0),
        "timeout, stand still off the box": dict(dists=[d0] * (n + 1), yaws=y0, off_after=0),
        "timeout, overshoot": dict(dists=lin(d0, near, n // 4) + lin(near, d0 + 0.2, n - n // 4)[1:],
                                   yaws=lin(0, math.radians(40), n)),
    }
    rows = []
    for name, kw in sc.items():
        total, steps, why = _run(task, **kw)
        rows.append({"outcome": name, "total": total, "steps": steps, "ends": why})
    return rows


def scale_flags(rows: List[dict]) -> List[str]:
    tot = {r["outcome"]: r["total"] for r in rows}
    succ = next(v for k, v in tot.items() if k.startswith("success"))
    out = []
    for k, v in tot.items():
        if not k.startswith("success") and v >= succ:
            out.append(f"'{k}' ({v:+.2f}) scores >= success ({succ:+.2f})")
    timeouts = {k: v for k, v in tot.items() if k.startswith("timeout")}
    for fail in ("fall early", "box lost early", "fall late", "box lost late"):
        fk = next(k for k in tot if k.startswith(fail))
        for k, v in timeouts.items():
            if tot[fk] > v:
                out.append(f"'{fk}' ({tot[fk]:+.2f}) beats continuing to '{k}' ({v:+.2f})")
    return out
