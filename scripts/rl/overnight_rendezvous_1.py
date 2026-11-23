#!/usr/bin/env python3
"""Rendezvous night 1: train the rendezvous coordinator from scratch (2 seeds), then the full pipeline on 200 starts.

    caffeinate -is scripts/rl.sh scripts/rl/overnight_rendezvous_1.py
    scripts/rl.sh scripts/rl/overnight_rendezvous_1.py --dry-run        # tiny settings into runs/d2-rendezvous-night1-dry/

Steps (each marked done in runs/d2-rendezvous-night1/steps/, so a restart skips what is finished; training resumes from
its last checkpoint):
  scripted  the scripted rendezvous baseline through the full pipeline (rendezvous -> handoff -> push with L2-s2) on
            experiments/test_sets/rendezvous_large.json (200 starts): the reference for this night
  s1, s2    scripts/rl/train_rendezvous.py, PPO from scratch, seeds 1 and 2, 2M duck steps each, eval every 200k steps
            on the same 200 starts (rendezvous alone, the training ending)
  eval      each trained seed through the full pipeline on the 200 starts (same handoff rule and 50-step cap as scripted)
  gifs      10 starts side by side (scripted left, the better seed right): first starts where the two differ in push
            outcome, then the trained seed's failures, then its successes
STOP file (runs/d2-rendezvous-night1/STOP): the current step finishes, no new one starts. No new step starts after
--deadline (09:00). progress.log, crash.log, logs/<step>.log. SUMMARY.md (experiments/d2-rendezvous/night1/) is written
once, at the end, from whatever finished.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts", "rl")]

from ci_report import mean_ci, wilson  # noqa: E402

CONFIG = "experiments/d2-rendezvous/config.yaml"
SET = "experiments/test_sets/rendezvous_large.json"
PUSH = "runs/d2-steering-night5/l2-s2/model.zip"
E = "experiments/d2-rendezvous/night1"
STEPS = ("scripted", "s1", "s2", "eval", "gifs")
SEEDS = {"s1": 1, "s2": 2}
KINDS = ("uniform", "near_symmetric", "wrong_side")
N_GIFS = 10


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else "missing"


def pct(x):
    return "n/a" if x is None else f"{max(0.0, 100 * x):.1f}%"


def rate(k, n):
    lo, hi = wilson(k, n)
    return f"{pct(k / n)} ({pct(lo)} to {pct(hi)})" if n else "n/a"


class Night:
    def __init__(self, dry: bool, deadline: str):
        self.dry = dry
        self.dir = os.path.join(ROOT, "runs", "d2-rendezvous-night1" + ("-dry" if dry else ""))
        self.exp = os.path.join(self.dir, "summary") if dry else os.path.join(ROOT, E)
        for d in ("logs", "steps"):
            os.makedirs(os.path.join(self.dir, d), exist_ok=True)
        now = dt.datetime.now()
        hh, mm = map(int, deadline.split(":"))
        self.deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if self.deadline <= now:
            self.deadline += dt.timedelta(days=1)
        self.n = 10 if dry else 0                               # pipeline starts (0 = all 200)
        self.train_args = ["--steps", "8192", "--eval-every", "4096", "--eval-starts", "8"] if dry else []
        self.n_gifs = 2 if dry else N_GIFS

    # ── bookkeeping ─────────────────────────────────────────────────────────
    def log(self, msg):
        line = f"{dt.datetime.now():%H:%M:%S} {msg}"
        print(line, flush=True)
        with open(os.path.join(self.dir, "progress.log"), "a") as f:
            f.write(line + "\n")

    def done(self, step):
        return os.path.exists(os.path.join(self.dir, "steps", step + ".done"))

    def mark(self, step, t0):
        json.dump({"start": t0, "end": f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"},
                  open(os.path.join(self.dir, "steps", step + ".done"), "w"))

    def crash(self, msg):
        with open(os.path.join(self.dir, "crash.log"), "a") as f:
            f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")

    def sh(self, step, cmd):
        logp = os.path.join(self.dir, "logs", step + ".log")
        with open(logp, "a") as f:
            f.write(f"\n$ {' '.join(cmd)}\n")
            f.flush()
            rc = subprocess.call(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        if rc != 0:
            tail = open(logp).read().splitlines()[-30:]
            self.crash(f"step {step} exit {rc}: {' '.join(cmd)}\n" + "\n".join(tail) + "\n")
        return rc == 0

    def model(self, run):
        return os.path.join(self.dir, run, "model.zip")

    def evaldir(self, name):
        return os.path.join(self.dir, f"eval_{name}")

    def pipeline(self, step, rendezvous, name):
        cmd = [sys.executable, "scripts/rl/rendezvous_eval.py", "eval", "--rendezvous", rendezvous, "--push", PUSH,
               "--out", os.path.relpath(self.evaldir(name), ROOT)]
        if self.n:
            cmd += ["--starts", str(self.n)]
        return self.sh(step, cmd)

    # ── steps ───────────────────────────────────────────────────────────────
    def step_scripted(self):
        return self.pipeline("scripted", "scripted", "scripted")

    def step_train(self, run):
        return self.sh(run, [sys.executable, "scripts/rl/train_rendezvous.py", "--config", CONFIG, "--seed", str(SEEDS[run]),
                             "--out", os.path.relpath(os.path.join(self.dir, run), ROOT), *self.train_args])

    def step_eval(self):
        ok = True
        for run in SEEDS:
            if os.path.exists(self.model(run)):
                ok &= self.pipeline("eval", os.path.relpath(self.model(run), ROOT), run)
            else:
                self.crash(f"eval: {run} has no model.zip; skipped")
                ok = False
        return ok

    def episodes(self, name):
        p = os.path.join(self.evaldir(name), "results.json")
        return json.load(open(p))["episodes"] if os.path.exists(p) else None

    def best_seed(self):
        rates = {r: sum(e["push_success"] for e in eps) for r in SEEDS if (eps := self.episodes(r))}
        return max(rates, key=lambda r: (rates[r], -SEEDS[r])) if rates else None

    def step_gifs(self):
        best, scr = self.best_seed(), self.episodes("scripted")
        if best is None or scr is None:
            self.crash("gifs: missing pipeline results")
            return False
        tr = self.episodes(best)
        differ = [e["i"] for e, s in zip(tr, scr) if e["push_success"] != s["push_success"]]
        fails = [e["i"] for e in tr if not e["push_success"] and e["i"] not in differ]
        wins = [e["i"] for e in tr if e["push_success"] and e["i"] not in differ]
        pick = (differ + fails[:3] + wins)[: self.n_gifs]
        gdir = os.path.join(self.dir, "gifs")
        ok = True
        for i in pick:
            ok &= self.sh("gifs", [sys.executable, "scripts/rl/rendezvous_gif.py", "--start", str(i), "--left", "scripted",
                                   "--right", os.path.relpath(self.model(best), ROOT), "--right-label", f"trained {best}",
                                   "--push", PUSH, "--out", os.path.relpath(gdir, ROOT)])
        json.dump({"seed": best, "starts": pick}, open(os.path.join(gdir, "picked.json"), "w"))
        return ok

    def run(self):
        free = shutil.disk_usage(ROOT).free / 1e9
        self.log(f"start ({'dry run' if self.dry else 'rendezvous night 1'}); no new step after {self.deadline:%Y-%m-%d %H:%M}; "
                 f"free disk {free:.0f} GB")
        if free < 10:
            self.log("WARNING: under 10 GB free")
        for step in STEPS:
            if self.done(step):
                self.log(f"skip {step} (done)")
                continue
            if os.path.exists(os.path.join(self.dir, "STOP")):
                self.log("STOP file found: stopping before " + step)
                break
            if dt.datetime.now() >= self.deadline:
                self.log(f"past the deadline ({self.deadline:%H:%M}): not starting {step}")
                break
            t0 = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"
            self.log(f"start {step}")
            fn = {"scripted": self.step_scripted, "eval": self.step_eval, "gifs": self.step_gifs}.get(step) or \
                (lambda s=step: self.step_train(s))
            try:
                ok = fn()
            except Exception as e:                                # a bug in a step must not end the night
                ok = False
                self.crash(f"step {step} raised {e!r}")
            if ok:
                self.mark(step, t0)
                self.log(f"end {step} ok")
            else:
                self.log(f"end {step} FAILED (see crash.log)")
        try:
            os.makedirs(self.exp, exist_ok=True)
            self.copy_results()
            with open(os.path.join(self.exp, "SUMMARY.md"), "w") as f:
                f.write(self.summary())
            self.log(f"wrote {os.path.relpath(os.path.join(self.exp, 'SUMMARY.md'), ROOT)}")
        except Exception as e:
            self.crash(f"summary raised {e!r}")
        self.log("ALL DONE" if all(self.done(s) for s in STEPS) else "stopped; finished: " + ", ".join(s for s in STEPS if self.done(s)))

    # ── summary ─────────────────────────────────────────────────────────────
    def copy_results(self):
        """results.md of each pipeline eval, the training curves and the GIFs into the experiment folder (the per-episode
        results.json files stay in runs/)."""
        for name in ("scripted", *SEEDS):
            src = os.path.join(self.evaldir(name), "results.md")
            if os.path.exists(src):
                os.makedirs(os.path.join(self.exp, "results", name), exist_ok=True)
                shutil.copy(src, os.path.join(self.exp, "results", name, "results.md"))
        for run in SEEDS:
            src = os.path.join(self.dir, run, "evals.jsonl")
            if os.path.exists(src):
                os.makedirs(os.path.join(self.exp, "results", run), exist_ok=True)
                shutil.copy(src, os.path.join(self.exp, "results", run, "evals.jsonl"))
        g = os.path.join(self.dir, "gifs")
        if os.path.isdir(g):
            os.makedirs(os.path.join(self.exp, "gifs"), exist_ok=True)
            for f in sorted(os.listdir(g)):
                if f.endswith(".gif") or f == "picked.json":
                    shutil.copy(os.path.join(g, f), os.path.join(self.exp, "gifs", f))

    def paired(self, a, b, key):
        d = [float(x[key]) - float(y[key]) for x, y in zip(a, b)]
        if len(d) < 2:
            return None
        m, h = mean_ci(d)
        return m, m - h, m + h

    def summary(self) -> str:
        eps = {n: self.episodes(n) for n in ("scripted", *SEEDS)}
        have = [n for n in ("scripted", *SEEDS) if eps[n]]
        L = ["# D2 rendezvous, night 1: a learned rendezvous coordinator against the scripted one", "",
             f"*Written {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/rl/overnight_rendezvous_1.py`"
             + (" (DRY RUN: tiny settings, numbers mean nothing)" if self.dry else "") + ".*", "", "## Steps", "",
             "| step | status | finished |", "|---|---|---|"]
        for s in STEPS:
            p = os.path.join(self.dir, "steps", s + ".done")
            L.append(f"| {s} | {'done' if os.path.exists(p) else 'not done'} | {json.load(open(p))['end'] if os.path.exists(p) else ''} |")
        L += ["", "## Setup", "",
              "- **The one change:** the rendezvous phase is a trained policy (PPO from scratch, one shared network per duck, "
              "each duck seeing its spot, its partner and the box in its own frame) instead of the scripted coordinator "
              "(copush.rendezvous.ScriptedRendezvous). Everything after the handoff is the same: the night 5 L2-s2 push policy "
              f"(`{PUSH}`, sha256 `{sha(os.path.join(ROOT, PUSH))[:16]}...`).",
              "- **Reward per duck per step:** 10 x (decrease in distance to its spot) + 1 x (decrease in heading error, rad) "
              "- 0.03 - 1.0 if it touched the box or its partner; +5 to both when both are within 3 cm and 15 deg for 0.25 s "
              "(episode ends), -5 at 100 steps or on a fall.",
              "- **Training:** 2,000,000 duck steps (2 per simulator step) per seed, seeds 1 and 2, configs/copush.yaml's PPO "
              "(8 envs, n_steps 256, ent_coef 0.01), starts drawn like the eval set (box over stage 1's range, 80% uniform / 10% "
              "near-symmetric / 10% wrong-side duck placements).",
              f"- **Eval set:** `{SET}`, 200 starts on stage1_large's 200 box poses (160 uniform, 20 near-symmetric, 20 "
              "wrong-side), seed 10000 + i, deterministic. Pipeline: rendezvous until both ducks are within 3 cm and 15 deg of "
              "their spots and upright (checked every 0.2 s), at most 50 steps, then the push policy for 100 steps; push "
              "success = box in the target, yaw within 15 deg, both up, held 1 s.",
              "- **Rule for \"measurable\":** the paired 95% interval (same starts, seeds averaged) excludes 0 **and** both "
              "seed rates are on the same side of the scripted rate (the scripted controller is deterministic, one rate).", ""]
        for run in SEEDS:
            p = os.path.join(self.dir, run, "evals.jsonl")
            if os.path.exists(p):
                rows = [json.loads(x) for x in open(p) if x.strip()]
                L += [f"**Training curve, {run}** (rendezvous alone on the eval set, 100-step training ending)", "",
                      "| duck steps | arrived | mean steps to arrive | position error (cm) | heading error (deg) | duck-box hits | duck-duck hits | falls |",
                      "|---|---|---|---|---|---|---|---|"]
                for r in rows:
                    ms = "n/a" if r["mean_steps_to_arrive"] is None else f"{r['mean_steps_to_arrive']:.1f}"
                    L.append(f"| {r['step']} | {r['arrived']}/{r['n']} | {ms} | {r['pos_err_cm_mean']:.1f} | "
                             f"{r['yaw_err_deg_mean']:.1f} | {r['duck_box_hits']} | {r['duck_duck_hits']} | {r['falls']} |")
                L.append("")
        if not have:
            return "\n".join(L + ["No pipeline results."]) + "\n"
        L += ["## Results on the 200 starts (full pipeline)", "",
              "| controller | arrived in 50 steps | end-to-end push success | push success when arrived | mean steps to arrive | "
              "position / heading error at handoff (mean) | duck-box hits (episodes) | duck-duck hits (episodes) |",
              "|---|---|---|---|---|---|---|---|"]
        for n in have:
            e = eps[n]
            arr = [x for x in e if x["arrived"]]
            ms = f"{sum(x['rv_steps'] for x in arr) / len(arr):.1f}" if arr else "n/a"
            pe = sum(x["pos_err_cm"][d] for x in e for d in x["pos_err_cm"]) / (2 * len(e))
            ye = sum(x["yaw_err_deg"][d] for x in e for d in x["yaw_err_deg"]) / (2 * len(e))
            L.append(f"| {n} | {rate(len(arr), len(e))} | {rate(sum(x['push_success'] for x in e), len(e))} | "
                     f"{sum(x['push_success'] for x in arr)} of {len(arr)} | {ms} | {pe:.1f} cm / {ye:.1f} deg | "
                     f"{sum(sum(x['hit_box'].values()) for x in e)} ({sum(1 for x in e if any(x['hit_box'].values()))}) | "
                     f"{sum(x['hit_ducks'] for x in e)} ({sum(1 for x in e if x['hit_ducks'])}) |")
        L += ["", "**By start kind** (end-to-end push success)", "", "| controller | " + " | ".join(KINDS) + " |", "|---|" + "---|" * len(KINDS)]
        for n in have:
            L.append(f"| {n} | " + " | ".join(rate(sum(x["push_success"] for x in eps[n] if x["kind"] == k),
                                                  sum(1 for x in eps[n] if x["kind"] == k)) for k in KINDS) + " |")
        trained = [r for r in SEEDS if eps[r]]
        if eps["scripted"] and trained:
            n = min(len(eps["scripted"]), *(len(eps[r]) for r in trained))
            avg = [{"push_success": sum(eps[r][i]["push_success"] for r in trained) / len(trained),
                    "arrived": sum(eps[r][i]["arrived"] for r in trained) / len(trained)} for i in range(n)]
            scr = eps["scripted"][:n]
            L += ["", "## Verdict (fixed rule)", ""]
            for key, label in (("push_success", "end-to-end push success"), ("arrived", "arrival within 50 steps")):
                p = self.paired(avg, scr, key)
                srate = sum(x[key] for x in scr) / n
                seed_rates = [sum(eps[r][i][key] for i in range(n)) / n for r in trained]
                if p is None:
                    continue
                m, lo, hi = p
                same_side = len(seed_rates) == 2 and (all(s > srate for s in seed_rates) or all(s < srate for s in seed_rates))
                if lo > 0 and same_side:
                    v = "**trained is measurably better**"
                elif hi < 0 and same_side:
                    v = "**trained is measurably worse**"
                else:
                    v = "**no measurable difference**" + (" (one seed only)" if len(seed_rates) < 2 else "")
                L.append(f"- {label}: trained (seeds averaged) minus scripted {100 * m:+.1f} points ({100 * lo:+.1f} to "
                         f"{100 * hi:+.1f}); seed rates {', '.join(pct(s) for s in seed_rates)} vs scripted {pct(srate)}: {v}")
        g = os.path.join(self.exp, "gifs")
        if os.path.isdir(g):
            picked = json.load(open(os.path.join(g, "picked.json"))) if os.path.exists(os.path.join(g, "picked.json")) else {}
            L += ["", f"## Clips (scripted left, trained {picked.get('seed', '')} right; then the same push policy)", ""]
            for f in sorted(x for x in os.listdir(g) if x.endswith(".gif")):
                L += [f"**{f.split('_')[0]}**", "", f"![{f}](gifs/{f})", ""]
        L += ["", "Per-episode results: `runs/d2-rendezvous-night1/eval_<controller>/results.json` (git-ignored); the tables "
              "above come from them, and `results/<controller>/results.md` has the full per-kind breakdown."]
        return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--deadline", default="09:00", help="no new step starts after this local time (HH:MM)")
    a = ap.parse_args()
    night = Night(a.dry_run, a.deadline)
    lock = os.path.join(night.dir, "lock")
    if os.path.exists(lock):
        try:
            os.kill(int(open(lock).read() or 0), 0)
            print(f"already running; remove {lock} if it is not")
            return 1
        except (OSError, ValueError):
            pass
    open(lock, "w").write(str(os.getpid()))
    try:
        night.run()
    finally:
        if os.path.exists(lock):
            os.remove(lock)
    return 0


if __name__ == "__main__":
    sys.exit(main())

