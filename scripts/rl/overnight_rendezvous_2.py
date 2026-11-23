#!/usr/bin/env python3
"""Rendezvous night 2: night 1 never docked once in 2M steps (0/200 on both seeds; experiments/d2-rendezvous/night1/
SUMMARY.md). This night's one change (several settings; experiments/d2-rendezvous/config.yaml) is the reward and
training schedule: absolute distance/heading reward instead of its improvement, a reachable partial bonus, 50-step
episodes instead of 100, and a curriculum that starts ducks close to their spot and widens once that is solved.

    caffeinate -is scripts/rl.sh scripts/rl/overnight_rendezvous_2.py
    scripts/rl.sh scripts/rl/overnight_rendezvous_2.py --dry-run        # tiny settings into runs/d2-rendezvous-night2-dry/

Steps (each marked done in runs/d2-rendezvous-night2/steps/, so a restart skips what is finished; training resumes
from its last checkpoint):
  scripted  the scripted rendezvous baseline through the full pipeline (unchanged from night 1: same script, same
            200 starts), recomputed here so this night's SUMMARY is self-contained
  s1, s2    scripts/rl/train_rendezvous.py, PPO from scratch, seeds 1 and 2, up to 2M duck steps each, eval every
            200k steps on the same 200 starts (rendezvous alone, the training ending). --early-stop-step 400000:
            if an eval at or after 400k steps finds 0 arrivals, that seed's training stops there (not a crash) and,
            if it was s1, s2 is skipped rather than spending another ~70 minutes on the same reward from scratch
  eval      each trained seed that produced a model.zip through the full pipeline on the 200 starts
  gifs      10 starts side by side (scripted left, the better seed right)
STOP file (runs/d2-rendezvous-night2/STOP): the current step finishes, no new one starts. No new step starts after
--deadline (09:00). progress.log (also carries forward each training run's "curriculum:" level-change and
"early-stop:"/"aborted early:" lines), crash.log, logs/<step>.log. SUMMARY.md (experiments/d2-rendezvous/night2/) is
written once, at the end, from whatever finished.
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
E = "experiments/d2-rendezvous/night2"
STEPS = ("scripted", "s1", "s2", "eval", "gifs")
SEEDS = {"s1": 1, "s2": 2}
KINDS = ("uniform", "near_symmetric", "wrong_side")
N_GIFS = 10
EARLY_STOP_STEP = 400000        # duck steps: abort a seed if it has docked 0 times by here


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
        self.dir = os.path.join(ROOT, "runs", "d2-rendezvous-night2" + ("-dry" if dry else ""))
        self.exp = os.path.join(self.dir, "summary") if dry else os.path.join(ROOT, E)
        for d in ("logs", "steps"):
            os.makedirs(os.path.join(self.dir, d), exist_ok=True)
        now = dt.datetime.now()
        hh, mm = map(int, deadline.split(":"))
        self.deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if self.deadline <= now:
            self.deadline += dt.timedelta(days=1)
        self.n = 10 if dry else 0                               # pipeline starts (0 = all 200)
        self.train_args = ["--steps", "8192", "--eval-every", "4096", "--eval-starts", "8", "--early-stop-step", "4096"] \
            if dry else ["--early-stop-step", str(EARLY_STOP_STEP)]
        self.n_gifs = 2 if dry else N_GIFS
        self.skip = {}                                          # step -> reason, set when s1 aborts early

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
        return rc == 0, logp

    def model(self, run):
        return os.path.join(self.dir, run, "model.zip")

    def abort_reason(self, run):
        p = os.path.join(self.dir, run, "abort.json")
        return json.load(open(p))["reason"] if os.path.exists(p) else None

    def evaldir(self, name):
        return os.path.join(self.dir, f"eval_{name}")

    def pipeline(self, step, rendezvous, name):
        cmd = [sys.executable, "scripts/rl/rendezvous_eval.py", "eval", "--rendezvous", rendezvous, "--push", PUSH,
               "--out", os.path.relpath(self.evaldir(name), ROOT)]
        if self.n:
            cmd += ["--starts", str(self.n)]
        ok, _ = self.sh(step, cmd)
        return ok

    # ── steps ───────────────────────────────────────────────────────────────
    def step_scripted(self):
        return self.pipeline("scripted", "scripted", "scripted")

    def step_train(self, run):
        ok, logp = self.sh(run, [sys.executable, "scripts/rl/train_rendezvous.py", "--config", CONFIG, "--seed", str(SEEDS[run]),
                                 "--out", os.path.relpath(os.path.join(self.dir, run), ROOT), *self.train_args])
        if os.path.exists(logp):
            for line in open(logp):
                line = line.strip()
                if line.startswith("curriculum:") or line.startswith("early-stop:") or line.startswith("aborted early:"):
                    self.log(f"{run}: {line}")
        if ok:
            reason = self.abort_reason(run)
            if reason and run == "s1":
                self.skip["s2"] = f"s1 aborted early ({reason}); the same from-scratch reward would likely do the same"
        return ok

    def step_eval(self):
        ok = True
        for run in SEEDS:
            if os.path.exists(self.model(run)):
                ok &= self.pipeline("eval", os.path.relpath(self.model(run), ROOT), run)
            elif run not in self.skip:
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
            rc, _ = self.sh("gifs", [sys.executable, "scripts/rl/rendezvous_gif.py", "--start", str(i), "--left", "scripted",
                                     "--right", os.path.relpath(self.model(best), ROOT), "--right-label", f"trained {best}",
                                     "--push", PUSH, "--out", os.path.relpath(gdir, ROOT)])
            ok &= rc
        json.dump({"seed": best, "starts": pick}, open(os.path.join(gdir, "picked.json"), "w"))
        return ok

    def run(self):
        free = shutil.disk_usage(ROOT).free / 1e9
        self.log(f"start ({'dry run' if self.dry else 'rendezvous night 2'}); no new step after {self.deadline:%Y-%m-%d %H:%M}; "
                 f"free disk {free:.0f} GB")
        if free < 10:
            self.log("WARNING: under 10 GB free")
        for step in STEPS:
            if step in self.skip:
                self.log(f"skip {step}: {self.skip[step]}")
                continue
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
        finished = [s for s in STEPS if self.done(s) or s in self.skip]
        self.log("ALL DONE" if len(finished) == len(STEPS) else "stopped; finished: " + ", ".join(finished))

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
            ab = os.path.join(self.dir, run, "abort.json")
            if os.path.exists(ab):
                shutil.copy(ab, os.path.join(self.exp, "results", run, "abort.json"))
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
        L = ["# D2 rendezvous, night 2: absolute-distance reward, a partial bonus, shorter episodes, a curriculum", "",
             f"*Written {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/rl/overnight_rendezvous_2.py`"
             + (" (DRY RUN: tiny settings, numbers mean nothing)" if self.dry else "") + ".*", "", "## Steps", "",
             "| step | status | finished |", "|---|---|---|"]
        for s in STEPS:
            p = os.path.join(self.dir, "steps", s + ".done")
            status = "skipped (" + self.skip[s] + ")" if s in self.skip else ("done" if os.path.exists(p) else "not done")
            L.append(f"| {s} | {status} | {json.load(open(p))['end'] if os.path.exists(p) else ''} |")
        L += ["", "## Setup", "",
              "- **Why this night:** night 1's reward (10 x decrease in distance to the spot per step) never docked "
              "once in 2,000,000 steps on either seed: at the fastest walking speed the per-step reward (about 0.24) "
              "barely cleared the 0.03 time penalty, and standing still made the reward (and its gradient) vanish. "
              "See `experiments/d2-rendezvous/night1/SUMMARY.md`.",
              "- **The change (one named reward/schedule, several settings; `experiments/d2-rendezvous/config.yaml`):** "
              "reward is now absolute distance/heading, not their improvement, so it never vanishes while a duck is "
              "still far away: -1.0 x (distance to its spot / 0.8 m) - 0.3 x (heading error / pi) - 0.02 per step "
              "- 1.0 if it touched the box or its partner, +2.0 the first time within 10 cm of its spot (once per "
              "duck per episode), +5 to both on handoff (episode end), -2 at 50 steps (down from 100) or on a fall.",
              "- **Curriculum (new):** training starts begin at 15-20 cm from the box and widen to 20-40, 40-60, "
              "then the full 60-80 cm once the docking rate over the last 50,000 duck steps exceeds 60%, per worker "
              "(bearing and heading stay uniform over 360 deg at every level).",
              f"- **Early stop:** a seed whose docking rate is still 0% at {EARLY_STOP_STEP} steps aborts there "
              "instead of running to 2,000,000 (not a crash); if s1 aborts, s2 is skipped rather than repeat it.",
              "- **Everything else as night 1:** PPO from scratch, seeds 1 and 2, configs/copush.yaml's PPO (8 envs, "
              "n_steps 256, ent_coef 0.01), the same push policy after handoff "
              f"(`{PUSH}`, sha256 `{sha(os.path.join(ROOT, PUSH))[:16]}...`), the same "
              f"200-start eval set (`{SET}`) and pipeline (rendezvous up to 50 steps, then the push policy for 100 "
              "steps), the same \"measurable\" rule (the paired 95% interval excludes 0 and both seed rates are on "
              "the same side of the scripted rate).", ""]
        for run in SEEDS:
            p = os.path.join(self.dir, run, "evals.jsonl")
            if os.path.exists(p):
                rows = [json.loads(x) for x in open(p) if x.strip()]
                ab = self.abort_reason(run)
                L += [f"**Training curve, {run}**" + (f" (aborted: {ab})" if ab else "") +
                      " (rendezvous alone on the eval set, 50-step training ending)", "",
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
        L += ["", "Per-episode results: `runs/d2-rendezvous-night2/eval_<controller>/results.json` (git-ignored); the tables "
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
