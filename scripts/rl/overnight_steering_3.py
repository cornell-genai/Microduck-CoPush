#!/usr/bin/env python3
"""D2 steering, night 3: the both-held penalty (reward v1.4), two seeds, a fixed budget.

    scripts/rl.sh scripts/rl/overnight_steering_3.py              # the night (wrap it in caffeinate)
    scripts/rl.sh scripts/rl/overnight_steering_3.py --dry-run    # tiny end-to-end test in runs/d2-steering-night3-dry/

Steps, in this order (each is a subprocess with its own log):
  c_s1   train Run C (stand-still + reward v1.4: -0.05 per step while both ducks hold and the episode is not in a success
         state), seed 1, a fixed 2,000,000 duck steps (no early stopping)
  c_s2   Run C, seed 2
  eval   the D2 reference, night 2's Run A (seeds 1, 2) and Run C (seeds 1, 2) on stage1_large and stage1_noisy_large, 200 starts
         each, 100-step limit; 8 workers per policy
  gifs   start 185 for A seed 1 against C seed 1, and one stall episode per C run
experiments/d2-steering/night3/SUMMARY.md is rewritten after every step, so a partial night still has results.

Restart-safe: a finished step leaves <run dir>/steps/<name>.done and is skipped; a training step resumes from its last
checkpoint (scripts/rl/stage.py); a failing step goes to <run dir>/crash.log. progress.log, crash.log, lock and STOP live in
<run dir> (runs/d2-steering-night3/); `touch <run dir>/STOP` stops after the current step. No new step starts after the
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

E = "experiments/d2-steering/night3"
SETS = {"large": ("experiments/test_sets/stage1_large.json", "experiments/stage1-random-box-pose/config.yaml"),
        "noisy": ("experiments/test_sets/stage1_noisy_large.json", "experiments/d2-steering/noisy-sets/config.yaml")}
REF = "runs/decentral-p2-d2/model.zip"              # the policies-v1 release's stage1-d2 policy
N2_A = {"a_s1": "runs/d2-steering/night2/a-s1/model.zip", "a_s2": "runs/d2-steering/night2/a-s2/model.zip"}   # night 2, Run A
RUNS = {"c_s1": ("c", 1), "c_s2": ("c", 2)}
STEPS = ("c_s1", "c_s2", "eval", "gifs")
SIDES = ("< -15", "-15 to +15", "> +15")
LONG = "> +15"
LABEL = {"reference": "D2 reference", "a_s1": "A seed 1 (night 2, stand-still)", "a_s2": "A seed 2 (night 2, stand-still)",
         "c_s1": "C seed 1 (v1.4)", "c_s2": "C seed 2 (v1.4)"}
ORDER = ("reference", "a_s1", "a_s2", "c_s1", "c_s2")
WORKERS = 8
PIVOT_RUN = 3
BOTH_IDLE = 0.3
LIMIT = 100


def pct(x):
    return f"{100 * x:.0f}%"


def rate_str(k, n):
    lo, hi = wilson(k, n)
    return f"{pct(k / n)} ({pct(lo)} to {pct(hi)})" if n else "n/a"


def both_idle(r):
    return r["both_hold_steps"] / max(1, r["steps"]) >= BOTH_IDLE


class Night:
    def __init__(self, dry: bool, deadline: str):
        self.dry = dry
        self.dir = os.path.join(ROOT, "runs", "d2-steering-night3" + ("-dry" if dry else ""))
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
        self.cfgs = {"c": f"{E}/run-c/config.yaml"}
        if dry:
            self._dry_inputs()

    # ── setup ───────────────────────────────────────────────────────────────
    def _abs(self, p):
        return p if os.path.isabs(p) else os.path.join(ROOT, p)

    def _dry_inputs(self):
        """Tiny copies: 9 starts per set (3 per side), 6-start check sets, runs of 6144 duck steps."""
        def subset(src, n_per_side, name):
            d = json.load(open(self._abs(src)))
            pick = []
            for lo, hi in ((-99, -15), (-15, 15), (15, 99)):
                pick += [s for s in d["starts"] if lo < s["dyaw"] <= hi][:n_per_side]
            d["starts"] = [dict(s, id=i) for i, s in enumerate(pick)]
            p = os.path.join(self.dir, "sets", name)
            json.dump(d, open(p, "w"), indent=1)
            return p
        self.sets = {"large": (subset(SETS["large"][0], 3, "large.json"), SETS["large"][1]),
                     "noisy": (subset(SETS["noisy"][0], 3, "noisy.json"), SETS["noisy"][1])}
        checks = {"c": subset("experiments/test_sets/stage1_checks.json", 2, "checks.json")}
        for k, c in list(self.cfgs.items()):
            cfg = yaml.safe_load(open(self._abs(c)))
            cfg.update(out=os.path.join(self.dir, "train", f"{k}-s1"), results=os.path.join(self.dir, "train", k + "_results"),
                       check_set=checks[k], steps=6144, checkpoint_every=2048, max_videos=2)
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
        return self._abs(REF if name == "reference" else N2_A[name])

    def spec(self, name):
        return f"{name}={self.model(name)}@partner" + ("" if name == "reference" else "@standstill")

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

    def compare(self, step, set_key, outname, names, max_steps=None):
        out = os.path.join(self.res, outname)
        cj = os.path.join(out, "comparison.json")
        if os.path.exists(cj) and set(json.load(open(cj))["episodes"]) == set(names):
            return True                                           # finished before a restart
        ts, cfg = self.sets[set_key]
        cmd = [sys.executable, "scripts/rl/compare_policies.py", "--config", cfg, "--test-set", ts,
               "--workers", str(WORKERS), "--out", out]
        if max_steps and max_steps != 100:
            cmd += ["--max-steps", str(max_steps)]
        for n in names:
            cmd += ["--policy", self.spec(n)]
        return self.sh(step, cmd)

    # ── steps ───────────────────────────────────────────────────────────────
    def step_train(self, run):
        k, seed = RUNS[run]
        ok = self.sh(run, [sys.executable, "scripts/rl/stage.py", "--config", self.cfgs[k], "--seed", str(seed)])
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
        names = [n for n in ORDER if os.path.exists(self.model(n))]
        if not any(n in RUNS for n in names):
            return False
        ok = True
        for k in self.sets:
            ok &= self.compare("eval", k, f"eval{LIMIT}_{k}", names, LIMIT)
        return ok

    def step_gifs(self):
        ep = self.episodes(f"eval{LIMIT}_large")
        if "reference" not in ep:
            return False
        ts, cfg = self.sets["large"]
        base = os.path.join(self.res, "gifs")
        ok, info = True, {}

        def clip(name, start, left, right):
            return self.sh("gifs", [sys.executable, "scripts/rl/side_by_side_policies.py", "--config", cfg, "--test-set", ts,
                                    "--start", str(start), "--left", self.label_spec(left), "--right", self.label_spec(right),
                                    "--out", os.path.join(base, name)])
        if "a_s1" in ep and "c_s1" in ep:
            start = 185 if not self.dry else ep["reference"][0]["id"]
            ok &= clip("a_s1_vs_c_s1", start, "a_s1", "c_s1")
            info["a_s1_vs_c_s1"] = start
        for run in RUNS:
            if run not in ep:
                continue
            stalls = [r for r in ep[run] if r["reason"] == "timeout"]
            both = sorted([r for r in stalls if both_idle(r)], key=lambda r: -r["both_hold_steps"] / max(1, r["steps"]))
            pick = (both or stalls or [None])[0]
            if pick is None:
                continue
            ok &= clip(f"stall_{run}", pick["id"], "reference", run)
            info[f"stall_{run}"] = pick["id"]
        os.makedirs(base, exist_ok=True)
        json.dump(info, open(os.path.join(base, "starts.json"), "w"))
        return ok

    def label_spec(self, name):
        return f"{LABEL[name]}=" + self.spec(name).split("=", 1)[1]

    # ── results ─────────────────────────────────────────────────────────────
    def episodes(self, dirname):
        p = os.path.join(self.res, dirname, "comparison.json")
        return json.load(open(p))["episodes"] if os.path.exists(p) else {}

    # ── the night ───────────────────────────────────────────────────────────
    def run(self):
        free = shutil.disk_usage(ROOT).free / 1e9
        self.log(f"start ({'dry run' if self.dry else 'night 3'}); no new step after {self.deadline:%Y-%m-%d %H:%M}; free disk {free:.0f} GB")
        if free < 10:
            self.log("WARNING: under 10 GB free")
        self.write_summary()
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
            fn = {"eval": self.step_eval, "gifs": self.step_gifs}.get(step) or (lambda s=step: self.step_train(s))
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
            self.write_summary()
        self.write_summary()
        self.log("ALL DONE" if all(self.done(s) for s in STEPS) else "stopped; finished: " + ", ".join(s for s in STEPS if self.done(s)))

    def write_summary(self):
        try:
            text = Summary(self).text()
        except Exception as e:                                    # keep the previous SUMMARY.md rather than lose it
            with open(os.path.join(self.dir, "crash.log"), "a") as f:
                f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} summary raised {e!r}\n")
            return
        os.makedirs(os.path.dirname(self.summary), exist_ok=True)
        open(self.summary, "w").write(text)


class Summary:
    """SUMMARY.md: Run C (v1.4) against night 2's Run A, the seed spread, stall metrics and the verdict by fixed rules."""

    def __init__(self, night: Night):
        self.n = night

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

    def text(self):
        n = self.n
        L = ["# D2 steering, night 3: the both-held penalty (reward v1.4)", "",
             f"*Written {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/rl/overnight_steering_3.py`"
             + (" (DRY RUN, tiny settings: the numbers mean nothing)" if n.dry else "") + ".*", ""]
        L += ["## Steps", "", "| step | status | finished |", "|---|---|---|"]
        for s in STEPS:
            p = os.path.join(n.dir, "steps", s + ".done")
            L.append(f"| {s} | {'done' if os.path.exists(p) else 'not done'} | {json.load(open(p))['end'] if os.path.exists(p) else ''} |")
        L += self.setup()
        for k in n.sets:
            L += self.headline(k)
        L += self.clips()
        return "\n".join(L) + "\n"

    def setup(self):
        n = self.n
        from copush.config import load_config
        ref = os.path.join(ROOT, REF)
        sha = hashlib.sha256(open(ref, "rb").read()).hexdigest() if os.path.exists(ref) else "missing"
        man = json.load(open(os.path.join(ROOT, "policies", "manifest.json")))
        want = [f["sha256"] for p in man["policies"] for f in p["files"] if f["dest"] == REF]
        L = ["", "## Setup", "",
             "- **The one change:** reward v1.4 = v1.1 plus -0.05 per env step while both ducks are held (both command a forward speed "
             "below the stand-still threshold) and the episode is not in a success state. Night 2's Run A (reward v1.1) is the comparison; "
             "everything else is identical. (The log calls it v1.4 because v1.2 and v1.3 already existed; see docs/REWARD_LOG.md.)",
             f"- **Warm start (both runs):** `{ref}`, sha256 `{sha}`"
             + (" (matches policies/manifest.json, policies-v1 stage1-d2)" if want and want[0] == sha else " (DOES NOT match the manifest)"),
             "- **Seeds:** C trained with seed 1 and seed 2 (stage.py `--seed`), like night 2's A",
             "- **Budget:** a fixed 2,000,000 duck steps per run, no early stopping; the 50-start check set is evaluated every checkpoint "
             "(200k duck steps) for the log only; checkpoints every 200k, only final policies kept; no start noise in training",
             f"- **Stand-still threshold:** {load_config()['env']['stand_still']['vx_threshold']} m/s (the default, as in night 2)",
             "- **Sets:** `stage1_large.json` (no noise) and `stage1_noisy_large.json` (start noise), 200 starts each, one deterministic "
             "episode per start, 100-step limit.",
             "- **Rule for \"measurable\":** a difference counts only if its 95% interval (paired, same starts, seeds averaged) excludes 0 "
             "**and** the seed rates of the two groups do not overlap; otherwise it is \"no measurable difference\"."]
        L += ["", "| run | seed (from results.json) | trained | stopped early | wall time |", "|---|---|---|---|---|"]
        for run, (k, seed) in RUNS.items():
            rj = os.path.join(n.out_dir(run), "results.json")
            d = os.path.join(n.dir, "steps", run + ".done")
            if os.path.exists(rj):
                r = json.load(open(rj))
                steps = r.get("steps") or r.get("total_steps") or "?"
                wall = ""
                if os.path.exists(d):
                    t = json.load(open(d))
                    wall = f"{(dt.datetime.fromisoformat(t['end']) - dt.datetime.fromisoformat(t['start'])).total_seconds() / 60:.0f} min"
                L.append(f"| {run} | {r.get('seed', seed)} | {steps} of {r.get('steps_planned', '?')} duck steps | "
                         f"{'YES' if r.get('early_stopped') else 'no'} | {wall} |")
            else:
                L.append(f"| {run} | {seed} | not finished | | |")
        return L

    def headline(self, k):
        n = self.n
        ep = n.episodes(f"eval{LIMIT}_{k}")
        title = "Stage 1 starts, no noise" if k == "large" else "Stage 1 starts with duck start noise"
        L = ["", f"## {title} ({LIMIT}-step limit)", ""]
        if not ep:
            return L + ["Not evaluated yet."]
        names = [x for x in ORDER if x in ep]
        N = len(ep[names[0]])
        L += [f"**Success ({N} starts, 95% intervals)**", "", "| policy | overall | " + " | ".join(f"{s} deg" for s in SIDES) + " |",
              "|---|---|---|---|---|"]
        for nm in names:
            cells = [rate_str(sum(r["reason"] == "success" for r in ep[nm] if r["side"] == s), sum(r["side"] == s for r in ep[nm])) for s in SIDES]
            L.append(f"| {LABEL[nm]} | {rate_str(int(sum(map(won, ep[nm]))), N)} | " + " | ".join(cells) + " |")
        long_idx = [i for i, r in enumerate(ep[names[0]]) if r["side"] == LONG]
        allidx = list(range(N))
        groups = {"A": [x for x in ("a_s1", "a_s2") if x in ep], "C": [x for x in ("c_s1", "c_s2") if x in ep]}
        L += ["", "**Seed spread** (success per seed; spread = the gap between seed 1 and seed 2)", "",
              "| group | overall, seed 1 / seed 2 | spread | long-turn side, seed 1 / seed 2 | spread |", "|---|---|---|---|---|"]
        for g, members in groups.items():
            if not members:
                continue
            o = [sum(won(ep[m][i]) for i in allidx) / N for m in members]
            lg = [sum(won(ep[m][i]) for i in long_idx) / len(long_idx) for m in members]
            L.append(f"| {g} ({'night 2, v1.1' if g == 'A' else 'night 3, v1.4'}) | {' / '.join(pct(x) for x in o)} | "
                     f"{100 * (max(o) - min(o)):.1f} pts | {' / '.join(pct(x) for x in lg)} | {100 * (max(lg) - min(lg)):.1f} pts |")
        comps = [("C (seeds averaged) minus A (night 2, seeds averaged)", "the hold-penalty effect", groups["C"], groups["A"]),
                 ("C (seeds averaged) minus the D2 reference", "penalty + stand-still together", groups["C"], ["reference"])]
        L += ["", "**Comparisons** (percentage points; seed rates in brackets)", "",
              "| comparison | what it measures | where | difference | 95% interval | seed rates (first group; second group) | verdict |",
              "|---|---|---|---|---|---|---|"]
        for text, what, X, Y in comps:
            if not X or not Y or not all(y in ep for y in Y):
                continue
            for where, idx in (("overall", allidx), ("long-turn side (> +15 deg)", long_idx)):
                m, h, rx, ry, v = self.verdict(ep, X, Y, idx)
                L.append(f"| {text} | {what} | {where} (n={len(idx)}) | {100 * m:+.1f} | {100 * (m - h):+.1f} to {100 * (m + h):+.1f} | "
                         f"{', '.join(pct(x) for x in rx)}; {', '.join(pct(y) for y in ry)} | {v} |")
        L += ["", "**Stall and behavior metrics** (all starts; both idle: both ducks held on 30% or more of an episode's steps; holding steps: "
                  "total steps a duck is held, over all episodes)", "",
              "| policy | time-outs | both idle | holding steps, duck A / duck B | falls | overshoots | idle share | long-turn starts with a pivot |",
              "|---|---|---|---|---|---|---|---|"]
        for nm in names:
            rows = ep[nm]
            idle, ih = mean_ci([r["idle_frac"] for r in rows]) if len(rows) > 1 else (rows[0]["idle_frac"], 0.0)
            ha = sum(r["hold_a_frac"] * r["steps"] for r in rows)
            hb = sum(r["hold_b_frac"] * r["steps"] for r in rows)
            lt = [r for r in rows if r["side"] == LONG]
            pv = sum(r["max_pivot_run"] >= PIVOT_RUN for r in lt)
            L.append(f"| {LABEL[nm]} | {sum(r['reason'] == 'timeout' for r in rows)} | {sum(both_idle(r) for r in rows)} | {ha:.0f} / {hb:.0f} | "
                     f"{sum(r['fell'] for r in rows)} | {sum(bool(r['overshoot']) for r in rows)} | {pct(idle)} (+-{100 * ih:.0f}) | {pv}/{len(lt)} |")
        L += self.verdict_text(ep, groups, long_idx, k)
        return L

    def verdict_text(self, ep, groups, long_idx, k):
        """Fixed rules. Both idle drops meaningfully: BOTH C seeds have fewer both-idle episodes than BOTH A seeds, and the C average
        is at most half the A average. Pivot survives: the C average of long-turn starts with a pivot is at least 80% of the A average."""
        A, C = groups["A"], groups["C"]
        if not A or not C:
            return []
        bi = {m: sum(both_idle(r) for r in ep[m]) for m in A + C}
        a_avg, c_avg = sum(bi[m] for m in A) / len(A), sum(bi[m] for m in C) / len(C)
        drop = max(bi[m] for m in C) < min(bi[m] for m in A) and c_avg <= 0.5 * a_avg
        pv = {m: sum(r["max_pivot_run"] >= PIVOT_RUN for r in ep[m] if r["side"] == LONG) for m in A + C}
        pa, pc = sum(pv[m] for m in A) / len(A), sum(pv[m] for m in C) / len(C)
        surv = pc >= 0.8 * pa
        setname = "no-noise set" if k == "large" else "noisy set"
        return ["", f"**Verdict, {setname} (fixed rules)**", "",
                f"- *Does \"both idle\" drop meaningfully?* **{'YES' if drop else 'NO'}.** Both-idle episodes per seed: A "
                f"{' / '.join(str(bi[m]) for m in A)}, C {' / '.join(str(bi[m]) for m in C)} (averages {a_avg:.1f} and {c_avg:.1f}). "
                "Rule: both C seeds below both A seeds and the C average at most half the A average.",
                f"- *Does the pivot behavior survive?* **{'YES' if surv else 'NO'}.** Long-turn starts with a pivot per seed: A "
                f"{' / '.join(str(pv[m]) for m in A)}, C {' / '.join(str(pv[m]) for m in C)} (averages {pa:.1f} and {pc:.1f} of {len(long_idx)}). "
                "Rule: the C average is at least 80% of the A average."]

    def clips(self):
        g = os.path.join(self.n.res, "gifs")
        found = sorted(glob.glob(os.path.join(g, "*", "*.gif")))
        if not found:
            return ["", "## Clips", "", "Not made yet."]
        starts = json.load(open(os.path.join(g, "starts.json"))) if os.path.exists(os.path.join(g, "starts.json")) else {}
        base = os.path.dirname(self.n.summary)
        L = ["", "## Clips", "", "Left: A seed 1 (or the D2 reference), right: the run named. Stall clips are the run's time-out with the "
             "largest share of steps with both ducks held, on the no-noise set."]
        for f in found:
            name = os.path.basename(os.path.dirname(f))
            L += ["", f"**{name.replace('_', ' ')}** (start {starts.get(name)}):", "", f"![{name}]({os.path.relpath(f, base)})"]
        return L


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="tiny settings into runs/d2-steering-night3-dry/")
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
