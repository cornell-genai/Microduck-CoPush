#!/usr/bin/env python3
"""Two central steering seeds with small start noise; then clean/noisy held-out evaluation.

Run from the repository root. Finished steps are skipped and stage.py resumes checkpoints.
Touch runs/steering-start-noise/STOP to stop before the next step.
"""
from pathlib import Path
import datetime as dt
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/steering-start-noise"
EXP = "experiments/steering/start-noise"
CONFIG = f"{EXP}/config.yaml"
REFS = {s: f"runs/steering/stand-still-s{s}/model.zip" for s in (1, 2)}
MODELS = {s: f"runs/steering/start-noise-s{s}/model.zip" for s in (1, 2)}
SETS = {
    "clean": ("experiments/steering/stand-still/config.yaml", "experiments/test_sets/stage1_large.json"),
    "noisy": (CONFIG, "experiments/test_sets/stage1_noisy_large.json"),
}


def log(message):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {message}"
    print(line, flush=True)
    with (RUN / "progress.log").open("a") as f:
        f.write(line + "\n")


def step(name, args):
    marker = RUN / "steps" / f"{name}.done"
    if marker.exists():
        log(f"skip {name} (done)")
        return
    if (RUN / "STOP").exists():
        log("STOP found; leaving remaining steps pending")
        raise SystemExit(0)
    log(f"starting {name}")
    with (RUN / "logs" / f"{name}.log").open("a") as f:
        result = subprocess.run([sys.executable, *args], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if result.returncode:
        log(f"FAILED {name}: exit {result.returncode}; see logs/{name}.log")
        raise SystemExit(result.returncode)
    marker.write_text(dt.datetime.now().isoformat() + "\n")
    log(f"finished {name}")


def main():
    for folder in ("logs", "steps", "videos"):
        (RUN / folder).mkdir(parents=True, exist_ok=True)
    # Refuse to reuse finished steps if their experiment inputs have changed.
    inputs = [CONFIG, *REFS.values(), *(v[1] for v in SETS.values()),
              "experiments/test_sets/stage1_noisy_checks.json"]
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs}
    manifest = RUN / "inputs.json"
    if manifest.exists() and json.loads(manifest.read_text()) != hashes:
        raise RuntimeError("Input hashes changed; use a new run directory")
    manifest.write_text(json.dumps(hashes, indent=2) + "\n")
    log("starting central steering noise round (two seeds)")
    for seed in (1, 2):
        step(f"train_s{seed}", ["scripts/rl/stage.py", "--config", CONFIG, "--seed", str(seed),
                               "--warm-start", REFS[seed]])
        if not (ROOT / MODELS[seed]).exists():
            raise RuntimeError(f"Missing final model for seed {seed}")
    for label, (config, test_set) in SETS.items():
        out = f"{EXP}/results/{label}"
        args = ["scripts/rl/compare_policies.py", "--config", config, "--test-set", test_set,
                "--workers", "8", "--out", out]
        for seed in (1, 2):
            args += ["--policy", f"clean_s{seed}={REFS[seed]}@standstill",
                     "--policy", f"noise_s{seed}={MODELS[seed]}@standstill"]
        step(f"eval_{label}", args)
        step(f"ci_{label}", ["scripts/rl/ci_report.py", "--comparison", f"{out}/comparison.json",
                              "--out", f"{out}/ci_report.md", "--pair", "noise_s1:clean_s1",
                              "--pair", "noise_s2:clean_s2"])
    episodes = json.loads((ROOT / EXP / "results/noisy/comparison.json").read_text())["episodes"]
    for label, success in (("success", True), ("failure", False)):
        candidates = [(seed, row) for seed in (1, 2) for row in episodes[f"noise_s{seed}"]
                      if (row["reason"] == "success") == success]
        if not candidates:
            log(f"No {label} episode available for clip")
            continue
        seed, row = max(candidates, key=lambda item: item[1]["needed_deg"])
        step(f"clip_{label}", ["scripts/rl/side_by_side_policies.py", "--config", CONFIG,
                               "--test-set", SETS["noisy"][1], "--start", str(row["id"]),
                               "--left", f"Clean-trained={REFS[seed]}@standstill",
                               "--right", f"Noise-adapted={MODELS[seed]}@standstill",
                               "--out", str(RUN / "videos" / label)])
    log("complete: clean/noisy comparisons and confidence intervals in " + EXP + "/results")


if __name__ == "__main__":
    main()
