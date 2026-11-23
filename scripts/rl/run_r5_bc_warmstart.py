#!/usr/bin/env python3
"""Rendezvous run r5-bc-warmstart: runs r1-r4 trained PPO from random weights and never docked (four reward designs; the
curriculum never left its first level). This run's one change is the starting policy: behavioral cloning (BC) of
the scripted coordinator first (scripts/rl/bc_rendezvous.py), then PPO fine-tuning from the BC weights. The reward is
r4's, unchanged (experiments/d2-rendezvous/r5-bc-warmstart.yaml); curriculum, observations, episode length, PPO settings,
early stop and pipeline are r4's.

    caffeinate -is scripts/rl.sh scripts/rl/run_r5_bc_warmstart.py
    scripts/rl.sh scripts/rl/run_r5_bc_warmstart.py --dry-run        # tiny settings into runs/d2-rendezvous-r5-bc-warmstart-dry/

Steps (each marked done in runs/d2-rendezvous-r5-bc-warmstart/steps/, so a restart skips what is finished; training resumes
from its last checkpoint):
  scripted  the scripted rendezvous baseline through the full pipeline (same script, same 200 starts as runs r1-r4)
  collect   scripted demonstrations on randomized training starts (bc.episodes, never the eval set)
  bc        supervised training of the policy network on them (80/20 split by episode, until the validation loss
            plateaus); writes bc/bc.zip and bc/loss.jsonl
  bc_eval   BC alone through the full pipeline on the 200 starts. GATE: if it docks 0 of 200, PPO is not started
            (s1 and s2 are skipped with the reason logged): something is wrong with the data or the cloning
  s1, s2    scripts/rl/train_rendezvous.py --init bc/bc.zip, seeds 1 and 2, up to 2M PPO duck steps each, eval at
            step 0 (BC weights) and every 200k steps on the same 200 starts. --early-stop-step 400000 (PPO steps
            only): if an eval at or after 400k finds 0 arrivals, that seed stops there and, if it was s1, s2 is skipped
  eval      each trained seed's best checkpoint (best.zip: most arrivals on the 200-start evals, ties by heading then
            position error; step 0 = BC is a candidate) through the full pipeline on the 200 starts
  gifs      10 starts side by side (scripted left, the better seed right; BC if PPO did not run)
STOP file (runs/d2-rendezvous-r5-bc-warmstart/STOP): the current step finishes, no new one starts. No new step starts after
--deadline (09:00). progress.log (also carries forward each training run's "curriculum:" level-change and
"early-stop:"/"aborted early:" lines), crash.log, logs/<step>.log. SUMMARY.md (experiments/d2-rendezvous/r5-bc-warmstart/) is
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

CONFIG = "experiments/d2-rendezvous/r5-bc-warmstart.yaml"        # training; the eval/gif scripts use config.yaml (same env)
PREV = {"approach bonus (s1)": "runs/d2-rendezvous-r4-approach-bonus/eval_s1/results.json",     # earlier runs' pipeline runs (best
        "heading bonus (s1)": "runs/d2-rendezvous-r3-heading-bonus/eval_s1/results.json",     # checkpoint, seed 1), for comparison rows
        "curriculum (s1)": "runs/d2-rendezvous-r2-curriculum/eval_s1/results.json"}
SET = "experiments/test_sets/rendezvous_large.json"
PUSH = "runs/d2-steering-night5/l2-s2/model.zip"
E = "experiments/d2-rendezvous/r5-bc-warmstart"
STEPS = ("scripted", "collect", "bc", "bc_eval", "s1", "s2", "eval", "gifs")
SEEDS = {"s1": 1, "s2": 2}
LABEL = {"bc": "BC alone (before PPO)", "s1": "BC warm start (s1)", "s2": "BC warm start (s2)"}
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


class Run:
    def __init__(self, dry: bool, deadline: str):
        self.dry = dry
        self.dir = os.path.join(ROOT, "runs", "d2-rendezvous-r5-bc-warmstart" + ("-dry" if dry else ""))
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
        self.train_args += ["--init", os.path.relpath(os.path.join(self.dir, "bc", "bc.zip"), ROOT)]
        self.n_gifs = 2 if dry else N_GIFS
        self.collect_args = ["--episodes", "40", "--workers", "4"] if dry else []
        self.bc_args = ["--max-epochs", "5"] if dry else []
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
        """The seed's best evaluated checkpoint (best.zip), else its final model.zip; bc/bc.zip for "bc"."""
        if run == "bc":
            return os.path.join(self.dir, "bc", "bc.zip")
        best = os.path.join(self.dir, run, "best.zip")
        return best if os.path.exists(best) else os.path.join(self.dir, run, "model.zip")

    def best_info(self, run):
        p = os.path.join(self.dir, run, "best.json")
        return json.load(open(p)) if os.path.exists(p) else None

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

    def step_collect(self):
        ok, logp = self.sh("collect", [sys.executable, "scripts/rl/bc_rendezvous.py", "collect", "--config", CONFIG,
                                       "--out", os.path.relpath(os.path.join(self.dir, "bc", "demos.npz"), ROOT), *self.collect_args])
        self.forward(logp, "collect", ("collected",))
        return ok

    def step_bc(self):
        ok, logp = self.sh("bc", [sys.executable, "scripts/rl/bc_rendezvous.py", "train", "--config", CONFIG,
                                  "--data", os.path.relpath(os.path.join(self.dir, "bc", "demos.npz"), ROOT),
                                  "--out", os.path.relpath(os.path.join(self.dir, "bc"), ROOT), *self.bc_args])
        self.forward(logp, "bc", ("epoch ", "BC done"))
        return ok

    def step_bc_eval(self):
        ok = self.pipeline("bc_eval", os.path.relpath(self.model("bc"), ROOT), "bc")
        e = self.episodes("bc")
        if ok and e:
            arr = sum(x["arrived"] for x in e)
            pe = sum(x["pos_err_cm"][d] for x in e for d in x["pos_err_cm"]) / (2 * len(e))
            ye = sum(x["yaw_err_deg"][d] for x in e for d in x["yaw_err_deg"]) / (2 * len(e))
            self.log(f"BC alone: docked {arr}/{len(e)} ({rate(arr, len(e))}), end-to-end push success "
                     f"{rate(sum(x['push_success'] for x in e), len(e))}, position {pe:.1f} cm, heading {ye:.1f} deg")
            if arr == 0:
                for run in SEEDS:
                    self.skip[run] = (f"BC alone docked 0 of the {len(e)} starts: the demonstrations or the cloning are broken; "
                                      "debug before PPO")
        return ok

    def forward(self, logp, step, prefixes):
        if os.path.exists(logp):
            for line in open(logp):
                if line.strip().startswith(prefixes):
                    self.log(f"{step}: {line.strip()}")

    def step_train(self, run):
        ok, logp = self.sh(run, [sys.executable, "scripts/rl/train_rendezvous.py", "--config", CONFIG, "--seed", str(SEEDS[run]),
                                 "--out", os.path.relpath(os.path.join(self.dir, run), ROOT), *self.train_args])
        if os.path.exists(logp):
            for line in open(logp):
                line = line.strip()
                if line.startswith(("curriculum:", "training docking by curriculum level", "early-stop:")) or line.startswith("aborted early:"):
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
            elif run not in self.skip and not os.path.exists(os.path.join(self.dir, run, "abort.json")):
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
        best, scr = self.best_seed() or ("bc" if self.episodes("bc") else None), self.episodes("scripted")
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
                                     "--right", os.path.relpath(self.model(best), ROOT), "--right-label", "BC alone" if best == "bc" else f"trained {best}",
                                     "--push", PUSH, "--out", os.path.relpath(gdir, ROOT)])
            ok &= rc
        json.dump({"seed": best, "starts": pick}, open(os.path.join(gdir, "picked.json"), "w"))
        return ok

    def run(self):
        free = shutil.disk_usage(ROOT).free / 1e9
        self.log(f"start ({'dry run' if self.dry else 'rendezvous r5-bc-warmstart'}); no new step after {self.deadline:%Y-%m-%d %H:%M}; "
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
            fn = {"scripted": self.step_scripted, "collect": self.step_collect, "bc": self.step_bc,
                  "bc_eval": self.step_bc_eval, "eval": self.step_eval, "gifs": self.step_gifs}.get(step) or \
                (lambda s=step: self.step_train(s))
            try:
                ok = fn()
            except Exception as e:                                # a bug in a step must not end the run
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
        for f in ("loss.jsonl", "bc.json", "demos.json"):
            src = os.path.join(self.dir, "bc", f)
            if os.path.exists(src):
                os.makedirs(os.path.join(self.exp, "results", "bc"), exist_ok=True)
                shutil.copy(src, os.path.join(self.exp, "results", "bc", f))
        for name in ("scripted", "bc", *SEEDS):
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

    def bc_section(self):
        """Demonstrations, the BC loss curve and BC alone's pipeline result."""
        b = os.path.join(self.dir, "bc")
        demos = json.load(open(os.path.join(b, "demos.json"))) if os.path.exists(os.path.join(b, "demos.json")) else None
        info = json.load(open(os.path.join(b, "bc.json"))) if os.path.exists(os.path.join(b, "bc.json")) else None
        rows = [json.loads(x) for x in open(os.path.join(b, "loss.jsonl")) if x.strip()] if os.path.exists(os.path.join(b, "loss.jsonl")) else []
        L = ["## Behavioral cloning", ""]
        if demos:
            L.append(f"- **Demonstrations:** {demos['episodes']} scripted episodes on randomized training starts "
                     f"({demos['dist_m'][0]:.2f}-{demos['dist_m'][1]:.2f} m), {demos['pairs']} per-duck (observation, action) "
                     f"pairs; the scripted coordinator docked {100 * demos['docking_rate']:.1f}% of them (outcomes "
                     f"{demos['outcomes']}); {demos['wall_s'] / 60:.1f} min.")
        if info:
            bb = info["best"]
            L.append(f"- **Training:** {info['pairs_train']} train / {info['pairs_val']} validation pairs (split by episode, "
                     f"{info['episodes_val']} validation episodes); stopped after {info['epochs_run']} epochs "
                     f"({'validation loss plateaued' if info['stopped'] == 'plateau' else 'the epoch limit'}); best epoch "
                     f"{bb['epoch']}: validation action MSE {bb['val_action_mse']:.4f} (train {bb['train_action_mse']:.4f}; "
                     f"for scale, the scripted actions' variance is {info['action_var']:.4f}), validation value MSE "
                     f"{bb['val_value_mse']:.2f}.")
        if rows:
            step = max(1, len(rows) // 10)
            pick = sorted({r["epoch"] for r in rows[::step]} | {rows[-1]["epoch"], info["best"]["epoch"] if info else 1})
            L += ["", "**BC loss curve** (every epoch in `results/bc/loss.jsonl`)", "",
                  "| epoch | train action MSE | val action MSE | train value MSE | val value MSE |", "|---|---|---|---|---|"]
            for r in rows:
                if r["epoch"] in pick:
                    L.append(f"| {r['epoch']} | {r['train_action_mse']:.4f} | {r['val_action_mse']:.4f} | "
                             f"{r['train_value_mse']:.2f} | {r['val_value_mse']:.2f} |")
        e = self.episodes("bc")
        if e:
            arr = sum(x["arrived"] for x in e)
            pe = sum(x["pos_err_cm"][d] for x in e for d in x["pos_err_cm"]) / (2 * len(e))
            ye = sum(x["yaw_err_deg"][d] for x in e for d in x["yaw_err_deg"]) / (2 * len(e))
            L += ["", f"- **BC alone, before PPO (full pipeline, {len(e)} starts):** docked within 50 steps "
                  f"{rate(arr, len(e))}, end-to-end push success {rate(sum(x['push_success'] for x in e), len(e))}, "
                  f"position / heading error at handoff {pe:.1f} cm / {ye:.1f} deg."
                  + (" **Gate failed: PPO was not started.**" if arr == 0 else "")]
        return L + [""]

    def curriculum_section(self):
        """Training episodes' docking rate per curriculum level (from evals.jsonl) and whether any worker advanced."""
        levels = ["15-20 cm", "20-40 cm", "40-60 cm", "60-80 cm"]
        L = []
        for run in SEEDS:
            p = os.path.join(self.dir, run, "evals.jsonl")
            if not os.path.exists(p):
                continue
            rows = [json.loads(x) for x in open(p) if x.strip()]
            if not rows or "train_by_level" not in rows[-1]:
                continue
            seen = sorted({int(k) for r in rows for k in r.get("train_by_level", {})})
            L += [f"**Curriculum, {run}** (training episodes' docking rate per level, between evals; level 0 = "
                  f"{levels[0]} starts)", "", "| duck steps | " + " | ".join(f"level {k} ({levels[k] if k < len(levels) else '?'})" for k in seen) + " |",
                  "|---|" + "---|" * len(seen)]
            for r in rows:
                cells = []
                for k in seen:
                    c = r.get("train_by_level", {}).get(str(k))
                    cells.append(f"{c['arrived']}/{c['episodes']} ({100 * c['arrived'] / max(c['episodes'], 1):.1f}%)" if c else "")
                L.append(f"| {r['step']} | " + " | ".join(cells) + " |")
            top = max(seen) if seen else 0
            log = os.path.join(self.dir, "logs", run + ".log")
            moves = sum(1 for x in open(log) if x.startswith("curriculum:")) if os.path.exists(log) else 0
            L += ["", f"- **Advanced past the first level (15-20 cm)?** " + (
                f"yes: training episodes reached level {top} ({levels[top]}); {moves} level changes across workers."
                if top > 0 else "no: every training episode stayed at level 0 (15-20 cm starts)."), ""]
        return L

    def summary(self) -> str:
        eps = {n: self.episodes(n) for n in ("scripted", "bc", *SEEDS)}
        for name, path in PREV.items():
            p = os.path.join(ROOT, path)
            eps[name] = json.load(open(p))["episodes"] if os.path.exists(p) else None
        names = ("scripted", *PREV, "bc", *SEEDS)
        have = [n for n in names if eps[n]]
        L = ["# D2 rendezvous, r5-bc-warmstart: behavioral cloning of the scripted coordinator, then PPO fine-tuning", "",
             f"*Written {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/rl/run_r5_bc_warmstart.py`"
             + (" (DRY RUN: tiny settings, numbers mean nothing)" if self.dry else "") + ".*", "", "## Steps", "",
             "| step | status | finished |", "|---|---|---|"]
        for s in STEPS:
            p = os.path.join(self.dir, "steps", s + ".done")
            status = "skipped (" + self.skip[s] + ")" if s in self.skip else ("done" if os.path.exists(p) else "not done")
            L.append(f"| {s} | {status} | {json.load(open(p))['end'] if os.path.exists(p) else ''} |")
        L += ["", "## Setup", "",
              "- **Why this run:** runs r1-r4 trained PPO from random weights and never docked, with four reward "
              "designs; in runs r2-r4 the curriculum never left its first level (15-20 cm starts), where training "
              "docked under 0.5% of episodes. Random exploration does not find the 3 cm / 15 deg docking target "
              "(`experiments/d2-rendezvous/r4-approach-bonus/SUMMARY.md`).",
              "- **The change (the starting policy only):** behavioral cloning (BC) first. The scripted coordinator "
              "drives randomized training starts (never the 200 eval starts; 15-80 cm), every step's per-duck "
              "(observation, action) pair is recorded, and the same network as runs r1-r4 is trained to output the "
              "scripted action (MSE; its value head is also fit to the demonstrations' returns). PPO then fine-tunes "
              "from those weights, with the action noise starting at std 0.37 instead of PPO's default 1.0 "
              "(`experiments/d2-rendezvous/r5-bc-warmstart.yaml`, `bc:`).",
              "- **Same as r4:** the reward (distance and heading shaping with heading weight 0.8, the holding "
              "bonus, the smooth final-approach term, collision and timeout penalties, no partial or arrival bonus), "
              "the curriculum (15-20 cm starts, widening to 20-40, 40-60, 60-80 cm once the training docking rate over "
              f"50,000 duck steps exceeds 60%, per worker), observations, 50-step episodes, and early stop (a seed still "
              f"at 0% docking at {EARLY_STOP_STEP} PPO steps aborts, the BC phase not counted; if s1 aborts, s2 is "
              "skipped).",
              "- **Checkpoint evaluated:** each seed's best.zip, the 200-start eval with the most arrivals (ties: lower "
              "heading error, then position error)" + "".join(
                  f"; {r}: step {b['step']} ({b['arrived']}/{b['n']} arrived, {b['pos_err_cm_mean']:.1f} cm, "
                  f"{b['yaw_err_deg_mean']:.1f} deg)" for r in SEEDS if (b := self.best_info(r))) + ".",
              "- **Runs r4, r3 and r2 rows:** each run's seed 1 best checkpoint (400k steps; all aborted there and "
              "skipped seed 2) through the same pipeline, from " + ", ".join(f"`{p}`" for p in PREV.values()) + ".",
              "- **Everything else as runs r1 and r2:** PPO from scratch, seeds 1 and 2, configs/copush.yaml's PPO (8 envs, "
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
        L += self.bc_section()
        L += self.curriculum_section()
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
            L.append(f"| {LABEL.get(n, n)} | {rate(len(arr), len(e))} | {rate(sum(x['push_success'] for x in e), len(e))} | "
                     f"{sum(x['push_success'] for x in arr)} of {len(arr)} | {ms} | {pe:.1f} cm / {ye:.1f} deg | "
                     f"{sum(sum(x['hit_box'].values()) for x in e)} ({sum(1 for x in e if any(x['hit_box'].values()))}) | "
                     f"{sum(x['hit_ducks'] for x in e)} ({sum(1 for x in e if x['hit_ducks'])}) |")
        L += ["", "**By start kind** (end-to-end push success)", "", "| controller | " + " | ".join(KINDS) + " |", "|---|" + "---|" * len(KINDS)]
        for n in have:
            L.append(f"| {LABEL.get(n, n)} | " + " | ".join(rate(sum(x["push_success"] for x in eps[n] if x["kind"] == k),
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
        for pname in ("bc", *PREV):
            if not (eps[pname] and trained):
                continue
            prev, short = eps[pname], ("BC alone" if pname == "bc" else pname.split(" (")[0])
            n = min(len(prev), *(len(eps[r]) for r in trained))
            L += ["", f"## Against {short} (same 200 starts, paired)", ""]
            for key, label, unit, f in (
                    ("arrived", "arrival within 50 steps", "points", lambda x: 100.0 * x["arrived"]),
                    ("push", "end-to-end push success", "points", lambda x: 100.0 * x["push_success"]),
                    ("yaw", "heading error at handoff (mean of the two ducks)", "deg", lambda x: sum(x["yaw_err_deg"].values()) / 2),
                    ("pos", "position error at handoff (mean of the two ducks)", "cm", lambda x: sum(x["pos_err_cm"].values()) / 2)):
                a = [{"v": sum(f(eps[r][i]) for r in trained) / len(trained)} for i in range(n)]
                b = [{"v": f(prev[i])} for i in range(n)]
                p = self.paired(a, b, "v")
                if p is None:
                    continue
                m, lo, hi = p
                seeds = [sum(f(eps[r][i]) for i in range(n)) / n for r in trained]
                base = sum(f(x) for x in prev[:n]) / n
                verdict = ("no measurable difference" if lo <= 0 <= hi else "measurable difference")
                if len(trained) < 2 and verdict != "no measurable difference":
                    verdict += " (one seed only: preliminary)"
                L.append(f"- {label}: BC warm start (seeds averaged) minus {short} {m:+.1f} {unit} ({lo:+.1f} to {hi:+.1f}); "
                         f"BC warm start seeds {', '.join(f'{s:.1f}' for s in seeds)} vs {short} {base:.1f}: **{verdict}**")
        g = os.path.join(self.exp, "gifs")
        if os.path.isdir(g):
            picked = json.load(open(os.path.join(g, "picked.json"))) if os.path.exists(os.path.join(g, "picked.json")) else {}
            L += ["", f"## Clips (scripted left, trained {picked.get('seed', '')} right; then the same push policy)", ""]
            for f in sorted(x for x in os.listdir(g) if x.endswith(".gif")):
                L += [f"**{f.split('_')[0]}**", "", f"![{f}](gifs/{f})", ""]
        L += ["", "Per-episode results: `runs/d2-rendezvous-r5-bc-warmstart/eval_<controller>/results.json` (git-ignored); the tables "
              "above come from them, and `results/<controller>/results.md` has the full per-kind breakdown."]
        return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--deadline", default="09:00", help="no new step starts after this local time (HH:MM)")
    a = ap.parse_args()
    job = Run(a.dry_run, a.deadline)
    lock = os.path.join(job.dir, "lock")
    if os.path.exists(lock):
        try:
            os.kill(int(open(lock).read() or 0), 0)
            print(f"already running; remove {lock} if it is not")
            return 1
        except (OSError, ValueError):
            pass
    open(lock, "w").write(str(os.getpid()))
    try:
        job.run()
    finally:
        if os.path.exists(lock):
            os.remove(lock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
