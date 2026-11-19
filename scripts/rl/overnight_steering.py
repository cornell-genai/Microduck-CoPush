#!/usr/bin/env python3
"""The unattended D2 steering night: zero-shot, Run A, Run B, evaluation, pivot metrics, GIFs, SUMMARY.md.

    scripts/rl.sh scripts/rl/overnight_steering.py              # the night (wrap it in caffeinate)
    scripts/rl.sh scripts/rl/overnight_steering.py --dry-run    # tiny end-to-end test in runs/d2-steering-overnight-dry/

Steps, in order (each runs as a subprocess with its own log in <run dir>/logs/):
  1 zero_shot   the D2 stage 1 policy (reference) on stage1_large and stage1_noisy_large, and the start-noise
                resample rate on the noisy set
  2 run_a       train Run A, D2 + the stand-still action (experiments/d2-steering/run-a/config.yaml)
  3 run_b       train Run B, Run A + duck start noise (experiments/d2-steering/run-b/config.yaml)
  4 eval        Run A and Run B on both 200-start sets, 8 worker processes per policy
  5 gifs        labeled side by side, reference vs A and A vs B, on the same long-turn start
experiments/d2-steering/SUMMARY.md is rewritten after every step, so a partial night still has results.

Restart-safe: a finished step leaves <run dir>/steps/<name>.done and is skipped; a training step resumes from its last
checkpoint (scripts/rl/stage.py); a failing step goes to <run dir>/crash.log and the steps that need it are skipped.
After a run finishes only its final policy, eval files and final video are kept. No new step starts after the deadline
(the first 09:00 after launch, or --deadline HH:MM); `touch <run dir>/STOP` stops after the current step.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ci_report import mcnemar_p, mean_ci, wilson, won  # noqa: E402

E = "experiments/d2-steering"
SETS = {"large": ("experiments/test_sets/stage1_large.json", "experiments/stage1-random-box-pose/config.yaml"),
        "noisy": ("experiments/test_sets/stage1_noisy_large.json", f"{E}/noisy-sets/config.yaml")}
REF = "runs/decentral-p2-d2/model.zip"                 # the policies-v1 release's stage1-d2 policy
SIDES = ("< -15", "-15 to +15", "> +15")
PIVOT_RUN = 3
WORKERS = 8
STEPS = ("zero_shot", "run_a", "run_b", "eval", "gifs")


class Night:
    def __init__(self, dry: bool, deadline: str):
        self.dry = dry
        self.dir = os.path.join(ROOT, "runs", "d2-steering-overnight" + ("-dry" if dry else ""))
        self.res = os.path.join(self.dir, "results") if dry else os.path.join(ROOT, E, "results")
        self.summary = os.path.join(self.dir if dry else os.path.join(ROOT, E), "SUMMARY.md")
        for d in ("logs", "steps", "configs", "sets"):
            os.makedirs(os.path.join(self.dir, d), exist_ok=True)
        now = dt.datetime.now()
        hh, mm = map(int, deadline.split(":"))
        self.deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if self.deadline <= now:
            self.deadline += dt.timedelta(days=1)
        self.sets = {k: v for k, v in SETS.items()}
        self.runs = {"run_a": f"{E}/run-a/config.yaml", "run_b": f"{E}/run-b/config.yaml"}
        if dry:
            self._dry_inputs()
        self.outs = {k: yaml.safe_load(open(self._abs(c)))["out"] for k, c in self.runs.items()}

    # ── setup ───────────────────────────────────────────────────────────────
    def _abs(self, p):
        return p if os.path.isabs(p) else os.path.join(ROOT, p)

    def _dry_inputs(self):
        """Tiny copies: 9 starts per set (3 per side), 4-start check sets, runs of 6144 duck steps."""
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
        checks = {"run_a": subset("experiments/test_sets/stage1_checks.json", 2, "checks.json"),
                  "run_b": subset("experiments/test_sets/stage1_noisy_checks.json", 2, "noisy_checks.json")}
        runs = {}
        for k, c in self.runs.items():
            cfg = yaml.safe_load(open(self._abs(c)))
            cfg.update(out=os.path.join(self.dir, "train", k), results=os.path.join(self.dir, "train", k + "_results"),
                       check_set=checks[k], steps=6144, checkpoint_every=2048, max_videos=2)
            cfg["overrides"]["rl"] = {"eval_every": 2048}
            cfg["widen"].update(eval_every=2048, episodes=4)
            p = os.path.join(self.dir, "configs", k + ".yaml")
            yaml.safe_dump(cfg, open(p, "w"), sort_keys=False)
            runs[k] = p
        self.runs = runs

    # ── bookkeeping ─────────────────────────────────────────────────────────
    def log(self, msg):
        line = f"{dt.datetime.now():%H:%M:%S} {msg}"
        print(line, flush=True)
        with open(os.path.join(self.dir, "progress.log"), "a") as f:
            f.write(line + "\n")

    def done(self, step):
        return os.path.exists(os.path.join(self.dir, "steps", step + ".done"))

    def mark(self, step, t0):
        with open(os.path.join(self.dir, "steps", step + ".done"), "w") as f:
            json.dump({"start": t0, "end": f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"}, f)

    def sh(self, step, cmd):
        """Run one command of a step, appending to its log; True when it succeeds."""
        with open(os.path.join(self.dir, "logs", step + ".log"), "a") as f:
            f.write(f"\n$ {' '.join(cmd)}\n")
            f.flush()
            rc = subprocess.call(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        if rc != 0:
            tail = open(os.path.join(self.dir, "logs", step + ".log")).read().splitlines()[-30:]
            with open(os.path.join(self.dir, "crash.log"), "a") as f:
                f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} step {step} exit {rc}: {' '.join(cmd)}\n" + "\n".join(tail) + "\n\n")
        return rc == 0

    def compare(self, step, set_key, out, policies):
        ts, cfg = self.sets[set_key]
        cmd = [sys.executable, "scripts/rl/compare_policies.py", "--config", cfg, "--test-set", ts,
               "--workers", str(WORKERS), "--out", out]
        for p in policies:
            cmd += ["--policy", p]
        return self.sh(step, cmd)

    # ── steps ───────────────────────────────────────────────────────────────
    def step_zero_shot(self):
        ok = all(self.compare("zero_shot", k, os.path.join(self.res, f"zero_shot_{k}"), [f"reference={REF}@partner"])
                 for k in self.sets)
        return ok and self.resample_rate()

    def resample_rate(self):
        from copush.env import CoPushEnv
        from copush.experiments import load_stage, load_test_set
        ts, cfg_path = self.sets["noisy"]
        _, cfg = load_stage(cfg_path)
        env = CoPushEnv(cfg, split="eval")
        seed0 = cfg["env"]["heldout_seeds"][0]
        for i, s in enumerate(load_test_set(ts)["starts"]):
            env.reset(seed=seed0 + i, options={"box": s})
        r = {"starts": env.start_draws - env.start_resamples, "draws": env.start_draws, "resamples": env.start_resamples}
        json.dump(r, open(os.path.join(self.res, "start_noise_resamples.json"), "w"))
        return True

    def step_train(self, step):
        cfg = self.runs[step]
        ok = self.sh(step, [sys.executable, "scripts/rl/stage.py", "--config", cfg])
        out = self._abs(self.outs[step]) if not self.dry else yaml.safe_load(open(cfg))["out"]
        ok = ok and os.path.exists(os.path.join(out, "model.zip"))
        if ok:                                                    # keep the final policy, eval files and final video
            for f in glob.glob(os.path.join(out, "checkpoints", "*.zip")):
                os.remove(f)
            for f in glob.glob(os.path.join(out, "videos", "*.mp4")):
                if "final" not in os.path.basename(f):
                    os.remove(f)
        return ok

    def model(self, step):
        out = yaml.safe_load(open(self._abs(self.runs[step])))["out"]
        return os.path.join(self._abs(out), "model.zip")

    def step_eval(self):
        pols = [f"{n}={self.model(s)}@partner@standstill" for s, n in (("run_a", "run_a"), ("run_b", "run_b"))
                if os.path.exists(self.model(s))]
        return bool(pols) and all(self.compare("eval", k, os.path.join(self.res, f"eval_{k}"), pols) for k in self.sets)

    def step_gifs(self):
        ep = self.episodes("large")
        ref, a, b = ep.get("reference"), ep.get("run_a"), ep.get("run_b")
        if not (ref and a):
            return False
        long_ = [i for i, e in enumerate(ref) if e["side"] == "> +15"] or list(range(len(ref)))
        win = [i for i in long_ if a[i]["reason"] == "success" and ref[i]["reason"] != "success"]
        pick = sorted(win or long_, key=lambda i: -a[i]["max_pivot_run"])[0]
        ts, cfg = self.sets["large"]
        gif = os.path.join(self.res, "gifs")
        pairs = [("ref_vs_a", f"D2 reference=" + REF + "@partner", f"Run A, stand-still={self.model('run_a')}@partner@standstill")]
        if b:
            pairs.append(("a_vs_b", f"Run A, stand-still={self.model('run_a')}@partner@standstill",
                          f"Run B, + start noise={self.model('run_b')}@partner@standstill"))
        ok = True
        for name, left, right in pairs:
            ok &= self.sh("gifs", [sys.executable, "scripts/rl/side_by_side_policies.py", "--config", cfg, "--test-set", ts,
                                   "--start", str(ref[pick]["id"]), "--left", left, "--right", right,
                                   "--out", os.path.join(gif, name)])
        json.dump({"start": ref[pick]["id"], "side": ref[pick]["side"]}, open(os.path.join(gif, "start.json"), "w"))
        return ok

    # ── results ─────────────────────────────────────────────────────────────
    def episodes(self, set_key):
        out = {}
        for d in (f"zero_shot_{set_key}", f"eval_{set_key}"):
            p = os.path.join(self.res, d, "comparison.json")
            if os.path.exists(p):
                out.update(json.load(open(p))["episodes"])
        return out

    def write_summary(self):
        S = Summary(self)
        open(self.summary, "w").write(S.text())

    # ── the night ───────────────────────────────────────────────────────────
    def run(self):
        needs = {"eval": ("run_a", "run_b"), "gifs": ("zero_shot", "eval")}
        self.log(f"start ({'dry run' if self.dry else 'night'}); no new step after {self.deadline:%Y-%m-%d %H:%M}; "
                 f"free disk {shutil.disk_usage(ROOT).free / 1e9:.0f} GB")
        if shutil.disk_usage(ROOT).free < 10e9:
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
            if step in needs and step == "eval" and not any(self.done(s) for s in needs[step]):
                self.log(f"skip {step}: neither run finished")
                continue
            if step == "gifs" and not (self.done("zero_shot") and self.done("eval")):
                self.log(f"skip {step}: needs zero_shot and eval")
                continue
            t0 = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"
            self.log(f"start {step}")
            ok = {"zero_shot": self.step_zero_shot, "eval": self.step_eval, "gifs": self.step_gifs}.get(
                step, lambda: self.step_train(step))()
            if ok:
                self.mark(step, t0)
                self.log(f"end {step} ok")
            else:
                self.log(f"end {step} FAILED (see crash.log)")
            self.write_summary()
        self.write_summary()
        self.log("ALL DONE" if all(self.done(s) for s in STEPS) else "stopped; finished: " +
                 ", ".join(s for s in STEPS if self.done(s)))


class Summary:
    def __init__(self, night: Night):
        self.n = night

    @staticmethod
    def pct(x):
        return f"{100 * x:.0f}%"

    def rate(self, k, n):
        lo, hi = wilson(k, n)
        return f"{self.pct(k / n)} ({self.pct(lo)} to {self.pct(hi)})" if n else "n/a"

    def diff(self, a, b, idx):
        d = [won(a[i]) - won(b[i]) for i in idx]
        m, h = mean_ci(d) if len(d) > 1 else (0.0, float("inf"))
        p = mcnemar_p(sum(v > 0 for v in d), sum(v < 0 for v in d))
        excl = m - h > 0 or m + h < 0
        v = (("up" if m > 0 else "down") if (excl and p < 0.05) else
             "borderline (the interval and the exact test disagree)" if (excl or p < 0.05) else "no measurable difference")
        return m, h, p, v

    def text(self):
        n = self.n
        L = ["# D2 steering overnight: summary", "",
             f"*Written {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/rl/overnight_steering.py`"
             + (" (DRY RUN, tiny settings: the numbers mean nothing)" if n.dry else "") + ".*", ""]
        L += ["## Steps", "", "| step | status | finished |", "|---|---|---|"]
        for s in STEPS:
            p = os.path.join(n.dir, "steps", s + ".done")
            L.append(f"| {s} | {'done' if os.path.exists(p) else 'not done'} | {json.load(open(p))['end'] if os.path.exists(p) else ''} |")
        L += self.setup()
        for k in n.sets:
            L += self.set_section(k)
        L += self.gifs() + self.read()
        return "\n".join(L) + "\n"

    def setup(self):
        n = self.n
        from copush.config import load_config
        ref = os.path.join(ROOT, REF)
        sha = hashlib.sha256(open(ref, "rb").read()).hexdigest() if os.path.exists(ref) else "missing"
        man = json.load(open(os.path.join(ROOT, "policies", "manifest.json")))
        want = [f["sha256"] for p in man["policies"] for f in p["files"] if f["dest"] == REF]
        cfgs = {k: yaml.safe_load(open(n._abs(c))) for k, c in n.runs.items()}
        seeds = {k: (c.get("overrides", {}).get("ppo") or {}).get("seed") for k, c in cfgs.items()}
        rr = os.path.join(n.res, "start_noise_resamples.json")
        rr = json.load(open(rr)) if os.path.exists(rr) else None
        L = ["", "## Setup", "",
             f"- **Warm start (both runs):** `{REF}`, sha256 `{sha}`"
             + (" (matches policies/manifest.json, policies-v1 stage1-d2)" if want and want[0] == sha else " (DOES NOT match the manifest)"),
             f"- **Training seed:** Run A {seeds.get('run_a')}, Run B {seeds.get('run_b')} (ppo.seed)",
             f"- **Stand-still threshold:** {load_config()['env']['stand_still']['vx_threshold']} m/s (the default; a commanded "
             "forward speed below it holds that duck on velstand at zero speed)",
             "- **Start noise (Run B and the noisy set):** heading 5 deg per duck, spacing 0.02 m, setback 0.01 m per duck, "
             "Gaussian, clipped at 3x, drawn from each episode's seed",
             f"- **Start-noise resamples on the noisy set:** "
             + (f"{rr['resamples']} redraws for {rr['starts']} starts ({100 * rr['resamples'] / max(1, rr['draws']):.1f}% of draws)" if rr else "not measured yet"),
             f"- **Sets:** `{n.sets['large'][0] if n.dry else SETS['large'][0]}` (no noise) and "
             f"`{n.sets['noisy'][0] if n.dry else SETS['noisy'][0]}` (start noise), one episode per start, 95% intervals "
             "(Wilson for rates; paired normal interval and exact McNemar test for differences)."]
        return L

    def set_section(self, k):
        ep = self.n.episodes(k)
        L = ["", f"## {'Stage 1 starts, no noise' if k == 'large' else 'Stage 1 starts with duck start noise'} "
                 f"({os.path.basename(self.n.sets[k][0])})", ""]
        if not ep:
            return L + ["Not evaluated yet."]
        N = len(next(iter(ep.values())))
        L += [f"**Success ({N} starts)**", "", "| policy | overall | " + " | ".join(f"{s} deg" for s in SIDES) + " |",
              "|---|---|---|---|---|"]
        for name, rows in ep.items():
            cells = [self.rate(sum(r["reason"] == "success" for r in rows if r["side"] == s), sum(r["side"] == s for r in rows))
                     for s in SIDES]
            L.append(f"| {name} | {self.rate(sum(map(won, rows)), N)} | " + " | ".join(cells) + " |")
        pairs = [(a, b) for a, b in (("run_a", "reference"), ("run_b", "run_a")) if a in ep and b in ep]
        if pairs:
            L += ["", "**Differences (percentage points, same starts)**", "",
                  "| comparison | where | difference | 95% interval | McNemar p | verdict |", "|---|---|---|---|---|---|"]
            for a, b in pairs:
                for where, idx in (("overall", list(range(N))),
                                   ("long-turn side (> +15 deg)", [i for i, r in enumerate(ep[b]) if r["side"] == "> +15"])):
                    m, h, p, v = self.diff(ep[a], ep[b], idx)
                    L.append(f"| {a} minus {b} | {where} (n={len(idx)}) | {100 * m:+.1f} | {100 * (m - h):+.1f} to "
                             f"{100 * (m + h):+.1f} | {p:.3f} | {v} |")
        L += ["", "**Pivots on the long-turn starts** (a pivot: 3 or more steps with exactly one duck held while the other "
                  "works; rotation: the box's turn toward the needed direction during those steps)", "",
              "| policy | episodes with a pivot | won with / without a pivot | steps with one duck held (mean, pivot episodes) "
              "| box rotation during them (deg, mean) | A holds alone / B holds alone (steps) |", "|---|---|---|---|---|---|"]
        for name, rows in ep.items():
            lt = [r for r in rows if r["side"] == "> +15"]
            pv = [r for r in lt if r.get("max_pivot_run", 0) >= PIVOT_RUN]
            npv = [r for r in lt if r.get("max_pivot_run", 0) < PIVOT_RUN]
            L.append(f"| {name} | {self.rate(len(pv), len(lt)) if lt else 'n/a'} | "
                     f"{sum(won(r) for r in pv):.0f}/{len(pv)} / {sum(won(r) for r in npv):.0f}/{len(npv)} | "
                     + (f"{sum(r['one_hold_steps'] for r in pv) / len(pv):.1f} | {sum(r['rot_one_hold_deg'] for r in pv) / len(pv):+.1f}"
                        if pv else "n/a | n/a")
                     + f" | {sum(r.get('hold_a_alone', 0) for r in lt)} / {sum(r.get('hold_b_alone', 0) for r in lt)} |")
        L += ["", "**Behavior (all starts)** (permanent holder: a duck held on 80% or more of an episode's steps; both idle: "
                  "both held on 30% or more)", "",
              "| policy | idle share | overshoots | time-outs | falls | box lost | push share A | lazy duck | permanent holder (A / B) | both idle |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for name, rows in ep.items():
            idle, ih = mean_ci([r["idle_frac"] for r in rows]) if len(rows) > 1 else (rows[0]["idle_frac"], 0.0)
            L.append(f"| {name} | {self.pct(idle)} (+-{100 * ih:.0f}) | {sum(bool(r['overshoot']) for r in rows)} | "
                     f"{sum(r['reason'] == 'timeout' for r in rows)} | {sum(r['fell'] for r in rows)} | "
                     f"{sum(r['box_lost'] for r in rows)} | {self.pct(sum(r['push_share_a'] for r in rows) / N)} | "
                     f"{sum(r['lazy'] for r in rows)} | {sum(r.get('hold_a_frac', 0) >= 0.8 for r in rows)} / "
                     f"{sum(r.get('hold_b_frac', 0) >= 0.8 for r in rows)} | "
                     f"{sum(r.get('both_hold_steps', 0) / max(1, r['steps']) >= 0.3 for r in rows)} |")
        return L

    def gifs(self):
        g = os.path.join(self.n.res, "gifs")
        found = sorted(glob.glob(os.path.join(g, "*", "*.gif")))
        if not found:
            return ["", "## Clips", "", "Not made yet."]
        st = json.load(open(os.path.join(g, "start.json"))) if os.path.exists(os.path.join(g, "start.json")) else {}
        base = os.path.dirname(self.n.summary)
        L = ["", "## Clips", "", f"Start {st.get('start')} of the no-noise set ({st.get('side')} deg side), the same start in both."]
        for f in found:
            rel = os.path.relpath(f, base)
            L += ["", f"![{os.path.basename(os.path.dirname(f)).replace('_', ' ')}]({rel})"]
        return L

    def read(self):
        """Plain words by fixed rules: A vs reference = the stand-still action; B vs A = the start noise."""
        L = ["", "## Read (fixed rules)", "",
             "Run A minus the reference is the effect of the stand-still action; Run B minus Run A is the effect of the "
             "start noise. \"Up\" or \"down\" only when the 95% interval excludes 0 and the exact test agrees (p < 0.05); "
             "anything else is \"no measurable difference\"."]
        for k in self.n.sets:
            ep = self.n.episodes(k)
            if not ep:
                continue
            N = len(next(iter(ep.values())))
            setname = "no-noise set" if k == "large" else "noisy set"
            for a, b, what in (("run_a", "reference", "Stand-still (A vs reference)"), ("run_b", "run_a", "Start noise (B vs A)")):
                if a not in ep or b not in ep:
                    continue
                m, h, p, v = self.diff(ep[a], ep[b], list(range(N)))
                lt = [i for i, r in enumerate(ep[b]) if r["side"] == "> +15"]
                m2, h2, p2, v2 = self.diff(ep[a], ep[b], lt)
                L.append(f"- **{what}, {setname}:** overall {100 * m:+.1f} points ({100 * (m - h):+.1f} to {100 * (m + h):+.1f}): "
                         f"**{v}**; long-turn side {100 * m2:+.1f} ({100 * (m2 - h2):+.1f} to {100 * (m2 + h2):+.1f}): **{v2}**.")
            for name, rows in ep.items():
                lt = [r for r in rows if r["side"] == "> +15"]
                pv = sum(r.get("max_pivot_run", 0) >= PIVOT_RUN for r in lt)
                perm = sum(max(r.get("hold_a_frac", 0), r.get("hold_b_frac", 0)) >= 0.8 for r in rows)
                both = sum(r.get("both_hold_steps", 0) / max(1, r["steps"]) >= 0.3 for r in rows)
                flags = []
                if perm > 0.1 * N:
                    flags.append(f"a duck holds all the time in {perm} of {N} episodes")
                if both > 0.1 * N:
                    flags.append(f"both ducks idle in {both} of {N} episodes")
                L.append(f"- *{name}, {setname}:* pivots on {pv} of {len(lt)} long-turn starts"
                         + (f"; **possible reward hacking:** {'; '.join(flags)}" if flags else "; no sign of reward hacking") + ".")
        return L


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="tiny settings into runs/d2-steering-overnight-dry/")
    ap.add_argument("--deadline", default="09:00", help="no new step starts after this local time (HH:MM)")
    a = ap.parse_args()
    night = Night(a.dry_run, a.deadline)
    lock = os.path.join(night.dir, "lock")
    if os.path.exists(lock):
        pid = int(open(lock).read() or 0)
        try:
            os.kill(pid, 0)
            print(f"already running (pid {pid}); remove {lock} if it is not")
            return 1
        except OSError:
            pass
    open(lock, "w").write(str(os.getpid()))
    try:
        night.run()
    finally:
        os.remove(lock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
