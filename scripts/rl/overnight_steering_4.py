#!/usr/bin/env python3
"""D2 steering, night 4: bounded exploration (Run E), two seeds, a fixed budget, and the deterministic vs sampled gap.

    scripts/rl.sh scripts/rl/overnight_steering_4.py              # the night (wrap it in caffeinate)
    scripts/rl.sh scripts/rl/overnight_steering_4.py --dry-run    # tiny end-to-end test in runs/d2-steering-night4-dry/

Steps, in this order (each is a subprocess with its own log):
  stoch_eval  no training: night 2's A seed 1 and seed 2, deterministic and with SAMPLED actions (sampling seeds 1, 2, 3), on
              stage1_large and stage1_noisy_large (200 starts each): the train/eval gap of the current policies
  e_s1        train Run E (night 2's Run A + the bounded action head: mean identity on [-1, 1] and soft-bounded to +-1.5, std
              capped at 0.5 and set to 0.5, ent_coef 0), seed 1, a fixed 2,000,000 duck steps (no early stopping)
  e_s2        Run E, seed 2
  eval        the D2 reference, A seeds 1 and 2, E seeds 1 and 2, deterministic (the headline), plus E sampled (sampling seeds
              1, 2, 3), on both 200-start sets, 100-step limit; 8 workers per policy
  gifs        start 185, A seed 1 against E seed 1, plus one stall clip per E seed if any stalls remain
experiments/d2-steering/night4/SUMMARY.md is rewritten after every step, so a partial night still has results.

Restart-safe: a finished step leaves <run dir>/steps/<name>.done and is skipped; a training step resumes from its last
checkpoint (scripts/rl/stage.py); a failing step goes to <run dir>/crash.log. progress.log, crash.log, lock and STOP live in
<run dir> (runs/d2-steering-night4/); `touch <run dir>/STOP` stops after the current step. No new step starts after the
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

E = "experiments/d2-steering/night4"
SETS = {"large": ("experiments/test_sets/stage1_large.json", "experiments/stage1-random-box-pose/config.yaml"),
        "noisy": ("experiments/test_sets/stage1_noisy_large.json", "experiments/d2-steering/noisy-sets/config.yaml")}
REF = "runs/decentral-p2-d2/model.zip"              # the policies-v1 release's stage1-d2 policy
N2_A = {"a_s1": "runs/d2-steering/night2/a-s1/model.zip", "a_s2": "runs/d2-steering/night2/a-s2/model.zip"}   # night 2, Run A
RUNS = {"e_s1": ("e", 1), "e_s2": ("e", 2)}
STEPS = ("stoch_eval", "e_s1", "e_s2", "eval", "gifs")
SAMPLE_SEEDS = (1, 2, 3)
SIDES = ("< -15", "-15 to +15", "> +15")
LONG = "> +15"
LABEL = {"reference": "D2 reference", "a_s1": "A seed 1 (night 2)", "a_s2": "A seed 2 (night 2)",
         "e_s1": "E seed 1 (bounded)", "e_s2": "E seed 2 (bounded)"}
ORDER = ("reference", "a_s1", "a_s2", "e_s1", "e_s2")
WORKERS = 8
PIVOT_RUN = 3
BOTH_IDLE = 0.3
LIMIT = 100
CKPT = 200_000


def pct(x):
    return f"{100 * x:.0f}%"


def rate_str(k, n):
    lo, hi = wilson(k, n)
    return f"{pct(k / n)} ({pct(lo)} to {pct(hi)})" if n else "n/a"


def both_idle(r):
    return r["both_hold_steps"] / max(1, r["steps"]) >= BOTH_IDLE


def smp(name, k):
    return f"{name}_smp{k}"


def label(name):
    m = re.match(r"(.+)_smp(\d+)$", name)
    return f"{LABEL[m[1]]}, sampled (seed {m[2]})" if m else LABEL[name]


class Night:
    def __init__(self, dry: bool, deadline: str):
        self.dry = dry
        self.dir = os.path.join(ROOT, "runs", "d2-steering-night4" + ("-dry" if dry else ""))
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
        self.cfgs = {"e": f"{E}/run-e/config.yaml"}
        if dry:
            self._dry_inputs()

    # ── setup ───────────────────────────────────────────────────────────────
    def _abs(self, p):
        return p if os.path.isabs(p) else os.path.join(ROOT, p)

    def _dry_inputs(self):
        """Tiny copies: 9 starts per set (3 per side), a 6-start check set, runs of 6144 duck steps."""
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
        cfg = yaml.safe_load(open(self._abs(self.cfgs["e"])))
        cfg.update(out=os.path.join(self.dir, "train", "e-s1"), results=os.path.join(self.dir, "train", "e_results"),
                   check_set=subset("experiments/test_sets/stage1_checks.json", 2, "checks.json"),
                   steps=6144, checkpoint_every=2048, max_videos=2)
        cfg["overrides"]["rl"] = {"eval_every": 2048}
        cfg["widen"].update(eval_every=2048, episodes=4)
        p = os.path.join(self.dir, "configs", "e.yaml")
        yaml.safe_dump(cfg, open(p, "w"), sort_keys=False)
        self.cfgs["e"] = p

    def out_dir(self, run):
        k, seed = RUNS[run]
        out = yaml.safe_load(open(self._abs(self.cfgs[k])))["out"]
        return self._abs(re.sub(r"-s\d+$", "", out.rstrip("/")) + f"-s{seed}")      # as scripts/rl/stage.py names it

    def model(self, name):
        name = re.sub(r"_smp\d+$", "", name)
        if name in RUNS:
            return os.path.join(self.out_dir(name), "model.zip")
        return self._abs(REF if name == "reference" else N2_A[name])

    def spec(self, name):
        m = re.match(r"(.+)_smp(\d+)$", name)
        base = m[1] if m else name
        s = f"{name}={self.model(base)}@partner" + ("" if base == "reference" else "@standstill")
        return s + (f"@sample:{m[2]}" if m else "")

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
    def step_stoch(self):
        names = [n for n in ("a_s1", "a_s2") if os.path.exists(self.model(n))]
        if not names:
            return False
        names += [smp(n, k) for n in list(names) for k in SAMPLE_SEEDS]
        ok = True
        for k in self.sets:
            ok &= self.compare("stoch_eval", k, f"stoch_{k}", names)
        return ok

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
        trained = [n for n in names if n in RUNS]
        if not trained:
            return False
        names += [smp(n, k) for n in trained for k in SAMPLE_SEEDS]
        ok = True
        for k in self.sets:
            ok &= self.compare("eval", k, f"eval_{k}", names)
        return ok

    def step_gifs(self):
        ep = self.episodes("eval_large")
        if "reference" not in ep:
            return False
        ts, cfg = self.sets["large"]
        base = os.path.join(self.res, "gifs")
        os.makedirs(base, exist_ok=True)
        ok, info = True, {}

        def clip(name, start, left, right):
            return self.sh("gifs", [sys.executable, "scripts/rl/side_by_side_policies.py", "--config", cfg, "--test-set", ts,
                                    "--start", str(start), "--left", self.label_spec(left), "--right", self.label_spec(right),
                                    "--out", os.path.join(base, name)])
        if "a_s1" in ep and "e_s1" in ep:
            start = 185 if not self.dry else ep["reference"][0]["id"]
            ok &= clip("a_s1_vs_e_s1", start, "a_s1", "e_s1")
            info["a_s1_vs_e_s1"] = start
        for run in RUNS:
            if run not in ep:
                continue
            stalls = [r for r in ep[run] if r["reason"] == "timeout"]
            both = sorted([r for r in stalls if both_idle(r)], key=lambda r: -r["both_hold_steps"] / max(1, r["steps"]))
            pick = (both or stalls or [None])[0]
            if pick is None:
                info[f"stall_{run}"] = None                     # no stalls left: no clip
                continue
            ok &= clip(f"stall_{run}", pick["id"], "a_s1", run)
            info[f"stall_{run}"] = pick["id"]
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
        self.log(f"start ({'dry run' if self.dry else 'night 4'}); no new step after {self.deadline:%Y-%m-%d %H:%M}; free disk {free:.0f} GB")
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
            fn = {"stoch_eval": self.step_stoch, "eval": self.step_eval, "gifs": self.step_gifs}.get(step) or (lambda s=step: self.step_train(s))
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
    """SUMMARY.md: Run E against night 2's Run A and the reference, the deterministic vs sampled gap, stall metrics, the std
    and raw-mean curves from training, and the verdicts by fixed rules."""

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
        L = ["# D2 steering, night 4: bounded exploration (Run E)", "",
             f"*Written {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/rl/overnight_steering_4.py`"
             + (" (DRY RUN, tiny settings: the numbers mean nothing)" if n.dry else "") + ".*", ""]
        L += ["## Steps", "", "| step | status | finished |", "|---|---|---|"]
        for s in STEPS:
            p = os.path.join(n.dir, "steps", s + ".done")
            L.append(f"| {s} | {'done' if os.path.exists(p) else 'not done'} | {json.load(open(p))['end'] if os.path.exists(p) else ''} |")
        L += self.setup()
        L += self.curves()
        for k in n.sets:
            L += self.headline(k)
        L += self.gap()
        L += self.final_verdict()
        L += self.clips()
        return "\n".join(L) + "\n"

    # ── setup ───────────────────────────────────────────────────────────────
    def setup(self):
        n = self.n
        from copush.config import load_config
        ref = os.path.join(ROOT, REF)
        sha = hashlib.sha256(open(ref, "rb").read()).hexdigest() if os.path.exists(ref) else "missing"
        man = json.load(open(os.path.join(ROOT, "policies", "manifest.json")))
        want = [f["sha256"] for p in man["policies"] for f in p["files"] if f["dest"] == REF]
        ba = yaml.safe_load(open(n._abs(n.cfgs["e"])))["bounded_action"]
        bj = [json.load(open(p)) for r in RUNS if os.path.exists(p := os.path.join(n.out_dir(r), "bounded.json"))]
        before = sorted({b["ent_coef_before"] for b in bj if b.get("ent_coef_before") is not None})
        after = sorted({b["ent_coef_after"] for b in bj})
        L = ["", "## Setup", "",
             "- **The one change:** the bounded action head (`copush/bounded_policy.py`). Night 2's Run A is the comparison; "
             "everything else is identical (reward v1.1, stand-still threshold, budget, box starts, no start noise in training).",
             f"- **Mean bound:** mean = raw on [-1, 1], else sign(raw) * (1 + {ba['mean_bound'] - 1:g} * tanh((|raw| - 1) / "
             f"{ba['mean_bound'] - 1:g})), so it never leaves +-{ba['mean_bound']:g}. Inside [-1, 1] it is the identity, so the clipped "
             "deterministic action is unchanged. **Pre-launch check:** the warm start with this head, deterministic on stage1_large, "
             "gave 133/200, exactly the D2 reference, with all 200 episodes identical.",
             f"- **Std cap:** std = exp(min(log_std, log {ba['std_cap']:g})), set to {ba['init_std']:g} at warm start; the stored log_std "
             "is also clamped after every rollout.",
             f"- **ent_coef:** before (the warm start's) {', '.join(map(str, before)) or 'not recorded yet'}; after "
             f"{', '.join(map(str, after)) or ba.get('ent_coef')} (set in the config).",
             f"- **Warm start (both runs):** `{REF}`, sha256 `{sha}`"
             + (" (matches policies/manifest.json, policies-v1 stage1-d2)" if want and want[0] == sha else " (DOES NOT match the manifest)"),
             "- **Seeds:** E trained with seed 1 and seed 2 (stage.py `--seed`), like night 2's A. Sampled evaluation: sampling seeds "
             f"{', '.join(map(str, SAMPLE_SEEDS))} (torch seeded per episode from the sampling seed and the episode seed).",
             "- **Budget:** a fixed 2,000,000 duck steps per run, no early stopping; the 50-start check set is evaluated every checkpoint "
             "(200k duck steps) for the log only; checkpoints every 200k, only final policies kept",
             f"- **Stand-still threshold:** {load_config()['env']['stand_still']['vx_threshold']} m/s (the default, as in night 2)",
             "- **Sets:** `stage1_large.json` (no noise) and `stage1_noisy_large.json` (start noise), 200 starts each, 100-step limit. "
             "Deterministic = one episode per start with the policy mean (the headline); sampled = one episode per start per sampling seed.",
             "- **Rule for \"measurable\":** a difference counts only if its 95% interval (paired, same starts, seeds averaged) excludes 0 "
             "**and** the seed rates of the two groups do not overlap; otherwise it is \"no measurable difference\"."]
        L += ["", "| run | seed (from results.json) | trained | stopped early | ent_coef | wall time |", "|---|---|---|---|---|---|"]
        for run, (k, seed) in RUNS.items():
            rj = os.path.join(n.out_dir(run), "results.json")
            d = os.path.join(n.dir, "steps", run + ".done")
            if os.path.exists(rj):
                r = json.load(open(rj))
                wall = ""
                if os.path.exists(d):
                    t = json.load(open(d))
                    wall = f"{(dt.datetime.fromisoformat(t['end']) - dt.datetime.fromisoformat(t['start'])).total_seconds() / 60:.0f} min"
                L.append(f"| {run} | {r.get('seed', seed)} | {r.get('steps', '?')} of {r.get('steps_planned', '?')} duck steps | "
                         f"{'YES' if r.get('early_stopped') else 'no'} | {r.get('ent_coef', '?')} | {wall} |")
            else:
                L.append(f"| {run} | {seed} | not finished | | | |")
        return L

    # ── training curves ─────────────────────────────────────────────────────
    def std_rows(self, run):
        p = os.path.join(self.n.out_dir(run), "std.jsonl")
        if not os.path.exists(p):
            return []
        by = {}
        for ln in open(p):
            if ln.strip():
                r = json.loads(ln)
                by[r["step"]] = r                                 # a restart may repeat steps: keep the last
        return [by[k] for k in sorted(by)]

    def checkpoints(self, rows):
        """The first logged rollout, then the first rollout at or after every checkpoint, then the last."""
        if not rows:
            return []
        every = CKPT if not self.n.dry else 2048
        pick = [rows[0]]
        target = every
        for r in rows:
            if r["step"] >= target:
                if r is not pick[-1]:
                    pick.append(r)
                while target <= r["step"]:
                    target += every
        if rows[-1] is not pick[-1]:
            pick.append(rows[-1])
        return pick

    def curves(self):
        L = ["", "## Training curves: policy std and raw speed outputs", "",
             "*From `<run>/std.jsonl`, logged after every rollout (shown at each checkpoint). std = the effective std after the cap. "
             "|raw| > 3 = the share of the rollout's speed outputs whose unbounded mean is beyond 3 (the night 2 and 3 stall means "
             "were -1 to -8). below hold = the share whose raw speed output is under the hold cutoff (-0.867).*"]
        any_rows = False
        for run in RUNS:
            rows = self.checkpoints(self.std_rows(run))
            if not rows:
                continue
            any_rows = True
            L += ["", f"**{LABEL[run]}**", "", "| duck steps | std speed | std turn | cap | |raw speed| > 3 | raw speed below hold |",
                  "|---|---|---|---|---|---|"]
            for r in rows:
                L.append(f"| {r['step']:,} | {r['std_vx']:.3f} | {r['std_vyaw']:.3f} | {r['cap']:g} | {100 * r['frac_raw_vx_abs_gt3']:.2f}% | "
                         f"{100 * r['frac_raw_vx_below_hold']:.1f}% |")
            allr = self.std_rows(run)
            mx = max(r["std_vx"] for r in allr)
            L.append(f"\nMax std (speed) over all {len(allr)} rollouts: {mx:.4f} (cap {allr[0]['cap']:g}): "
                     f"**{'stayed at or under the cap' if mx <= allr[0]['cap'] + 1e-6 else 'ABOVE THE CAP'}**.")
        if not any_rows:
            L += ["", "Not trained yet."]
        return L

    def falling(self, run):
        """Fixed rule: the |raw| > 3 share is falling by the end if the last value is below both the first and the 1M value."""
        rows = self.std_rows(run)
        if len(rows) < 3:
            return None, ""
        f = [r["frac_raw_vx_abs_gt3"] for r in rows]
        mid = f[min(range(len(rows)), key=lambda i: abs(rows[i]["step"] - rows[-1]["step"] / 2))]
        if f[0] == 0 and f[-1] == 0:
            return True, f"0.00% at the start and at the end (nothing to fall)"
        return (f[-1] < f[0] and f[-1] < mid), f"{100 * f[0]:.2f}% at the start, {100 * mid:.2f}% at the midpoint, {100 * f[-1]:.2f}% at the end"

    # ── per set ─────────────────────────────────────────────────────────────
    def headline(self, k):
        n = self.n
        ep = n.episodes(f"eval_{k}")
        title = "Stage 1 starts, no noise" if k == "large" else "Stage 1 starts with duck start noise"
        L = ["", f"## {title} (deterministic, {LIMIT}-step limit, headline)", ""]
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
        groups = {"A": [x for x in ("a_s1", "a_s2") if x in ep], "E": [x for x in ("e_s1", "e_s2") if x in ep]}
        L += ["", "**Seed spread** (success per seed; spread = the gap between seed 1 and seed 2)", "",
              "| group | overall, seed 1 / seed 2 | spread | long-turn side, seed 1 / seed 2 | spread |", "|---|---|---|---|---|"]
        for g, members in groups.items():
            if not members:
                continue
            o = [sum(won(ep[m][i]) for i in allidx) / N for m in members]
            lg = [sum(won(ep[m][i]) for i in long_idx) / len(long_idx) for m in members]
            L.append(f"| {g} ({'night 2' if g == 'A' else 'night 4, bounded'}) | {' / '.join(pct(x) for x in o)} | "
                     f"{100 * (max(o) - min(o)):.1f} pts | {' / '.join(pct(x) for x in lg)} | {100 * (max(lg) - min(lg)):.1f} pts |")
        comps = [("E (seeds averaged) minus A (night 2, seeds averaged)", "the bounded-exploration effect", groups["E"], groups["A"]),
                 ("E (seeds averaged) minus the D2 reference", "bounded exploration + stand-still together", groups["E"], ["reference"])]
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
        L += ["", "**Stall and behavior metrics** (deterministic; both idle: both ducks held on 30% or more of an episode's steps; "
                  "holding steps: total steps a duck is held, over all episodes)", "",
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
        return L

    # ── deterministic vs sampled ────────────────────────────────────────────
    def gap_rows(self, ep, base):
        """Per start: mean success over the sampling seeds minus the deterministic success; overall and long-turn."""
        ks = [smp(base, k) for k in SAMPLE_SEEDS if smp(base, k) in ep]
        if base not in ep or not ks:
            return None
        det = ep[base]
        N = len(det)
        out = {}
        for where, idx in (("overall", list(range(N))), ("long-turn", [i for i, r in enumerate(det) if r["side"] == LONG])):
            d = [sum(won(ep[s][i]) for s in ks) / len(ks) - won(det[i]) for i in idx]
            m, h = mean_ci(d) if len(d) > 1 else (0.0, float("inf"))
            out[where] = dict(det=sum(won(det[i]) for i in idx) / len(idx), smp=[sum(won(ep[s][i]) for i in idx) / len(idx) for s in ks],
                              m=m, h=h, n=len(idx),
                              bi_det=sum(both_idle(det[i]) for i in idx), bi_smp=[sum(both_idle(ep[s][i]) for i in idx) for s in ks])
        return out

    def gap(self):
        n = self.n
        L = ["", "## Deterministic vs sampled (the train/eval gap)", "",
             "*Gap = sampled success (mean over the sampling seeds) minus deterministic success, per start, with a 95% interval. "
             "A positive gap means the mean action does worse than the policy it was trained as. A's numbers come from step 1 "
             "(stoch_eval), E's from step 4 (eval).*", "",
             "| policy | set | where | deterministic | sampled, per sampling seed | gap (sampled - det) | 95% interval | both idle, det / sampled |",
             "|---|---|---|---|---|---|---|---|"]
        have = False
        for k in n.sets:
            sets = {"A": n.episodes(f"stoch_{k}"), "E": n.episodes(f"eval_{k}")}
            for g, bases in (("A", ("a_s1", "a_s2")), ("E", ("e_s1", "e_s2"))):
                for b in bases:
                    r = self.gap_rows(sets[g], b)
                    if not r:
                        continue
                    have = True
                    for where in ("overall", "long-turn"):
                        x = r[where]
                        L.append(f"| {LABEL[b]} | {'no noise' if k == 'large' else 'noisy'} | {where} (n={x['n']}) | {pct(x['det'])} | "
                                 f"{' / '.join(pct(s) for s in x['smp'])} | {100 * x['m']:+.1f} | {100 * (x['m'] - x['h']):+.1f} to "
                                 f"{100 * (x['m'] + x['h']):+.1f} | {x['bi_det']} / {' / '.join(map(str, x['bi_smp']))} |")
        if not have:
            L += ["", "Not evaluated yet."]
        return L

    # ── verdict ─────────────────────────────────────────────────────────────
    def final_verdict(self):
        n = self.n
        L = ["", "## Verdict (fixed rules)", ""]
        out = []
        for k in n.sets:
            ep = n.episodes(f"eval_{k}")
            A, Ex = [x for x in ("a_s1", "a_s2") if x in ep], [x for x in ("e_s1", "e_s2") if x in ep]
            if not A or not Ex:
                continue
            setname = "no-noise set" if k == "large" else "noisy set"
            N = len(ep[A[0]])
            long_idx = [i for i, r in enumerate(ep[A[0]]) if r["side"] == LONG]
            m, h, _, _, v = self.verdict(ep, Ex, A, list(range(N)))
            m2, h2, _, _, v2 = self.verdict(ep, Ex, A, long_idx)
            out.append(f"- **E vs A, {setname}:** overall {100 * m:+.1f} points ({100 * (m - h):+.1f} to {100 * (m + h):+.1f}): **{v}**; "
                       f"long-turn side {100 * m2:+.1f} ({100 * (m2 - h2):+.1f} to {100 * (m2 + h2):+.1f}): **{v2}**.")
            bi = {x: sum(both_idle(r) for r in ep[x]) for x in A + Ex}
            aa, ea = sum(bi[x] for x in A) / len(A), sum(bi[x] for x in Ex) / len(Ex)
            drop = max(bi[x] for x in Ex) < min(bi[x] for x in A) and ea <= 0.5 * aa
            out.append(f"- *Does \"both idle\" drop meaningfully, {setname}?* **{'YES' if drop else 'NO'}.** Per seed: A "
                       f"{' / '.join(str(bi[x]) for x in A)}, E {' / '.join(str(bi[x]) for x in Ex)} (averages {aa:.1f} and {ea:.1f}). "
                       "Rule: both E seeds below both A seeds and the E average at most half the A average.")
            pv = {x: sum(r["max_pivot_run"] >= PIVOT_RUN for r in ep[x] if r["side"] == LONG) for x in A + Ex}
            pa, pe = sum(pv[x] for x in A) / len(A), sum(pv[x] for x in Ex) / len(Ex)
            out.append(f"- *Does the pivot survive, {setname}?* **{'YES' if pe >= 0.8 * pa else 'NO'}.** Long-turn starts with a pivot: "
                       f"A {' / '.join(str(pv[x]) for x in A)}, E {' / '.join(str(pv[x]) for x in Ex)} of {len(long_idx)}. "
                       "Rule: the E average at least 80% of the A average.")
            gaps = [(b, self.gap_rows(ep, b)) for b in Ex]
            gaps = [(b, g) for b, g in gaps if g]
            if gaps:
                closed = all(g["overall"]["m"] - g["overall"]["h"] <= 0 <= g["overall"]["m"] + g["overall"]["h"] for _, g in gaps)
                out.append(f"- *Is E's train/eval gap closed, {setname}?* **{'YES' if closed else 'NO'}.** Sampled minus deterministic, "
                           "overall: " + "; ".join(f"{LABEL[b]} {100 * g['overall']['m']:+.1f} ({100 * (g['overall']['m'] - g['overall']['h']):+.1f} "
                                                   f"to {100 * (g['overall']['m'] + g['overall']['h']):+.1f})" for b, g in gaps)
                           + ". Rule: every E seed's 95% interval includes 0.")
        for run in RUNS:
            f, txt = self.falling(run)
            if f is None:
                continue
            allr = self.std_rows(run)
            mx = max(r["std_vx"] for r in allr)
            out.append(f"- *{LABEL[run]}: is the share of speed outputs with |raw| > 3 falling by the end?* **{'YES' if f else 'NO, NOT FALLING'}** "
                       f"({txt}). Rule: the last value below both the first and the midpoint value. Std stayed "
                       f"{'under' if mx <= allr[0]['cap'] + 1e-6 else 'ABOVE'} the cap (max {mx:.3f}).")
        return L + (out or ["Not evaluated yet."])

    def clips(self):
        g = os.path.join(self.n.res, "gifs")
        found = sorted(glob.glob(os.path.join(g, "*", "*.gif")))
        starts = json.load(open(os.path.join(g, "starts.json"))) if os.path.exists(os.path.join(g, "starts.json")) else {}
        if not found and not starts:
            return ["", "## Clips", "", "Not made yet."]
        base = os.path.dirname(self.n.summary)
        L = ["", "## Clips", "", "Left: A seed 1 (night 2), right: the run named. Stall clips are the E run's time-out with the "
             "largest share of steps with both ducks held, on the no-noise set."]
        for run in RUNS:
            if f"stall_{run}" in starts and starts[f"stall_{run}"] is None:
                L += ["", f"**stall {run.replace('_', ' ')}:** no time-outs left on the no-noise set, so no clip."]
        for f in found:
            name = os.path.basename(os.path.dirname(f))
            L += ["", f"**{name.replace('_', ' ')}** (start {starts.get(name)}):", "", f"![{name}]({os.path.relpath(f, base)})"]
        return L


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="tiny settings into runs/d2-steering-night4-dry/")
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
