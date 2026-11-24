#!/usr/bin/env python3
"""Rendezvous run r7-long-payout: r6-dock-payout (docking payout, BC warm start, then PPO) trained longer. r6 docked
87.0% (s1) and 75.0% (s2) on the 200 test starts with no collapse, and s1 was still improving at its last eval (2M
steps). This run's change: 3M PPO duck steps per seed instead of 2M (experiments/d2-rendezvous/r7-long-payout.yaml).
Every eval's checkpoint is kept (train_rendezvous.py --keep-checkpoints), and checkpoints are picked on the check set
(experiments/test_sets/rendezvous_check.json), never on the test set. No BC training: PPO starts from r6's bc.zip
(copied, sha256 checked), so the comparison with r6 is about PPO length only. Reward, curriculum, observations, PPO
settings, early stop and pipeline are r6's.

    caffeinate -is scripts/rl.sh scripts/rl/run_r7_long_payout.py
    scripts/rl.sh scripts/rl/run_r7_long_payout.py --dry-run        # tiny settings into runs/d2-rendezvous-r7-long-payout-dry/

Steps (each marked done in runs/d2-rendezvous-r7-long-payout/steps/, so a restart skips what is finished; training resumes
from its newest checkpoint):
  init      copy r6's bc/bc.zip into bc/ (the PPO starting policy) and record its sha256
  scripted  the scripted rendezvous baseline through the full pipeline on the 200 test starts
  s1, s2    scripts/rl/train_rendezvous.py --init bc/bc.zip --keep-checkpoints, seeds 1 and 2, 3M PPO duck steps each,
            evals at step 0 (the BC weights) and every 200k steps on the CHECK set (rendezvous alone, 50 steps, the
            training ending); every one of those checkpoints is kept in sN/checkpoints/. best.zip = the check-set eval
            with the most dockings (ties: lower heading error, then position error). --early-stop-step 400000: if an
            eval at or after 400k PPO steps finds 0 dockings the seed stops there, and if it was s1, s2 is skipped
  eval      per seed, on the 200 TEST starts, full pipeline (rendezvous up to 50 steps, then the frozen push policy):
            the check-set pick (best.zip), the 2M checkpoint and the final checkpoint (one eval per distinct checkpoint)
  gifs      side-by-side clips (scripted left, the better seed's check-set pick right)
STOP file (runs/d2-rendezvous-r7-long-payout/STOP): the current step finishes, no new one starts. No new step starts
after --deadline (12:00). progress.log carries each training run's eval, curriculum and early-stop lines. SUMMARY.md
(experiments/d2-rendezvous/r7-long-payout/) is written at the end from whatever finished.
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

CONFIG = "experiments/d2-rendezvous/r7-long-payout.yaml"
NAME = "r7-long-payout"
R6 = "runs/d2-rendezvous-r6-dock-payout"
R6_BC = f"{R6}/bc/bc.zip"
SET = "experiments/test_sets/rendezvous_large.json"     # the test set: results only
CHECK_SET = "experiments/test_sets/rendezvous_check.json"   # the check set: checkpoint picking only
PICK_SET = CHECK_SET
PUSH = "runs/d2-steering-night5/l2-s2/model.zip"
E = f"experiments/d2-rendezvous/{NAME}"
STEPS = ("init", "scripted", "s1", "s2", "eval", "gifs")
SEEDS = {"s1": 1, "s2": 2}
MID_STEP = 2000000                 # r6's length: the checkpoint that shows what steps 2M-3M added
EARLY_STOP_STEP = 400000
N_GIFS = 6
KINDS = ("uniform", "near_symmetric", "wrong_side")
# r6's official numbers: final checkpoints (picked on the check set), test set, full pipeline
R6_OFFICIAL = {"s1": f"{R6}/reselect/test_s1_final/results.json", "s2": f"{R6}/reselect/test_s2_final/results.json"}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else "missing"


def pct(x):
    return "n/a" if x is None else f"{max(0.0, 100 * x):.1f}%"


def rate(k, n):
    lo, hi = wilson(k, n)
    return f"{pct(k / n)} ({pct(lo)} to {pct(hi)})" if n else "n/a"


def err(e, key):
    return sum(e[key].values()) / 2


def mean_ci_text(xs, unit):
    m, h = mean_ci(xs)
    return f"{m:.1f} {unit} ({m - h:.1f} to {m + h:.1f})"


def paired(a, b):
    d = [x - y for x, y in zip(a, b)]
    m, h = mean_ci(d)
    return m, m - h, m + h


def verdict(lo, hi, seed_rates, base, rule):
    """rule "fixed": the paired interval excludes 0 AND both seed rates are on the same side of base (success rates
    against scripted, as every run); rule "interval": the paired interval alone (errors, and run-vs-run comparisons)."""
    if rule == "fixed":
        side = len(seed_rates) == 2 and (all(s > base for s in seed_rates) or all(s < base for s in seed_rates))
        if lo > 0 and side:
            return "measurably higher"
        if hi < 0 and side:
            return "measurably lower"
        return "no measurable difference" + (" (one seed only)" if len(seed_rates) < 2 else "")
    return "no measurable difference" if lo <= 0 <= hi else ("measurably higher" if lo > 0 else "measurably lower")


def ckpt_step(path):
    b = os.path.basename(path)
    return int(b[len("ckpt_"):-len(".zip")]) if b.startswith("ckpt_") else None


class Run:
    def __init__(self, dry: bool, deadline: str):
        self.dry = dry
        self.dir = os.path.join(ROOT, "runs", f"d2-rendezvous-{NAME}" + ("-dry" if dry else ""))
        self.exp = os.path.join(self.dir, "summary") if dry else os.path.join(ROOT, E)
        for d in ("logs", "steps"):
            os.makedirs(os.path.join(self.dir, d), exist_ok=True)
        now = dt.datetime.now()
        hh, mm = map(int, deadline.split(":"))
        self.deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if self.deadline <= now:
            self.deadline += dt.timedelta(days=1)
        self.n = 10 if dry else 0                               # pipeline starts (0 = all 200)
        self.mid = 4096 if dry else MID_STEP
        self.train_args = (["--steps", "12288", "--eval-every", "4096", "--eval-starts", "8", "--early-stop-step", "4096"]
                           if dry else ["--early-stop-step", str(EARLY_STOP_STEP)])
        self.train_args += ["--init", os.path.relpath(os.path.join(self.dir, "bc", "bc.zip"), ROOT), "--keep-checkpoints",
                            "--eval-set", PICK_SET]
        self.n_gifs = 1 if dry else N_GIFS
        self.skip = {}

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

    def rows(self, run):
        """The seed's check-set evals (evals.jsonl), one per kept checkpoint."""
        p = os.path.join(self.dir, run, "evals.jsonl")
        return [json.loads(x) for x in open(p) if x.strip()] if os.path.exists(p) else []

    def checkpoints(self, run):
        """{label: (step, path)} for the test-set evals: the check-set pick, the mid (2M) and the final checkpoint;
        labels sharing a checkpoint point at one eval."""
        d = os.path.join(self.dir, run)
        best = os.path.join(d, "best.json")
        out = {}
        if os.path.exists(best):
            out["pick"] = (json.load(open(best))["step"], os.path.join(d, "best.zip"))
        mid = os.path.join(d, "checkpoints", f"ckpt_{self.mid}.zip")
        if os.path.exists(mid):
            out["mid"] = (self.mid, mid)
        res = os.path.join(d, "results.json")
        if os.path.exists(res):
            st = json.load(open(res))["steps"]
            p = os.path.join(d, "checkpoints", f"ckpt_{st}.zip")
            out["final"] = (st, p if os.path.exists(p) else os.path.join(d, "model.zip"))
        return out

    def evaldir(self, name):
        return os.path.join(self.dir, f"eval_{name}")

    def episodes(self, name):
        p = os.path.join(self.evaldir(name), "results.json")
        return json.load(open(p))["episodes"] if os.path.exists(p) else None

    def pipeline(self, step, rendezvous, name):
        cmd = [sys.executable, "scripts/rl/rendezvous_eval.py", "eval", "--rendezvous", rendezvous, "--push", PUSH,
               "--set", SET, "--out", os.path.relpath(self.evaldir(name), ROOT)]
        if self.n:
            cmd += ["--starts", str(self.n)]
        ok, _ = self.sh(step, cmd)
        return ok

    # ── steps ───────────────────────────────────────────────────────────────
    def step_init(self):
        src = os.path.join(ROOT, R6_BC)
        if not os.path.exists(src):
            self.crash(f"init: {R6_BC} missing")
            return False
        os.makedirs(os.path.join(self.dir, "bc"), exist_ok=True)
        dst = os.path.join(self.dir, "bc", "bc.zip")
        shutil.copy(src, dst)
        for f in ("bc.json", "loss.jsonl", "demos.json"):
            if os.path.exists(os.path.join(ROOT, R6, "bc", f)):
                shutil.copy(os.path.join(ROOT, R6, "bc", f), os.path.join(self.dir, "bc", f))
        h = sha(dst)
        if h != sha(src):
            self.crash("init: copy of r6's bc.zip differs")
            return False
        json.dump({"from": R6_BC, "sha256": h}, open(os.path.join(self.dir, "bc", "source.json"), "w"), indent=1)
        self.log(f"init: PPO starts from {R6_BC} (sha256 {h[:16]}...)")
        return True

    def step_scripted(self):
        return self.pipeline("scripted", "scripted", "scripted")

    def step_train(self, run):
        ok, logp = self.sh(run, [sys.executable, "scripts/rl/train_rendezvous.py", "--config", CONFIG, "--seed", str(SEEDS[run]),
                                 "--out", os.path.relpath(os.path.join(self.dir, run), ROOT), *self.train_args])
        if os.path.exists(logp):
            for line in open(logp):
                line = line.strip()
                if line.startswith(("eval @", "curriculum:", "training docking by curriculum level", "early-stop:", "aborted early:")):
                    self.log(f"{run}: {line}")
        st = self.stability(run)
        if st:
            self.log(f"{run}: {st['text']}")
        kept = sorted(os.listdir(os.path.join(self.dir, run, "checkpoints"))) if os.path.isdir(os.path.join(self.dir, run, "checkpoints")) else []
        self.log(f"{run}: {len(kept)} checkpoints kept")
        if ok:
            p = os.path.join(self.dir, run, "abort.json")
            if os.path.exists(p) and run == "s1":
                self.skip["s2"] = f"s1 aborted early ({json.load(open(p))['reason']}); the same setup would likely do the same"
        return ok

    def stability(self, run):
        """Did docking on the check-set evals stay near its peak? The last eval against the peak by 95% intervals."""
        rows = self.rows(run)
        if len(rows) < 2:
            return None
        peak = max(rows, key=lambda r: r["arrived"])
        after = [r for r in rows if r["step"] > peak["step"]]
        last, low = rows[-1], (min(after, key=lambda r: r["arrived"]) if after else None)
        plo, _ = wilson(peak["arrived"], peak["n"])
        _, lhi = wilson(last["arrived"], last["n"])
        if not after:
            v = "still at its peak at the last eval"
        elif lhi < plo:
            v = "fell measurably after its peak (the last eval's 95% interval is below the peak's): collapsed"
        else:
            v = "stayed near its peak (the last eval's 95% interval overlaps the peak's): no collapse"
        text = (f"check-set docking peaked at {peak['arrived']}/{peak['n']} (step {peak['step']}) and was {last['arrived']}/"
                f"{last['n']} at the last eval (step {last['step']})" + (f", lowest after the peak {low['arrived']}/{low['n']} "
                f"(step {low['step']})" if low else "") + f": {v}")
        return {"peak": peak, "last": last, "low": low, "text": text}

    def step_eval(self):
        ok = True
        for run in SEEDS:
            if run in self.skip:
                continue
            seen = {}
            for label, (step, path) in self.checkpoints(run).items():
                if not os.path.exists(path):
                    self.crash(f"eval: {run} {label} checkpoint {path} missing")
                    ok = False
                    continue
                key = sha(path)
                if key in seen:                                     # same weights: link the earlier eval
                    json.dump({"same_as": seen[key], "step": step}, open(os.path.join(self.dir, f"eval_{run}_{label}.link"), "w"))
                    continue
                seen[key] = f"{run}_{label}"
                ok &= self.pipeline("eval", os.path.relpath(path, ROOT), f"{run}_{label}")
            json.dump({k: {"step": s, "sha256": sha(p), "path": os.path.relpath(p, ROOT)} for k, (s, p) in self.checkpoints(run).items()},
                      open(os.path.join(self.dir, f"eval_{run}_checkpoints.json"), "w"), indent=1)
        return ok

    def test_eps(self, run, label):
        """Test-set episodes of a seed's checkpoint (pick / mid / final), following links between identical ones."""
        e = self.episodes(f"{run}_{label}")
        if e is None:
            link = os.path.join(self.dir, f"eval_{run}_{label}.link")
            if os.path.exists(link):
                e = self.episodes(json.load(open(link))["same_as"])
        return e

    def step_gifs(self):
        picks = {r: self.test_eps(r, "pick") for r in SEEDS}
        rates = {r: sum(x["push_success"] for x in e) for r, e in picks.items() if e}
        scr = self.episodes("scripted")
        if not rates or scr is None:
            self.crash("gifs: missing pipeline results")
            return False
        best = max(rates, key=lambda r: (rates[r], -SEEDS[r]))
        tr = picks[best]
        differ = [e["i"] for e, s in zip(tr, scr) if e["push_success"] != s["push_success"]]
        fails = [e["i"] for e in tr if not e["push_success"] and e["i"] not in differ]
        wins = [e["i"] for e in tr if e["push_success"] and e["i"] not in differ]
        pick = (differ[: self.n_gifs - 1] + fails[:1] + wins)[: self.n_gifs]
        gdir = os.path.join(self.dir, "gifs")
        ok = True
        for i in pick:
            rc, _ = self.sh("gifs", [sys.executable, "scripts/rl/rendezvous_gif.py", "--start", str(i), "--left", "scripted",
                                     "--right", os.path.relpath(os.path.join(self.dir, best, "best.zip"), ROOT),
                                     "--right-label", f"trained {best}", "--push", PUSH, "--out", os.path.relpath(gdir, ROOT)])
            ok &= rc
        json.dump({"seed": best, "starts": pick}, open(os.path.join(gdir, "picked.json"), "w"))
        return ok

    def run(self):
        free = shutil.disk_usage(ROOT).free / 1e9
        self.log(f"start ({'dry run' if self.dry else 'rendezvous ' + NAME}); no new step after {self.deadline:%Y-%m-%d %H:%M}; "
                 f"free disk {free:.0f} GB")
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
            fn = {"init": self.step_init, "scripted": self.step_scripted, "eval": self.step_eval,
                  "gifs": self.step_gifs}.get(step) or (lambda s=step: self.step_train(s))
            try:
                ok = fn()
            except Exception as e:
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
        names = ["scripted"] + [f"{r}_{lab}" for r in SEEDS for lab in ("pick", "mid", "final")]
        for name in names:
            src = os.path.join(self.evaldir(name), "results.md")
            if os.path.exists(src):
                os.makedirs(os.path.join(self.exp, "results", name), exist_ok=True)
                shutil.copy(src, os.path.join(self.exp, "results", name, "results.md"))
        for run in SEEDS:
            for f in ("evals.jsonl", "abort.json", "best.json"):
                src = os.path.join(self.dir, run, f)
                if os.path.exists(src):
                    os.makedirs(os.path.join(self.exp, "results", run), exist_ok=True)
                    shutil.copy(src, os.path.join(self.exp, "results", run, f))
            src = os.path.join(self.dir, f"eval_{run}_checkpoints.json")
            if os.path.exists(src):
                shutil.copy(src, os.path.join(self.exp, "results", run, "test_checkpoints.json"))
        g = os.path.join(self.dir, "gifs")
        if os.path.isdir(g):
            os.makedirs(os.path.join(self.exp, "gifs"), exist_ok=True)
            for f in sorted(os.listdir(g)):
                if f.endswith(".gif") or f == "picked.json":
                    shutil.copy(os.path.join(g, f), os.path.join(self.exp, "gifs", f))

    def curve_section(self):
        L = ["## Docking on the check set, every eval (every kept checkpoint)", "",
             "Rendezvous alone, 50 steps, the training ending, 200 check-set starts. Step 0 is r6's BC policy. "
             "**bold** = the seed's check-set pick (best.zip).", ""]
        runs = [r for r in SEEDS if self.rows(r)]
        if not runs:
            return L + ["No evals.", ""]
        steps = sorted({row["step"] for r in runs for row in self.rows(r)})
        picks = {r: (json.load(open(p))["step"] if os.path.exists(p := os.path.join(self.dir, r, "best.json")) else None) for r in runs}
        L += ["| duck steps | " + " | ".join(f"{r} docked (95% interval) | {r} pos / heading error" for r in runs) + " |",
              "|---|" + "---|---|" * len(runs)]
        for s in steps:
            cells = []
            for r in runs:
                row = next((x for x in self.rows(r) if x["step"] == s), None)
                if row is None:
                    cells += ["", ""]
                    continue
                c = rate(row["arrived"], row["n"])
                cells += [f"**{c}**" if s == picks[r] else c, f"{row['pos_err_cm_mean']:.1f} cm / {row['yaw_err_deg_mean']:.1f} deg"]
            L.append(f"| {s} | " + " | ".join(cells) + " |")
        L += ["", "**Did docking stay stable?**", ""]
        for r in runs:
            st = self.stability(r)
            if st:
                L.append(f"- **{r}:** {st['text']}.")
        L += ["", "**Curriculum** (training episodes' docking rate per level between evals; level 0 = 15-20 cm, 3 = 60-80 cm)", ""]
        for r in runs:
            changes = []
            prev = None
            for row in self.rows(r):
                lv = sorted(int(k) for k in row.get("train_by_level", {}))
                top = lv[-1] if lv else None
                if top is not None and top != prev:
                    changes.append(f"level {top} by step {row['step']}")
                    prev = top
            tot = self.rows(r)[-1].get("train_by_level_total", {})
            L.append(f"- **{r}:** " + (", ".join(changes) if changes else "no training episodes logged") + "; whole run: " +
                     ", ".join(f"level {k} {v['arrived']}/{v['episodes']} ({pct(v['arrived'] / max(v['episodes'], 1))})" for k, v in sorted(tot.items())) + ".")
        return L + [""]

    def summary(self) -> str:
        L = [f"# D2 rendezvous, {NAME}: r6's setup trained for 3M steps, checkpoints picked on the check set", "",
             f"*Written {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/rl/run_r7_long_payout.py`"
             + (" (DRY RUN: tiny settings, numbers mean nothing)" if self.dry else "") + ".*", "", "## Steps", "",
             "| step | status | finished |", "|---|---|---|"]
        for s in STEPS:
            p = os.path.join(self.dir, "steps", s + ".done")
            status = "skipped (" + self.skip[s] + ")" if s in self.skip else ("done" if os.path.exists(p) else "not done")
            L.append(f"| {s} | {status} | {json.load(open(p))['end'] if os.path.exists(p) else ''} |")
        src = os.path.join(self.dir, "bc", "source.json")
        bc = json.load(open(src)) if os.path.exists(src) else {}
        L += ["", "## Setup", "",
              "- **Why this run:** r6 (docking payout) docked 87.0% (s1) and 75.0% (s2) on the 200 test starts with no "
              "collapse, and s1 was still improving at its last eval (2M steps). Does training longer help?",
              "- **The change:** PPO length 2M -> 3M duck steps per seed (`experiments/d2-rendezvous/r7-long-payout.yaml`).",
              "- **Also different from r6 (bookkeeping, not behavior):** every eval's checkpoint is kept, and evals during "
              "training (and so best.zip) use the check set (`experiments/test_sets/rendezvous_check.json`), never the test set.",
              f"- **No BC training:** PPO starts from r6's BC policy (`{R6_BC}`, sha256 `{bc.get('sha256', 'n/a')[:16]}...`). r6's "
              "longer BC made no measurable difference, and reusing it keeps this comparison about PPO length.",
              "- **Same as r6:** the reward (distance and heading shaping, holding bonus, approach term, docking payout 0.5 x "
              "steps left, collision and timeout penalties), the curriculum (15-20 cm starts widening to 60-80 cm at 60% docking "
              "per worker), observations, 50-step episodes, PPO settings (configs/copush.yaml: 8 envs, n_steps 256, ent_coef "
              "0.01), seeds 1 and 2, early stop (0 dockings at 400k PPO steps aborts; s2 is skipped if s1 aborts), the push "
              f"policy after handoff (`{PUSH}`, sha256 `{sha(os.path.join(ROOT, PUSH))[:16]}...`) and the pipeline.",
              "- **Test set:** `experiments/test_sets/rendezvous_large.json`, 200 starts, full pipeline (rendezvous up to 50 "
              "steps, then the push policy for 100 steps). Evaluated: each seed's check-set pick, its 2M checkpoint (r6's "
              "length) and its final checkpoint.",
              "- **Measurable rule:** against scripted, the paired 95% interval (seeds averaged per start) excludes 0 and "
              "both seed rates are on the same side of scripted's; against r6 and for 2M vs 3M, the paired interval alone.", ""]
        L += self.curve_section()
        scr = self.episodes("scripted")
        r6 = {r: (json.load(open(os.path.join(ROOT, p)))["episodes"] if os.path.exists(os.path.join(ROOT, p)) else None)
              for r, p in R6_OFFICIAL.items()}
        rows = []                                               # (label, episodes)
        if scr:
            rows.append(("scripted", scr))
        for r in SEEDS:
            if r6.get(r):
                rows.append((f"r6 dock payout {r} (official: final 2M checkpoint, picked on the check set)", r6[r]))
        steps = {r: self.checkpoints(r) for r in SEEDS}
        for r in SEEDS:
            for lab, word in (("pick", "check-set pick"), ("mid", "2M checkpoint"), ("final", "final checkpoint")):
                e = self.test_eps(r, lab)
                if e:
                    st = steps[r].get(lab, (None,))[0]
                    rows.append((f"{'**' if lab == 'pick' else ''}r7 {r}, {word} (step {st}){'**' if lab == 'pick' else ''}", e))
        L += ["## Results on the 200 test starts (full pipeline)", "",
              "| controller | docked in 50 steps | end-to-end push success | position error at handoff | heading error at handoff |",
              "|---|---|---|---|---|"]
        for lab, e in rows:
            n = len(e)
            L.append(f"| {lab} | {rate(sum(x['arrived'] for x in e), n)} | {rate(sum(x['push_success'] for x in e), n)} | "
                     f"{mean_ci_text([err(x, 'pos_err_cm') for x in e], 'cm')} | {mean_ci_text([err(x, 'yaw_err_deg') for x in e], 'deg')} |")
        L += ["", "Errors: mean over the starts of the two ducks' mean, with a 95% interval for that mean. Rows with the same "
              "step are the same checkpoint.", "",
              "**By start kind** (end-to-end push success)", "", "| controller | " + " | ".join(KINDS) + " |", "|---|" + "---|" * len(KINDS)]
        for lab, e in rows:
            L.append(f"| {lab} | " + " | ".join(rate(sum(x["push_success"] for x in e if x["kind"] == k), sum(1 for x in e if x["kind"] == k))
                                                for k in KINDS) + " |")
        L += self.comparisons(scr, r6)
        L += self.behavior(rows)
        g = os.path.join(self.exp, "gifs")
        if os.path.isdir(g):
            picked = json.load(open(os.path.join(g, "picked.json"))) if os.path.exists(os.path.join(g, "picked.json")) else {}
            L += ["", f"## Clips (scripted left, r7 {picked.get('seed', '')} check-set pick right; then the same push policy)", ""]
            for f in sorted(x for x in os.listdir(g) if x.endswith(".gif")):
                L += [f"**{f.split('_')[0]}**", "", f"![{f}](gifs/{f})", ""]
        L += ["", f"Per-episode results: `runs/d2-rendezvous-{NAME}/eval_<seed>_<pick|mid|final>/results.json` (git-ignored); "
              "`results/` has each eval's results.md, each seed's check-set evals (evals.jsonl) and best.json. "
              f"Checkpoints: `runs/d2-rendezvous-{NAME}/sN/checkpoints/` (all kept)."]
        return "\n".join(L) + "\n"

    def comparisons(self, scr, r6):
        metrics = (("arrived", "docked in 50 steps", lambda x: 100.0 * x["arrived"], "points", True),
                   ("push", "end-to-end push success", lambda x: 100.0 * x["push_success"], "points", True),
                   ("yaw", "heading error at handoff", lambda x: err(x, "yaw_err_deg"), "deg", False),
                   ("pos", "position error at handoff", lambda x: err(x, "pos_err_cm"), "cm", False))
        L = []
        runs = [r for r in SEEDS if self.test_eps(r, "pick")]

        def block(title, mine, other, other_label, fixed):
            out = ["", f"## {title}", ""]
            n = min(len(other(None)), *(len(m) for m in mine.values()))
            for _, label, f, unit, is_rate in metrics:
                a = [sum(f(mine[r][i]) for r in mine) / len(mine) for i in range(n)]
                b = [f(x) for x in other(None)[:n]]
                m, lo, hi = paired(a, b)
                seeds = [sum(f(mine[r][i]) for i in range(n)) / n for r in mine]
                base = sum(b) / n
                v = verdict(lo, hi, seeds, base, "fixed" if fixed and is_rate else "interval")
                out.append(f"- {label}: r7 (seeds averaged) minus {other_label} {m:+.1f} {unit} ({lo:+.1f} to {hi:+.1f}); "
                           f"r7 seeds {', '.join(f'{s:.1f}' for s in seeds)} vs {other_label} {base:.1f}: **{v}**")
            return out

        if runs and scr:
            L += block("r7 check-set picks against scripted (same 200 starts, paired, fixed rule)",
                       {r: self.test_eps(r, "pick") for r in runs}, lambda _: scr, "scripted", True)
        if runs and all(r6.get(r) for r in runs):
            def r6avg(_):
                return [{"arrived": sum(r6[r][i]["arrived"] for r in runs) / len(runs),
                         "push_success": sum(r6[r][i]["push_success"] for r in runs) / len(runs),
                         "yaw_err_deg": {d: sum(r6[r][i]["yaw_err_deg"][d] for r in runs) / len(runs) for d in r6[runs[0]][i]["yaw_err_deg"]},
                         "pos_err_cm": {d: sum(r6[r][i]["pos_err_cm"][d] for r in runs) / len(runs) for d in r6[runs[0]][i]["pos_err_cm"]}}
                        for i in range(len(r6[runs[0]]))]
            L += block("r7 check-set picks against r6 official (seeds averaged, same 200 starts, paired)",
                       {r: self.test_eps(r, "pick") for r in runs}, r6avg, "r6", False)
            if all(self.test_eps(r, "final") for r in runs):
                L += block("r7 final checkpoints (3M) against r6 official (2M, seeds averaged, paired)",
                           {r: self.test_eps(r, "final") for r in runs}, r6avg, "r6", False)
        both = [r for r in runs if self.test_eps(r, "mid") and self.test_eps(r, "final")]
        if both:
            mids = {r: self.test_eps(r, "mid") for r in both}
            avg_mid = [{"arrived": sum(mids[r][i]["arrived"] for r in both) / len(both),
                        "push_success": sum(mids[r][i]["push_success"] for r in both) / len(both),
                        "yaw_err_deg": {d: sum(mids[r][i]["yaw_err_deg"][d] for r in both) / len(both) for d in mids[both[0]][i]["yaw_err_deg"]},
                        "pos_err_cm": {d: sum(mids[r][i]["pos_err_cm"][d] for r in both) / len(both) for d in mids[both[0]][i]["pos_err_cm"]}}
                       for i in range(len(mids[both[0]]))]
            L += block("Did steps 2M to 3M help? r7's final checkpoints against its own 2M checkpoints (same seeds, paired)",
                       {r: self.test_eps(r, "final") for r in both}, lambda _: avg_mid, "r7 at 2M", False)
            for r in both:
                a = sum(x["push_success"] for x in self.test_eps(r, "final"))
                b = sum(x["push_success"] for x in mids[r])
                c = sum(x["arrived"] for x in self.test_eps(r, "final"))
                d = sum(x["arrived"] for x in mids[r])
                L.append(f"- {r} alone: docked {d} -> {c} of 200, push success {b} -> {a} of 200 (2M -> final).")
        return L

    def behavior(self, rows):
        L = ["", "## Failures and collisions (test set)", "",
             "| controller | push endings | falls in rendezvous | duck-box hits (episodes) | duck-duck hits (episodes) | push share duck A (mean) |",
             "|---|---|---|---|---|---|"]
        for lab, e in rows:
            reasons = {}
            for x in e:
                reasons[x.get("push_reason", "n/a")] = reasons.get(x.get("push_reason", "n/a"), 0) + 1
            sh = [x["push_share_a"] for x in e if x.get("push_share_a") is not None]
            L.append(f"| {lab} | {', '.join(f'{k} {v}' for k, v in sorted(reasons.items()))} | {sum(x['fell_rv'] for x in e)} | "
                     f"{sum(sum(x['hit_box'].values()) for x in e)} ({sum(1 for x in e if any(x['hit_box'].values()))}) | "
                     f"{sum(x['hit_ducks'] for x in e)} ({sum(1 for x in e if x['hit_ducks'])}) | "
                     f"{pct(sum(sh) / len(sh)) if sh else 'n/a'} |")
        return L


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--deadline", default="12:00", help="HH:MM; no new step starts after it")
    a = ap.parse_args()
    Run(a.dry_run, a.deadline).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
