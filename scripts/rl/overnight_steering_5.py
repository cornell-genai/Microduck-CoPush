#!/usr/bin/env python3
"""D2 steering, night 5: train on wider duck start noise (levels L1 and L2), two seeds each, a fixed budget.

    scripts/rl.sh scripts/rl/overnight_steering_5.py              # the night (wrap it in caffeinate)
    scripts/rl.sh scripts/rl/overnight_steering_5.py --dry-run    # tiny end-to-end test in runs/d2-steering-night5-dry/

Steps, in this order (each is a subprocess with its own log, except `sets`):
  sets      write experiments/test_sets/stage1_L1_large.json and stage1_L2_large.json: the SAME 200 box poses as
            stage1_large.json (every episode uses the same per-start seed, 10000 + i), so only the duck start noise differs;
            the noise comes from the set's env config (experiments/d2-steering/night5/sets/L1|L2/config.yaml)
  a_eval    night 2's Run A seeds 1 and 2 on the L1 and L2 sets (deterministic): how much A drops with wider noise
  l1_s1     train Run L1 (night 2 Run A + L1 start noise), seed 1, warm start from A seed 1, 2,000,000 duck steps fixed
  l2_s1     Run L2, seed 1, warm start from A seed 1
  l1_s2     Run L1, seed 2, warm start from A seed 2
  l2_s2     Run L2, seed 2, warm start from A seed 2
  eval      A, L1 and L2 (seeds 1 and 2) on the clean, noisy, L1 and L2 sets, deterministic, 100-step limit, 8 workers
            (A on L1 and L2 comes from a_eval)
  gifs      4 per trained run from the L2 set (2 successes, 2 failures), the matching A seed on the left
experiments/d2-steering/night5/SUMMARY.md is written once, at the end (also after a STOP or the deadline).

Restart-safe: a finished step leaves <run dir>/steps/<name>.done and is skipped; a training step resumes from its last
checkpoint (scripts/rl/stage.py); a failing step goes to <run dir>/crash.log. progress.log, crash.log, lock and STOP live in
<run dir> (runs/d2-steering-night5/); `touch <run dir>/STOP` stops after the current step. No new step starts after the
deadline (the first 09:00 after launch, or --deadline HH:MM). Only final policies, eval files and final videos are kept.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ci_report import mean_ci, wilson, won  # noqa: E402

E = "experiments/d2-steering/night5"
BASE_SET = "experiments/test_sets/stage1_large.json"
SETS = {"clean": (BASE_SET, "experiments/stage1-random-box-pose/config.yaml"),
        "noisy": ("experiments/test_sets/stage1_noisy_large.json", "experiments/d2-steering/noisy-sets/config.yaml"),
        "L1": ("experiments/test_sets/stage1_L1_large.json", f"{E}/sets/L1/config.yaml"),
        "L2": ("experiments/test_sets/stage1_L2_large.json", f"{E}/sets/L2/config.yaml")}
SETNAME = {"clean": "clean (stage1_large)", "noisy": "noisy (stage1_noisy_large)", "L1": "L1 (stage1_L1_large)",
           "L2": "L2 (stage1_L2_large)"}
A = {"a_s1": "runs/d2-steering/night2/a-s1/model.zip", "a_s2": "runs/d2-steering/night2/a-s2/model.zip"}    # night 2, Run A
RUNS = {"l1_s1": ("l1", 1), "l2_s1": ("l2", 1), "l1_s2": ("l1", 2), "l2_s2": ("l2", 2)}
STEPS = ("sets", "a_eval", "l1_s1", "l2_s1", "l1_s2", "l2_s2", "eval", "gifs")
SIDES = ("< -15", "-15 to +15", "> +15")
LONG = "> +15"
LABEL = {"a_s1": "A seed 1 (night 2)", "a_s2": "A seed 2 (night 2)", "l1_s1": "L1 seed 1", "l1_s2": "L1 seed 2",
         "l2_s1": "L2 seed 1", "l2_s2": "L2 seed 2"}
ORDER = ("a_s1", "a_s2", "l1_s1", "l1_s2", "l2_s1", "l2_s2")
GROUPS = {"A": ("a_s1", "a_s2"), "L1": ("l1_s1", "l1_s2"), "L2": ("l2_s1", "l2_s2")}
WORKERS = 8
PIVOT_RUN = 3
BOTH_IDLE = 0.3
DRY_STARTS = 10
# the reset-only check made while building (scripts/rl/start_noise_check.py, 500 resets, training seeds 0..499)
RESET_CHECK = [
    "| level | std (limit) | redraw rate | out of redraws | duck down at first step | result |",
    "|---|---|---|---|---|---|",
    "| L1 | heading 10 deg (+-25), spacing 3 cm (+-6), setback 1.5 cm (+4.5 back / -2 forward) | 2.2% (11 of 511 draws) | 0 | 0 | pass |",
    "| L2 as first specified | heading 15 deg (+-30), spacing 4 cm (+-8), setback 2 cm (+6 / -2) | 7.4% (40 of 540) | 0 | 0 | FAIL (> 5%) |",
    "| L2, heading limit lowered by the rule | +-25 / +-20 / +-15 / +-10 deg | 7.7% / 7.2% / 6.5% / 0.0% | 0 | 0 | passes only at +-10 deg |",
    "| **L2 used** | heading 15 deg (+-30), spacing 4 cm (+-8), setback 2 cm (+6 back / **-1 forward**) | 0.0% (0 of 500) | 0 | 0 | pass |",
]
RESET_NOTE = ("Almost every L2 redraw was a duck turned more than 15 deg AND placed 1.5 to 2 cm forward, which nudges the box while "
              "settling. The 5-degree heading rule only passed at +-10 deg, narrower than L1's +-25, so (decided before launch) L2 "
              "keeps heading +-30 and tightens only the forward setback limit to 1 cm.")


def pct(x):
    return f"{100 * x:.0f}%"


def rate_str(k, n):
    lo, hi = wilson(k, n)
    return f"{pct(k / n)} ({pct(lo)} to {pct(hi)})" if n else "n/a"


def both_idle(r):
    return r["both_hold_steps"] / max(1, r["steps"]) >= BOTH_IDLE


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else "missing"


class Night:
    def __init__(self, dry: bool, deadline: str):
        self.dry = dry
        self.dir = os.path.join(ROOT, "runs", "d2-steering-night5" + ("-dry" if dry else ""))
        self.res = os.path.join(self.dir, "results") if dry else os.path.join(ROOT, E, "results")
        self.summary = os.path.join(self.dir if dry else os.path.join(ROOT, E), "SUMMARY.md")
        for d in ("logs", "steps", "configs", "sets"):
            os.makedirs(os.path.join(self.dir, d), exist_ok=True)
        now = dt.datetime.now()
        hh, mm = map(int, deadline.split(":"))
        self.deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if self.deadline <= now:
            self.deadline += dt.timedelta(days=1)
        self.sets = dict(SETS)
        self.cfgs = {"l1": f"{E}/run-l1/config.yaml", "l2": f"{E}/run-l2/config.yaml"}
        if dry:
            self._dry_inputs()

    # ── setup ───────────────────────────────────────────────────────────────
    def _abs(self, p):
        return p if os.path.isabs(p) else os.path.join(ROOT, p)

    def _subset(self, src, name, n_per_side):
        d = json.load(open(self._abs(src)))
        pick = []
        for lo, hi in ((-99, -15), (-15, 15), (15, 99)):
            pick += [s for s in d["starts"] if lo < s["dyaw"] <= hi][:n_per_side]
        d["starts"] = pick                     # ids kept: the start index i (and its seed) is the position in the list
        p = os.path.join(self.dir, "sets", name)
        json.dump(d, open(p, "w"), indent=1)
        return p

    def _dry_inputs(self):
        """Tiny copies: 10 starts per set (4 + 3 + 3 by side), a 6-start check set, runs of 6144 duck steps."""
        per = (4, 3, 3)

        def subset10(src, name):
            d = json.load(open(self._abs(src)))
            pick = []
            for (lo, hi), n in zip(((-99, -15), (-15, 15), (15, 99)), per):
                pick += [s for s in d["starts"] if lo < s["dyaw"] <= hi][:n]
            d["starts"] = [dict(s, id=i) for i, s in enumerate(pick)]
            p = os.path.join(self.dir, "sets", name)
            json.dump(d, open(p, "w"), indent=1)
            return p
        clean = subset10(BASE_SET, "clean.json")
        self.sets = {"clean": (clean, SETS["clean"][1]),
                     "noisy": (subset10(SETS["noisy"][0], "noisy.json"), SETS["noisy"][1]),
                     "L1": (os.path.join(self.dir, "sets", "L1.json"), SETS["L1"][1]),
                     "L2": (os.path.join(self.dir, "sets", "L2.json"), SETS["L2"][1])}
        self.dry_base = clean
        checks = self._subset("experiments/test_sets/stage1_checks.json", "checks.json", 2)
        for k, c in list(self.cfgs.items()):
            cfg = yaml.safe_load(open(self._abs(c)))
            cfg.update(out=os.path.join(self.dir, "train", f"{k}-s1"), results=os.path.join(self.dir, "train", k + "_results"),
                       check_set=checks, steps=6144, checkpoint_every=2048, max_videos=2)
            cfg["overrides"]["rl"] = {"eval_every": 2048}
            cfg["widen"].update(eval_every=2048, episodes=4)
            p = os.path.join(self.dir, "configs", k + ".yaml")
            yaml.safe_dump(cfg, open(p, "w"), sort_keys=False)
            self.cfgs[k] = p

    def out_dir(self, run):
        k, seed = RUNS[run]
        out = yaml.safe_load(open(self._abs(self.cfgs[k])))["out"]
        return self._abs(re.sub(r"-s\d+$", "", out.rstrip("/")) + f"-s{seed}")      # as scripts/rl/stage.py names it

    def model(self, name):
        if name in RUNS:
            return os.path.join(self.out_dir(name), "model.zip")
        return self._abs(A[name])

    def spec(self, name):
        return f"{name}={self.model(name)}@partner@standstill"

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

    def sh(self, step, cmd):
        """One command of a step, appended to the step's log; True when it succeeds, else a crash.log entry."""
        logp = os.path.join(self.dir, "logs", step + ".log")
        with open(logp, "a") as f:
            f.write(f"\n$ {' '.join(cmd)}\n")
            f.flush()
            rc = subprocess.call(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        if rc != 0:
            tail = open(logp).read().splitlines()[-30:]
            with open(os.path.join(self.dir, "crash.log"), "a") as f:
                f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} step {step} exit {rc}: {' '.join(cmd)}\n" + "\n".join(tail) + "\n\n")
        return rc == 0

    def compare(self, step, set_key, outname, names):
        out = os.path.join(self.res, outname)
        cj = os.path.join(out, "comparison.json")
        if os.path.exists(cj) and set(json.load(open(cj))["episodes"]) == set(names):
            return True                                           # finished before a restart
        ts, cfg = self.sets[set_key]
        cmd = [sys.executable, "scripts/rl/compare_policies.py", "--config", cfg, "--test-set", ts,
               "--workers", str(WORKERS), "--out", out]
        for n in names:
            cmd += ["--policy", self.spec(n)]
        return self.sh(step, cmd)

    # ── steps ───────────────────────────────────────────────────────────────
    def step_sets(self):
        """The L1 and L2 sets: stage1_large's box poses, written once (an existing file is checked, never rewritten)."""
        base = json.load(open(self.dry_base if self.dry else self._abs(BASE_SET)))
        for lv in ("L1", "L2"):
            path = self._abs(self.sets[lv][0])
            want = [{k: s[k] for k in ("id", "dx", "dy", "dyaw", "x", "y", "yaw")} for s in base["starts"]]
            if os.path.exists(path):
                if [{k: s[k] for k in ("id", "dx", "dy", "dyaw", "x", "y", "yaw")} for s in json.load(open(path))["starts"]] != want:
                    raise RuntimeError(f"{path} exists with different box poses; not overwriting it")
                continue
            d = {k: v for k, v in base.items() if k != "starts"}
            d.update(stage=f"stage1-{lv}", created=f"{dt.date.today()}", config=SETS[lv][1], base_set=BASE_SET,
                     note=(f"the same box poses as {BASE_SET} (same order, so start i uses the same seed, heldout_seeds[0] + i); "
                           f"only the duck start noise differs, from the env config `{SETS[lv][1]}`, drawn from that seed at "
                           "each reset. Never used in training."),
                     starts=base["starts"])
            json.dump(d, open(path, "w"), indent=1)
        return True

    def step_a_eval(self):
        ok = True
        for lv in ("L1", "L2"):
            ok &= self.compare("a_eval", lv, f"a_{lv}", list(A))
        return ok

    def step_train(self, run):
        k, seed = RUNS[run]
        warm = A[f"a_s{seed}"]                                    # the MATCHING night 2 A seed
        ok = self.sh(run, [sys.executable, "scripts/rl/stage.py", "--config", self.cfgs[k], "--seed", str(seed),
                           "--warm-start", warm])
        out = self.out_dir(run)
        ok = ok and os.path.exists(os.path.join(out, "model.zip"))
        if ok:                                                    # keep the final policy, eval files and final video
            for f in glob.glob(os.path.join(out, "checkpoints", "*.zip")):
                os.remove(f)
            for f in glob.glob(os.path.join(out, "videos", "*.mp4")):
                if "final" not in os.path.basename(f):
                    os.remove(f)
        return ok

    def step_eval(self):
        trained = [n for n in RUNS if os.path.exists(self.model(n))]
        if not trained:
            return False
        ok = True
        for k in ("clean", "noisy"):
            ok &= self.compare("eval", k, f"eval_{k}", list(A) + trained)
        for k in ("L1", "L2"):                                    # A on these comes from a_eval
            ok &= self.compare("eval", k, f"eval_{k}", trained)
        return ok

    def step_gifs(self):
        ep = self.episodes("L2")
        ts, cfg = self.sets["L2"]
        base = os.path.join(self.res, "gifs")
        os.makedirs(base, exist_ok=True)
        ok, info = True, {}
        for run in RUNS:
            if run not in ep:
                continue
            a = f"a_s{RUNS[run][1]}"
            rows, arows = ep[run], ep.get(a)
            win = [i for i, r in enumerate(rows) if won(r)]
            lose = [i for i, r in enumerate(rows) if not won(r)]
            if arows:                                             # prefer starts where the run and A disagree
                win = sorted(win, key=lambda i: won(arows[i]))
                lose = sorted(lose, key=lambda i: not won(arows[i]))
            for kind, idx in (("success", win[:2]), ("failure", lose[:2])):
                for i in idx:
                    sid = rows[i]["id"]
                    name = f"{run}_{kind}_start{sid}"
                    ok &= self.sh("gifs", [sys.executable, "scripts/rl/side_by_side_policies.py", "--config", cfg, "--test-set", ts,
                                           "--start", str(sid), "--left", self.label_spec(a), "--right", self.label_spec(run),
                                           "--out", os.path.join(base, name)])
                    info[name] = {"start": sid, "run": run, "kind": kind, "run_reason": rows[i]["reason"],
                                  "a_reason": arows[i]["reason"] if arows else None}
        json.dump(info, open(os.path.join(base, "clips.json"), "w"), indent=1)
        return ok

    def label_spec(self, name):
        return f"{LABEL[name]}=" + self.spec(name).split("=", 1)[1]

    # ── results ─────────────────────────────────────────────────────────────
    def episodes(self, k):
        """Every policy's episodes on set k (a_eval and eval merged)."""
        out = {}
        for d in ([f"a_{k}"] if k in ("L1", "L2") else []) + [f"eval_{k}"]:
            p = os.path.join(self.res, d, "comparison.json")
            if os.path.exists(p):
                out.update(json.load(open(p))["episodes"])
        return out

    # ── the night ───────────────────────────────────────────────────────────
    def run(self):
        free = shutil.disk_usage(ROOT).free / 1e9
        self.log(f"start ({'dry run' if self.dry else 'night 5'}); no new step after {self.deadline:%Y-%m-%d %H:%M}; free disk {free:.0f} GB")
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
            fn = {"sets": self.step_sets, "a_eval": self.step_a_eval, "eval": self.step_eval,
                  "gifs": self.step_gifs}.get(step) or (lambda s=step: self.step_train(s))
            try:
                ok = fn()
            except Exception as e:                                # a bug in a step must not end the night
                ok = False
                with open(os.path.join(self.dir, "crash.log"), "a") as f:
                    f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} step {step} raised {e!r}\n")
            if ok:
                self.mark(step, t0)
                self.log(f"end {step} ok")
            else:
                self.log(f"end {step} FAILED (see crash.log)")
        self.write_summary()                                      # once, at the end
        self.log("ALL DONE" if all(self.done(s) for s in STEPS) else "stopped; finished: " + ", ".join(s for s in STEPS if self.done(s)))

    def write_summary(self):
        try:
            text = Summary(self).text()
        except Exception as e:
            with open(os.path.join(self.dir, "crash.log"), "a") as f:
                f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} summary raised {e!r}\n")
            return
        os.makedirs(os.path.dirname(self.summary), exist_ok=True)
        open(self.summary, "w").write(text)
        self.log(f"wrote {self.summary}")


