#!/usr/bin/env python3
"""Central steering from +-45 to +-90 degrees, two matching warm-start seeds.

    scripts/rl.sh scripts/rl/overnight_wide_angles.py --dry-run
    scripts/rl.sh scripts/rl/overnight_wide_angles.py

Restart-safe: completed steps leave markers in runs/steering-wide-angles[-dry]/steps and stage.py
resumes training checkpoints. Touch <run dir>/STOP to stop after the current step.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
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

E = "experiments/steering/wide-angles"
CONFIG = f"{E}/config.yaml"
WIDE_SET = "experiments/test_sets/steering_wide_angles_large.json"
STAGE1_SET = "experiments/test_sets/stage1_large.json"
STAGE1_CONFIG = "experiments/stage1-random-box-pose/config.yaml"
REFS = {1: "runs/steering/stand-still-s1/model.zip", 2: "runs/steering/stand-still-s2/model.zip"}
SEEDS = (1, 2)
STEPS = ("baseline", "train_s1", "train_s2", "eval_wide", "forgetting", "clips")
ANGLE_BANDS = ((-90, -45), (-45, -15), (-15, 15), (15, 45), (45, 90))


def read_json(path):
    with open(path) as f:
        return json.load(f)


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(value, f, indent=1)
    os.replace(tmp, path)


def pct(value):
    return f"{100 * value:.0f}%"


def ci(k, n):
    lo, hi = wilson(k, n)
    return f"{pct(k / n)} ({pct(lo)} to {pct(hi)})"


class WideAngles:
    def __init__(self, dry=False):
        self.dry = dry
        suffix = "-dry" if dry else ""
        self.run_dir = os.path.join(ROOT, "runs", "steering-wide-angles" + suffix)
        self.results = os.path.join(self.run_dir, "results") if dry else os.path.join(ROOT, E, "results")
        self.summary = os.path.join(self.run_dir, "SUMMARY.md") if dry else os.path.join(ROOT, E, "SUMMARY.md")
        self.config = CONFIG
        self.wide_set = WIDE_SET
        self.stage1_set = STAGE1_SET
        for folder in ("steps", "logs", "sets", "configs"):
            os.makedirs(os.path.join(self.run_dir, folder), exist_ok=True)
        if dry:
            self.make_dry_inputs()

    def absolute(self, path):
        return path if os.path.isabs(path) else os.path.join(ROOT, path)

    def make_dry_inputs(self):
        def subset(src, per_band, name, bands):
            data = read_json(self.absolute(src))
            picked = []
            for lo, hi in bands:
                picked += [row for row in data["starts"] if lo < row["dyaw"] <= hi][:per_band]
            data["starts"] = [dict(row, id=i) for i, row in enumerate(picked)]
            dest = os.path.join(self.run_dir, "sets", name)
            write_json(dest, data)
            return dest

        self.wide_set = subset(WIDE_SET, 2, "wide.json", ANGLE_BANDS)
        self.stage1_set = subset(STAGE1_SET, 2, "stage1.json", ((-91, -15), (-15, 15), (15, 91)))
        checks = subset("experiments/test_sets/steering_wide_angles_checks.json", 1, "checks.json", ANGLE_BANDS)
        with open(self.absolute(CONFIG)) as f:
            cfg = yaml.safe_load(f)
        cfg.update(out=os.path.join(self.run_dir, "train", "wide-s1"), check_set=checks,
                   steps=4096, checkpoint_every=2048, max_videos=0)
        cfg["overrides"]["rl"] = {"eval_every": 2048}
        cfg["widen"].update(levels=[0.5, 1.0], eval_every=2048, episodes=5)
        self.config = os.path.join(self.run_dir, "configs", "wide.yaml")
        with open(self.config, "w") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)

    def marker(self, step):
        return os.path.join(self.run_dir, "steps", step + ".done")

    def done(self, step):
        return os.path.exists(self.marker(step))

    def mark(self, step, started):
        write_json(self.marker(step), {"started": started, "finished": f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"})

    def log(self, message):
        line = f"{dt.datetime.now():%H:%M:%S} {message}"
        print(line, flush=True)
        with open(os.path.join(self.run_dir, "progress.log"), "a") as f:
            f.write(line + "\n")

    def command(self, step, args):
        path = os.path.join(self.run_dir, "logs", step + ".log")
        with open(path, "a") as f:
            f.write("\n$ " + " ".join(args) + "\n")
            f.flush()
            code = subprocess.call(args, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        if code:
            self.log(f"{step} failed with exit code {code}; see {os.path.relpath(path, ROOT)}")
        return code == 0

    def model(self, seed):
        with open(self.config) as f:
            out = yaml.safe_load(f)["out"].rstrip("/")
        return os.path.join(re.sub(r"-s\d+$", "", out) + f"-s{seed}", "model.zip")

    def compare(self, step, config, test_set, out, policies):
        args = [sys.executable, "scripts/rl/compare_policies.py", "--config", config, "--test-set", test_set,
                "--workers", "2" if self.dry else "8", "--out", out]
        for policy in policies:
            args += ["--policy", policy]
        return self.command(step, args)

    def reference_policies(self):
        return [f"reference_s{s}={REFS[s]}@standstill" for s in SEEDS]

    def all_policies(self):
        return self.reference_policies() + [f"wide_s{s}={self.model(s)}@standstill" for s in SEEDS]

    def step_baseline(self):
        return self.compare("baseline", self.config, self.wide_set, os.path.join(self.results, "baseline"),
                            self.reference_policies())

    def step_train(self, seed):
        step = f"train_s{seed}"
        ok = self.command(step, [sys.executable, "scripts/rl/stage.py", "--config", self.config,
                                 "--seed", str(seed), "--warm-start", REFS[seed]])
        return ok and os.path.exists(self.absolute(self.model(seed)))

    def step_eval_wide(self):
        return self.compare("eval_wide", self.config, self.wide_set, os.path.join(self.results, "wide"),
                            self.all_policies())

    def step_forgetting(self):
        return self.compare("forgetting", STAGE1_CONFIG, self.stage1_set,
                            os.path.join(self.results, "stage1_forgetting"), self.all_policies())

    def step_clips(self):
        if self.dry:
            return True
        eps = read_json(os.path.join(self.results, "wide", "comparison.json"))["episodes"]
        rows = eps["wide_s1"]
        gains = [i for i in range(len(rows)) if won(rows[i]) and not won(eps["reference_s1"][i])]
        failures = [i for i, row in enumerate(rows) if not won(row)]
        picks = []
        if gains:
            picks.append(("success", max(gains, key=lambda i: abs(self.start_by_id(self.wide_set)[rows[i]["id"]]["dyaw"]))))
        if failures:
            picks.append(("failure", max(failures, key=lambda i: rows[i]["both_hold_steps"])))
        ok = True
        for label, i in picks:
            out = os.path.join(self.results, "gifs", label)
            args = [sys.executable, "scripts/rl/side_by_side_policies.py", "--config", self.config,
                    "--test-set", self.wide_set, "--start", str(rows[i]["id"]),
                    "--left", f"Before: +-45 policy={REFS[1]}@standstill",
                    "--right", f"After: +-90 policy={self.model(1)}@standstill", "--out", out]
            ok = self.command("clips", args) and ok
        return ok

    def start_by_id(self, path):
        return {row["id"]: row for row in read_json(self.absolute(path))["starts"]}

    def status_table(self):
        lines = ["| step | status | finished |", "|---|---|---|"]
        for step in STEPS:
            if self.done(step):
                lines.append(f"| {step} | done | {read_json(self.marker(step))['finished']} |")
            else:
                lines.append(f"| {step} | pending | |")
        return lines

    def policy_table(self, eps, starts, wide):
        lines = ["| policy | overall | " + " | ".join(self.band_label(b) for b in (ANGLE_BANDS if wide else
                 ((-91, -15), (-15, 15), (15, 91)))) + " |", "|---|---|" + "---|" * (5 if wide else 3)]
        bands = ANGLE_BANDS if wide else ((-91, -15), (-15, 15), (15, 91))
        for name, rows in eps.items():
            cells = [ci(sum(won(row) for row in rows), len(rows))]
            for band in bands:
                selected = [row for row in rows if self.in_band(starts[row["id"]]["dyaw"], band)]
                cells.append(ci(sum(won(row) for row in selected), len(selected)))
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        return lines

    @staticmethod
    def in_band(angle, band):
        return band[0] < angle <= band[1]

    @staticmethod
    def band_label(band):
        return f"{band[0]:g}..{band[1]:g} deg"

    def group_comparison(self, eps, starts, wide):
        refs, trained = [f"reference_s{s}" for s in SEEDS], [f"wide_s{s}" for s in SEEDS]
        bands = ((-91, 91),) + (ANGLE_BANDS if wide else ((-91, -15), (-15, 15), (15, 91)))
        lines = ["| scope | wide-trained minus reference | 95% interval | seed rates (wide; reference) | verdict |",
                 "|---|---|---|---|---|"]
        for band in bands:
            idx = [i for i, row in enumerate(eps[refs[0]]) if self.in_band(starts[row["id"]]["dyaw"], band)]
            diffs = [sum(won(eps[n][i]) for n in trained) / 2 - sum(won(eps[n][i]) for n in refs) / 2 for i in idx]
            mean, half = mean_ci(diffs)
            wr = [sum(won(eps[n][i]) for i in idx) / len(idx) for n in trained]
            rr = [sum(won(eps[n][i]) for i in idx) / len(idx) for n in refs]
            if mean - half > 0 and min(wr) > max(rr):
                verdict = "up"
            elif mean + half < 0 and max(wr) < min(rr):
                verdict = "down"
            else:
                verdict = "no measurable difference"
            scope = "overall" if band == (-91, 91) else self.band_label(band) + f" (n={len(idx)})"
            lines.append(f"| {scope} | {100*mean:+.1f} points | {100*(mean-half):+.1f} to {100*(mean+half):+.1f} | "
                         f"{', '.join(pct(x) for x in wr)}; {', '.join(pct(x) for x in rr)} | **{verdict}** |")
        return lines

    def curriculum_table(self):
        lines = ["| seed | steps | reached full range | final check success |", "|---|---|---|---|"]
        for seed in SEEDS:
            path = os.path.join(os.path.dirname(self.absolute(self.model(seed))), "results.json")
            if not os.path.exists(path):
                continue
            result = read_json(path)
            history = result["widen_history"]
            final = history[-1]["success_rate"] if history else float("nan")
            reached = result["reached_full_at"]
            lines.append(f"| {seed} | {result['steps']} | {reached if reached is not None else 'not reached'} | {pct(final)} |")
        return lines

    @staticmethod
    def behavior_table(eps):
        lines = ["| policy | time-outs | falls | box lost/tipped | overshoots | both held >=30% | pivots | push share A | lazy duck |",
                 "|---|---|---|---|---|---|---|---|---|"]
        for name, rows in eps.items():
            pushes = [row["push_share_a"] for row in rows if not math.isnan(row["push_share_a"])]
            share = pct(sum(pushes) / len(pushes)) if pushes else "n/a"
            lines.append(
                f"| {name} | {sum(row['reason'] == 'timeout' for row in rows)} | "
                f"{sum(row['fell'] for row in rows)} | {sum(row['box_lost'] for row in rows)} | "
                f"{sum(row['overshoot'] for row in rows)} | "
                f"{sum(row['both_hold_steps'] >= 0.3 * row['steps'] for row in rows)} | "
                f"{sum(row['max_pivot_run'] >= 3 for row in rows)} | {share} | "
                f"{sum(row['lazy'] for row in rows)} |")
        return lines

    def write_summary(self):
        lines = ["# Central steering: wider box angles", "",
                 f"*Updated {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/rl/overnight_wide_angles.py`.*", "",
                 "## Steps", "", *self.status_table(), "", "## Setup", "",
                 "- Central controller with stand-still, warm-started from the matching successful ±45-degree seed.",
                 "- One task change: final box angle range ±45 → ±90 degrees.",
                 "- Auto-widen levels: ±45, ±56.25, ±67.5, ±78.75 and ±90 degrees.",
                 "- Two seeds, fixed 1,000,000-step budget, 200 final test starts, 50 separate fixed checks.", ""]
        baseline = os.path.join(self.results, "baseline", "comparison.json")
        if os.path.exists(baseline):
            eps = read_json(baseline)["episodes"]
            starts = self.start_by_id(self.wide_set)
            lines += ["## Zero-shot on ±90 degrees", "", *self.policy_table(eps, starts, True), ""]
        lines += ["## Curriculum", "", *self.curriculum_table(), ""]
        for title, folder, test_set, wide in (("Final ±90-degree result", "wide", self.wide_set, True),
                                              ("Stage 1 forgetting check", "stage1_forgetting", self.stage1_set, False)):
            path = os.path.join(self.results, folder, "comparison.json")
            if os.path.exists(path):
                eps, starts = read_json(path)["episodes"], self.start_by_id(test_set)
                lines += [f"## {title}", "", *self.policy_table(eps, starts, wide), "",
                          *self.group_comparison(eps, starts, wide), "", "### Failure modes and behavior", "",
                          *self.behavior_table(eps), "",
                          f"Raw comparison: [results/{folder}/comparison.md](results/{folder}/comparison.md).", ""]
        gif_dir = os.path.join(self.results, "gifs")
        clips = [(name, paths[0]) for name in ("success", "failure")
                 if (paths := sorted(glob.glob(os.path.join(gif_dir, name, "*_side_by_side.gif"))))]
        if clips:
            lines += ["## Clips", ""]
            for name, path in clips:
                rel = os.path.relpath(path, os.path.dirname(self.summary))
                lines += [f"- {name.title()}: [{rel}]({rel})"]
            lines.append("")
        os.makedirs(os.path.dirname(self.summary), exist_ok=True)
        with open(self.summary, "w") as f:
            f.write("\n".join(lines) + "\n")

    def run(self):
        handlers = {"baseline": self.step_baseline, "train_s1": lambda: self.step_train(1),
                    "train_s2": lambda: self.step_train(2), "eval_wide": self.step_eval_wide,
                    "forgetting": self.step_forgetting, "clips": self.step_clips}
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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    missing = [path for path in REFS.values() if not os.path.exists(os.path.join(ROOT, path))]
    if missing:
        parser.error("missing matching stand-still warm starts: " + ", ".join(missing))
    return WideAngles(args.dry_run).run()


if __name__ == "__main__":
    raise SystemExit(main())
