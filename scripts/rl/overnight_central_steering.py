#!/usr/bin/env python3
"""Matched central-controller steering experiment: control versus stand-still, two seeds each.

    scripts/rl.sh scripts/rl/overnight_central_steering.py --dry-run
    scripts/rl.sh scripts/rl/overnight_central_steering.py

The runner is restart-safe. Each completed step leaves a marker under runs/steering-overnight/steps;
training itself resumes from scripts/rl/stage.py checkpoints. Touch runs/steering-overnight/STOP to
stop after the current step. The full run writes evaluation artifacts and a continually refreshed
summary under experiments/steering/; a dry run keeps everything under runs/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ci_report import mean_ci, wilson, won  # noqa: E402

E = "experiments/steering"
REF = "runs/stage1-random-box-pose/model.zip"
TEST_SET = "experiments/test_sets/stage1_large.json"
ENV_CONFIG = "experiments/stage1-random-box-pose/config.yaml"
CONFIGS = {"control": f"{E}/control/config.yaml", "stand": f"{E}/stand-still/config.yaml"}
SEEDS = (1, 2)
SIDES = ("< -15", "-15 to +15", "> +15")
STEPS = ("baseline", "control_s1", "control_s2", "stand_s1", "stand_s2", "eval", "clips")


def _read(path):
    with open(path) as f:
        return json.load(f)


def _write(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(value, f, indent=1)
    os.replace(tmp, path)


def _pct(x):
    return f"{100 * x:.0f}%"


def _ci(k, n):
    lo, hi = wilson(k, n)
    return f"{_pct(k / n)} ({_pct(lo)} to {_pct(hi)})"


class Experiment:
    def __init__(self, dry=False):
        self.dry = dry
        suffix = "-dry" if dry else ""
        self.run_dir = os.path.join(ROOT, "runs", "steering-overnight" + suffix)
        self.results = os.path.join(self.run_dir, "results") if dry else os.path.join(ROOT, E, "results")
        self.summary = os.path.join(self.run_dir, "SUMMARY.md") if dry else os.path.join(ROOT, E, "SUMMARY.md")
        self.test_set = TEST_SET
        self.env_config = ENV_CONFIG
        self.configs = dict(CONFIGS)
        for d in ("steps", "logs", "configs", "sets"):
            os.makedirs(os.path.join(self.run_dir, d), exist_ok=True)
        if dry:
            self._make_dry_inputs()

    def _abs(self, path):
        return path if os.path.isabs(path) else os.path.join(ROOT, path)

    def _make_dry_inputs(self):
        def subset(src, per_side, dest):
            data = _read(self._abs(src))
            picked = []
            for lo, hi in ((-math.inf, -15), (-15, 15), (15, math.inf)):
                picked += [row for row in data["starts"] if lo < row["dyaw"] <= hi][:per_side]
            data["starts"] = [dict(row, id=i) for i, row in enumerate(picked)]
            _write(dest, data)
            return dest

        self.test_set = subset(TEST_SET, 3, os.path.join(self.run_dir, "sets", "large.json"))
        checks = subset("experiments/test_sets/stage1_checks.json", 2,
                        os.path.join(self.run_dir, "sets", "checks.json"))
        copied = {}
        for group, src in CONFIGS.items():
            with open(self._abs(src)) as f:
                cfg = yaml.safe_load(f)
            cfg.update(out=os.path.join(self.run_dir, "train", group + "-s1"), check_set=checks,
                       steps=4096, checkpoint_every=2048, max_videos=0)
            cfg["overrides"]["rl"] = {"eval_every": 2048}
            cfg["widen"].update(eval_every=2048, episodes=6)
            dest = os.path.join(self.run_dir, "configs", group + ".yaml")
            with open(dest, "w") as f:
                yaml.safe_dump(cfg, f, sort_keys=False)
            copied[group] = dest
        self.configs = copied

    def marker(self, step):
        return os.path.join(self.run_dir, "steps", step + ".done")

    def done(self, step):
        return os.path.exists(self.marker(step))

    def mark(self, step, started):
        _write(self.marker(step), {"started": started, "finished": f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"})

    def log(self, message):
        line = f"{dt.datetime.now():%H:%M:%S} {message}"
        print(line, flush=True)
        with open(os.path.join(self.run_dir, "progress.log"), "a") as f:
            f.write(line + "\n")

    def command(self, step, args):
        log = os.path.join(self.run_dir, "logs", step + ".log")
        with open(log, "a") as f:
            f.write("\n$ " + " ".join(args) + "\n")
            f.flush()
            code = subprocess.call(args, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        if code:
            self.log(f"{step} failed with exit code {code}; see {os.path.relpath(log, ROOT)}")
        return code == 0

    def model(self, group, seed):
        with open(self.configs[group]) as f:
            out = yaml.safe_load(f)["out"].rstrip("/")
        out = re.sub(r"-s\d+$", "", out) + f"-s{seed}"
        return os.path.join(out, "model.zip")

    def compare(self, step, out, policies):
        args = [sys.executable, "scripts/rl/compare_policies.py", "--config", self.env_config,
                "--test-set", self.test_set, "--workers", "2" if self.dry else "8", "--out", out]
        for policy in policies:
            args += ["--policy", policy]
        return self.command(step, args)

    def step_baseline(self):
        return self.compare("baseline", os.path.join(self.results, "baseline"),
                            [f"stage1={REF}", f"stage1_zero_shot_hold={REF}@standstill"])

    def step_train(self, group, seed):
        step = f"{group}_s{seed}"
        ok = self.command(step, [sys.executable, "scripts/rl/stage.py", "--config", self.configs[group],
                                 "--seed", str(seed)])
        return ok and os.path.exists(self._abs(self.model(group, seed)))

    def policies(self):
        policies = [f"stage1={REF}"]
        policies += [f"control_s{s}={self.model('control', s)}" for s in SEEDS]
        policies += [f"stand_s{s}={self.model('stand', s)}@standstill" for s in SEEDS]
        return policies

    def step_eval(self):
        return self.compare("eval", os.path.join(self.results, "comparison"), self.policies())

    def step_clips(self):
        if self.dry:
            return True
        path = os.path.join(self.results, "comparison", "comparison.json")
        eps = _read(path)["episodes"]
        control, stand = [f"control_s{s}" for s in SEEDS], [f"stand_s{s}" for s in SEEDS]
        rows = eps[stand[0]]

        def advantage(i):
            return sum(won(eps[n][i]) for n in stand) / len(stand) - sum(won(eps[n][i]) for n in control) / len(control)

        long_turn = [i for i, row in enumerate(rows) if row["side"] == "> +15"]
        successes = [i for i in long_turn if any(won(eps[n][i]) for n in stand)]
        failures = [i for i in long_turn if not won(eps[stand[0]][i])]
        picks = []
        if successes:
            picks.append(("success", max(successes, key=lambda i: (advantage(i), rows[i]["max_pivot_run"]))))
        if failures:
            picks.append(("failure", max(failures, key=lambda i: (rows[i]["both_hold_steps"], rows[i]["steps"]))))
        ok = True
        for label, i in picks:
            out = os.path.join(self.results, "gifs", label)
            args = [sys.executable, "scripts/rl/side_by_side_policies.py", "--config", self.env_config,
                    "--test-set", self.test_set, "--start", str(rows[i]["id"]),
                    "--left", f"Control seed 1={self.model('control', 1)}",
                    "--right", f"Stand-still seed 1={self.model('stand', 1)}@standstill", "--out", out]
            ok = self.command("clips", args) and ok
        return ok

    def _status_table(self):
        lines = ["| step | status | finished |", "|---|---|---|"]
        for step in STEPS:
            if self.done(step):
                data = _read(self.marker(step))
                lines.append(f"| {step} | done | {data['finished']} |")
            else:
                lines.append(f"| {step} | pending | |")
        return lines

    def _policy_table(self, eps):
        lines = ["| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |",
                 "|---|---|---|---|---|"]
        for name, rows in eps.items():
            cells = []
            for side in (None,) + SIDES:
                selected = rows if side is None else [row for row in rows if row["side"] == side]
                cells.append(_ci(sum(won(row) for row in selected), len(selected)))
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        return lines

    def _group_comparison(self, eps):
        control, stand = [f"control_s{s}" for s in SEEDS], [f"stand_s{s}" for s in SEEDS]
        lines = ["| scope | stand-still minus control | 95% interval | seed rates (stand; control) | verdict |",
                 "|---|---|---|---|---|"]
        for side in (None,) + SIDES:
            idx = [i for i, row in enumerate(eps[control[0]]) if side is None or row["side"] == side]
            diffs = [sum(won(eps[n][i]) for n in stand) / len(stand) -
                     sum(won(eps[n][i]) for n in control) / len(control) for i in idx]
            mean, half = mean_ci(diffs)
            sr = [sum(won(eps[n][i]) for i in idx) / len(idx) for n in stand]
            cr = [sum(won(eps[n][i]) for i in idx) / len(idx) for n in control]
            if mean - half > 0 and min(sr) > max(cr):
                verdict = "up"
            elif mean + half < 0 and max(sr) < min(cr):
                verdict = "down"
            else:
                verdict = "no measurable difference"
            scope = "overall" if side is None else f"{side} deg (n={len(idx)})"
            rates = f"{', '.join(_pct(x) for x in sr)}; {', '.join(_pct(x) for x in cr)}"
            lines.append(f"| {scope} | {100 * mean:+.1f} points | {100 * (mean-half):+.1f} to "
                         f"{100 * (mean+half):+.1f} | {rates} | **{verdict}** |")
        return lines

    def _behavior_table(self, eps):
        lines = ["| policy | time-outs | falls | box lost/tipped | overshoots | both held >=30% | pivots | push share A |",
                 "|---|---|---|---|---|---|---|---|"]
        for name, rows in eps.items():
            pushes = [row["push_share_a"] for row in rows if not math.isnan(row["push_share_a"])]
            lines.append(
                f"| {name} | {sum(row['reason'] == 'timeout' for row in rows)} | {sum(row['fell'] for row in rows)} | "
                f"{sum(row['box_lost'] for row in rows)} | {sum(row['overshoot'] for row in rows)} | "
                f"{sum(row['both_hold_steps'] >= 0.3 * row['steps'] for row in rows)} | "
                f"{sum(row['max_pivot_run'] >= 3 for row in rows)} | {_pct(sum(pushes) / len(pushes)) if pushes else 'n/a'} |")
        return lines

    def write_summary(self):
        lines = ["# Central steering: control versus stand-still", "",
                 f"*Updated {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/rl/overnight_central_steering.py`.*", "",
                 "## Steps", "", *self._status_table(), "", "## Setup", "",
                 "- Central controller, Stage 1 random box starts, reward v1.1.",
                 "- Both groups warm-start from the released Stage 1 central policy.",
                 "- Fixed 1,000,000-step budget, no early stopping, two PPO seeds per group.",
                 "- The only group difference is `env.stand_still.enabled`.",
                 "- Full results use the same 200 held-out starts for every policy.", ""]
        baseline = os.path.join(self.results, "baseline", "comparison.json")
        if os.path.exists(baseline):
            lines += ["## Zero-shot diagnostic", "", *self._policy_table(_read(baseline)["episodes"]), ""]
        comparison = os.path.join(self.results, "comparison", "comparison.json")
        if os.path.exists(comparison):
            eps = _read(comparison)["episodes"]
            lines += ["## Success", "", *self._policy_table(eps), "", "## Matched-group verdict", "",
                      *self._group_comparison(eps), "", "## Failure modes and behavior", "",
                      *self._behavior_table(eps), "", "Raw comparison: [results/comparison/comparison.md](results/comparison/comparison.md).", ""]
        with open(self.summary, "w") as f:
            f.write("\n".join(lines) + "\n")

    def run(self):
        handlers = {
            "baseline": self.step_baseline,
            "control_s1": lambda: self.step_train("control", 1),
            "control_s2": lambda: self.step_train("control", 2),
            "stand_s1": lambda: self.step_train("stand", 1),
            "stand_s2": lambda: self.step_train("stand", 2),
            "eval": self.step_eval,
            "clips": self.step_clips,
        }
        self.log("starting " + ("dry run" if self.dry else "full experiment"))
        self.write_summary()
        for step in STEPS:
            if self.done(step):
                self.log(f"skipping {step} (done)")
                continue
            if os.path.exists(os.path.join(self.run_dir, "STOP")):
                self.log("STOP found; leaving remaining steps pending")
                return 0
            started = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"
            self.log(f"starting {step}")
            if not handlers[step]():
                self.write_summary()
                return 1
            self.mark(step, started)
            self.write_summary()
            self.log(f"finished {step}")
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="nine-start evaluation and two-update training runs under runs/")
    args = parser.parse_args()
    if not os.path.exists(os.path.join(ROOT, REF)):
        parser.error(f"missing {REF}; run scripts/get_policies.sh")
    return Experiment(dry=args.dry_run).run()


if __name__ == "__main__":
    raise SystemExit(main())