class Summary:
    def __init__(self, night: Night):
        self.n = night
        self.ep = {k: night.episodes(k) for k in SETS}

    def verdict(self, ep, X, Y, idx):
        """X, Y: lists of policy names (seeds). Per-start difference of the seed means, a 95% interval, the seed rates.
        Measurable only if the interval excludes 0 AND the seed rates of X and Y do not overlap."""
        d = [sum(won(ep[x][i]) for x in X) / len(X) - sum(won(ep[y][i]) for y in Y) / len(Y) for i in idx]
        m, h = mean_ci(d) if len(d) > 1 else (0.0, float("inf"))
        rx = [sum(won(ep[x][i]) for i in idx) / len(idx) for x in X]
        ry = [sum(won(ep[y][i]) for i in idx) / len(idx) for y in Y]
        ci_ok = m - h > 0 or m + h < 0
        sep = min(rx) > max(ry) or max(rx) < min(ry)
        if ci_ok and sep:
            v = "up" if m > 0 else "down"
        else:
            why = [w for w, bad in (("the 95% interval", not ci_ok), ("the seed spread", not sep)) if bad]
            v = "no measurable difference (inside " + " and ".join(why) + ")"
        return m, h, rx, ry, v

    def grp(self, ep, g):
        return [x for x in GROUPS[g] if x in ep]

    def idx(self, ep, where):
        rows = next(iter(ep.values()))
        return list(range(len(rows))) if where == "overall" else [i for i, r in enumerate(rows) if r["side"] == LONG]

    def cmp(self, k, X, Y, where):
        ep = self.ep[k]
        X, Y = [x for x in X if x in ep], [y for y in Y if y in ep]
        if not X or not Y:
            return None
        return self.verdict(ep, X, Y, self.idx(ep, where))

    def fmt(self, r):
        if r is None:
            return "not available"
        m, h, rx, ry, v = r
        return (f"{100 * m:+.1f} points ({100 * (m - h):+.1f} to {100 * (m + h):+.1f}; seed rates {', '.join(pct(x) for x in rx)} vs "
                f"{', '.join(pct(y) for y in ry)}): **{v}**")

    def text(self):
        n = self.n
        L = ["# D2 steering, night 5: training on wider duck start noise (L1, L2)", "",
             f"*Written {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/rl/overnight_steering_5.py`"
             + (" (DRY RUN, tiny settings: the numbers mean nothing)" if n.dry else "") + ".*", ""]
        L += ["## Steps", "", "| step | status | finished |", "|---|---|---|"]
        for s in STEPS:
            p = os.path.join(n.dir, "steps", s + ".done")
            L.append(f"| {s} | {'done' if os.path.exists(p) else 'not done'} | {json.load(open(p))['end'] if os.path.exists(p) else ''} |")
        L += self.setup()
        L += self.verdicts()
        for k in SETS:
            L += self.per_set(k)
        L += self.clips()
        return "\n".join(L) + "\n"

    def setup(self):
        n = self.n
        from stable_baselines3 import PPO
        ent = {}
        for a, p in A.items():
            try:
                ent[a] = PPO.load(n._abs(p), device="cpu").ent_coef
            except Exception:
                ent[a] = "?"
        lv = {}
        for k in ("L1", "L2"):
            sn = yaml.safe_load(open(n._abs(SETS[k][1])))["overrides"]["start_noise"]
            lv[k] = (f"heading {sn['duck_heading_std_deg']:g} deg (+-{sn['duck_heading_limit_deg']:g}), spacing "
                     f"{100 * sn['duck_spacing_std_m']:g} cm (+-{100 * sn['duck_spacing_limit_m']:g}), setback "
                     f"{100 * sn['duck_setback_std_m']:g} cm (+{100 * sn['duck_setback_back_limit_m']:g} back / "
                     f"-{100 * sn['duck_setback_forward_limit_m']:g} forward)")
        L = ["", "## Setup", "",
             "- **The one change:** duck start noise in training, at level L1 or L2 (std, with a hard limit per term; Gaussian, "
             "drawn from each episode's seed, redrawn if a start fails the start check). Everything else is night 2's Run A: "
             "reward v1.1, the standard policy head, the warm start's hyperparameters, stand-still threshold 0.02 m/s, stage 1 box "
             "starts, a fixed 2,000,000 duck steps, no early stopping.",
             f"- **L1:** {lv['L1']}",
             f"- **L2:** {lv['L2']}",
             "- **For scale, the noisy set (and night 2's B):** heading 5 deg, spacing 2 cm, setback 1 cm, clipped at 3 std.",
             "- **Warm starts:** each seed from the MATCHING night 2 A seed: "
             + "; ".join(f"seed {a[-1]}: `{p}` (sha256 `{sha(n._abs(p))[:16]}...`, ent_coef {ent[a]})" for a, p in A.items()),
             "- **Sets (200 starts each, deterministic, 100-step limit):** clean = `stage1_large.json`; noisy = "
             "`stage1_noisy_large.json` (its own 200 box poses); L1 and L2 = `stage1_L1_large.json` / `stage1_L2_large.json`, the "
             "SAME box poses and per-start seeds (10000 + i) as clean, so clean, L1 and L2 differences are paired per start.",
             "- **Rule for \"measurable\":** a difference counts only if its 95% interval (paired, same starts, seeds averaged) "
             "excludes 0 **and** the seed rates of the two groups do not overlap; otherwise \"no measurable difference\".",
             "", "**Reset-only check made while building** (scripts/rl/start_noise_check.py, 500 resets each, no policy):", ""]
        L += RESET_CHECK + ["", RESET_NOTE]
        L += ["", "| run | warm start | seed (results.json) | trained | stopped early | wall time |", "|---|---|---|---|---|---|"]
        for run in RUNS:
            rj = os.path.join(n.out_dir(run), "results.json")
            d = os.path.join(n.dir, "steps", run + ".done")
            if os.path.exists(rj):
                r = json.load(open(rj))
                wall = ""
                if os.path.exists(d):
                    t = json.load(open(d))
                    wall = f"{(dt.datetime.fromisoformat(t['end']) - dt.datetime.fromisoformat(t['start'])).total_seconds() / 60:.0f} min"
                L.append(f"| {run} | `{r.get('warm_start')}` | {r.get('seed')} | {r.get('steps')} of {r.get('steps_planned')} duck steps | "
                         f"{'YES' if r.get('early_stopped') else 'no'} | {wall} |")
            else:
                L.append(f"| {run} | | | not finished | | |")
        return L

    def verdicts(self):
        L = ["", "## Verdict (fixed rules)", ""]
        # (1) how much A drops on L1 and L2 (paired with clean: same box poses and seeds)
        L += ["**(1) How much does A drop on L1 and L2?** (A seeds averaged, each wide set minus clean, paired per start)", ""]
        clean = self.ep["clean"]
        for lv in ("L1", "L2"):
            w = self.ep[lv]
            Aw, Ac = [x for x in GROUPS["A"] if x in w], [x for x in GROUPS["A"] if x in clean]
            if not Aw or not Ac or len(w[Aw[0]]) != len(clean[Ac[0]]):
                L.append(f"- {lv}: not available")
                continue
            for where in ("overall", "long-turn"):
                idx = self.idx(w, where)
                d = [sum(won(w[x][i]) for x in Aw) / len(Aw) - sum(won(clean[x][i]) for x in Ac) / len(Ac) for i in idx]
                m, h = mean_ci(d) if len(d) > 1 else (0.0, float("inf"))
                rw = [sum(won(w[x][i]) for i in idx) / len(idx) for x in Aw]
                rc = [sum(won(clean[x][i]) for i in idx) / len(idx) for x in Ac]
                v = "measurable drop" if m + h < 0 and max(rw) < min(rc) else (
                    "measurable rise" if m - h > 0 and min(rw) > max(rc) else "no measurable difference")
                L.append(f"- A on {lv}, {where} (n={len(idx)}): {', '.join(pct(x) for x in rw)} vs clean {', '.join(pct(x) for x in rc)}: "
                         f"{100 * m:+.1f} points ({100 * (m - h):+.1f} to {100 * (m + h):+.1f}): **{v}**")
        # (2) do L1 / L2 training beat A on the wide sets?
        L += ["", "**(2) Do L1 / L2 training beat A on the wide sets?** (seeds averaged, paired against A on the same set)", ""]
        for g in ("L1", "L2"):
            for k in ("L1", "L2"):
                for where in ("overall", "long-turn"):
                    L.append(f"- {g} training vs A, on the {k} set, {where}: {self.fmt(self.cmp(k, GROUPS[g], GROUPS['A'], where))}")
        # (3) losses on clean and noisy
        L += ["", "**(3) Do they lose anything on clean and noisy?**", ""]
        for g in ("L1", "L2"):
            for k in ("clean", "noisy"):
                for where in ("overall", "long-turn"):
                    L.append(f"- {g} training vs A, on the {k} set, {where}: {self.fmt(self.cmp(k, GROUPS[g], GROUPS['A'], where))}")
        # (4) direct jump to L2, or step L1 then L2?
        L += ["", "**(4) Did a direct jump to L2 work, or should night 6 step L1 then L2?**", ""]
        l2_on_l2 = self.cmp("L2", GROUPS["L2"], GROUPS["A"], "overall")
        l1_on_l1 = self.cmp("L1", GROUPS["L1"], GROUPS["A"], "overall")
        l2_clean = self.cmp("clean", GROUPS["L2"], GROUPS["A"], "overall")
        if l2_on_l2 is None or l2_clean is None:
            L.append("- Not available.")
        else:
            up = l2_on_l2[4] == "up"
            no_loss = l2_clean[4] != "down"
            l1_up = l1_on_l1 is not None and l1_on_l1[4] == "up"
            if up and no_loss:
                ans = "**The direct jump worked**: L2 training is measurably better than A on the L2 set and not measurably worse on clean."
            elif l1_up and not up:
                ans = ("**Step L1 then L2**: L1 training beat A on the L1 set, but L2 training did not beat A on the L2 set. Night 6 "
                       "should warm-start L2 from the L1 policies.")
            elif up and not no_loss:
                ans = ("**Partly**: L2 training beats A on the L2 set but is measurably worse on clean. Night 6 should step L1 then L2, "
                       "or mix clean starts back in.")
            else:
                ans = "**Neither level helped measurably**: no measurable gain from L1 or L2 training on the wide sets."
            L.append(f"- {ans} Rule: worked = L2 vs A on the L2 set is \"up\" AND L2 vs A on clean is not \"down\"; step = L1 is up on "
                     "L1 while L2 is not up on L2.")
        return L

    def per_set(self, k):
        ep = self.ep[k]
        L = ["", f"## {SETNAME[k]}", ""]
        names = [x for x in ORDER if x in ep]
        if not names:
            return L + ["Not evaluated."]
        N = len(ep[names[0]])
        L += [f"**Success ({N} starts, 95% intervals)**", "", "| policy | overall | " + " | ".join(f"{s} deg" for s in SIDES) + " |",
              "|---|---|---|---|---|"]
        for nm in names:
            cells = [rate_str(sum(won(r) for r in ep[nm] if r["side"] == s), sum(r["side"] == s for r in ep[nm])) for s in SIDES]
            L.append(f"| {LABEL[nm]} | {rate_str(int(sum(map(won, ep[nm]))), N)} | " + " | ".join(cells) + " |")
        L += ["", "**Seed spread** (spread = the gap between seed 1 and seed 2)", "",
              "| group | overall, seed 1 / seed 2 | spread | long-turn side, seed 1 / seed 2 | spread |", "|---|---|---|---|---|"]
        for g in GROUPS:
            m = self.grp(ep, g)
            if not m:
                continue
            o = [sum(won(ep[x][i]) for i in self.idx(ep, "overall")) / N for x in m]
            li = self.idx(ep, "long-turn")
            lg = [sum(won(ep[x][i]) for i in li) / len(li) for x in m]
            L.append(f"| {g} | {' / '.join(pct(x) for x in o)} | {100 * (max(o) - min(o)):.1f} pts | {' / '.join(pct(x) for x in lg)} | "
                     f"{100 * (max(lg) - min(lg)):.1f} pts |")
        L += ["", "**Paired differences against A** (seeds averaged)", "",
              "| comparison | where | difference | 95% interval | seed rates | verdict |", "|---|---|---|---|---|---|"]
        for g in ("L1", "L2"):
            for where in ("overall", "long-turn"):
                r = self.cmp(k, GROUPS[g], GROUPS["A"], where)
                if r is None:
                    continue
                m, h, rx, ry, v = r
                L.append(f"| {g} minus A | {where} (n={len(self.idx(ep, where))}) | {100 * m:+.1f} | {100 * (m - h):+.1f} to {100 * (m + h):+.1f} | "
                         f"{', '.join(pct(x) for x in rx)}; {', '.join(pct(y) for y in ry)} | {v} |")
        L += ["", "**Stalls and failures** (both idle: both ducks held on 30% or more of an episode's steps)", "",
              "| policy | time-outs | both idle | falls (rate) | box lost | overshoots | long-turn starts with a pivot |",
              "|---|---|---|---|---|---|---|"]
        for nm in names:
            rows = ep[nm]
            lt = [r for r in rows if r["side"] == LONG]
            f = sum(r["fell"] for r in rows)
            L.append(f"| {LABEL[nm]} | {sum(r['reason'] == 'timeout' for r in rows)} | {sum(both_idle(r) for r in rows)} | "
                     f"{f} ({pct(f / N)}) | {sum(r['box_lost'] for r in rows)} | {sum(bool(r['overshoot']) for r in rows)} | "
                     f"{sum(r['max_pivot_run'] >= PIVOT_RUN for r in lt)}/{len(lt)} |")
        return L

    def clips(self):
        g = os.path.join(self.n.res, "gifs")
        info = json.load(open(os.path.join(g, "clips.json"))) if os.path.exists(os.path.join(g, "clips.json")) else {}
        if not info:
            return ["", "## Clips (L2 set)", "", "Not made."]
        base = os.path.dirname(self.n.summary)
        L = ["", "## Clips (L2 set)", "", "Left: the matching A seed (night 2); right: the run named. Same start, same noise. "
             "Successes and failures are the run's; starts where the run and A disagree are picked first."]
        for name, c in info.items():
            gif = sorted(glob.glob(os.path.join(g, name, "*.gif")))
            line = f"**{LABEL[c['run']]}, {c['kind']}, start {c['start']}** (run: {c['run_reason']}; A: {c['a_reason']})"
            L += ["", line] + (["", f"![{name}]({os.path.relpath(gif[0], base)})"] if gif else ["", "(clip missing)"])
        return L


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="tiny settings into runs/d2-steering-night5-dry/")
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
