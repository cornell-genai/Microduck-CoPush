"""Resolve every experiment config in the repo and dump the box-task settings it ends up with.

    scripts/rl.sh scripts/rl/check_config_pins.py                 # table on stdout
    scripts/rl.sh scripts/rl/check_config_pins.py --json out.json # the dump, for diffing before / after a change

Why: the box task (box.mass, env.max_steps, the reward terms, the mass randomization range) has defaults in
configs/copush.yaml. Changing a default must not change what an older config resolves to. This script is how that is
checked, and tests/test_heavybox.py runs the same resolution over every config on disk.

What is resolved, over experiments/**/*.yaml and configs/*.yaml:
  queue     a file with a `reference` block and `runs` (overnight queues): the reference alone and each run that has its
            own `overrides`, resolved the way scripts/rl/overnight.py does (its run_cfg)
  stage     any other file with `base` or `overrides`: copush.experiments.load_stage
  other     everything else (run lists, distill settings, the default config itself): reported, no box task of its own
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from copush.config import effective_reward, load_config  # noqa: E402
from copush.experiments import load_stage  # noqa: E402


def yaml_files() -> list:
    out = []
    for top in ("configs", "experiments"):
        for dp, _, fs in os.walk(os.path.join(ROOT, top)):
            out += [os.path.relpath(os.path.join(dp, f), ROOT) for f in fs if f.endswith((".yaml", ".yml"))]
    return sorted(out)


def kind(doc) -> str:
    if not isinstance(doc, dict):
        return "other"
    if isinstance(doc.get("reference"), dict) and "runs" in doc:      # before `stage`: a queue may name a `base` too
        return "queue"
    if "base" in doc or "overrides" in doc:
        return "stage"
    return "other"


def summary(cfg: dict) -> dict:
    """The settings the box task is made of, plus a hash of everything else (reward_versions excluded: it only grows)."""
    rest = {k: v for k, v in cfg.items() if k != "reward_versions"}
    return {"box.mass": cfg["box"]["mass"], "env.max_steps": cfg["env"]["max_steps"],
            "reward": effective_reward(cfg), "env.random.box_mass": cfg["env"]["random"]["box_mass"],
            "env.randomize": cfg["env"]["randomize"],
            "rest_sha": hashlib.sha256(json.dumps(rest, sort_keys=True, default=str).encode()).hexdigest()[:12]}


def _overnight():
    spec = importlib.util.spec_from_file_location("overnight_for_pins", os.path.join(ROOT, "scripts/rl/overnight.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve_all() -> dict:
    """{label: {"kind": ..., "summary": {...}} or {"kind": "other"}} for every YAML under configs/ and experiments/."""
    out, on = {}, None
    for rel in yaml_files():
        with open(os.path.join(ROOT, rel)) as f:
            doc = yaml.safe_load(f)
        k = kind(doc)
        if k == "stage":
            out[rel] = {"kind": k, "summary": summary(load_stage(rel)[1])}
        elif k == "queue":
            on = on or _overnight()
            q = on.load_queue(os.path.join(ROOT, rel))
            out[rel] = {"kind": k, "summary": summary(on.run_cfg(q, {}))}
            for run in q["runs"]:
                if run.get("overrides") and not run.get("stage"):
                    out[f"{rel}::{run['name']}"] = {"kind": "queue-run", "summary": summary(on.run_cfg(q, run))}
        else:
            out[rel] = {"kind": "other"}
    out["DEFAULT (configs/copush.yaml via load_config())"] = {"kind": "default", "summary": summary(load_config())}
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--json", help="write the full dump here")
    a = p.parse_args()
    res = resolve_all()
    if a.json:
        with open(a.json, "w") as f:
            json.dump(res, f, indent=1, sort_keys=True)
    for label, r in res.items():
        s = r.get("summary")
        if s:
            print(f"{r['kind']:9s} mass={s['box.mass']:<5} steps={s['env.max_steps']:<4} tp={s['reward']['time_penalty']:<8} "
                  f"v={s['reward']['version']:<9} mass_rng={s['env.random.box_mass']} rand={s['env.randomize']}  {label}")
        else:
            print(f"{'other':9s} (no box task of its own)  {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
