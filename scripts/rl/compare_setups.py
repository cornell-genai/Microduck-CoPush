#!/usr/bin/env python3
"""Compare training setups across seeds: learning curves, test-set success, cooperation.

    scripts/rl.sh scripts/rl/compare_setups.py eval --runs experiments/d2-from-scratch-comparison/runs.yaml
    scripts/rl.sh scripts/rl/compare_setups.py plot --runs experiments/d2-from-scratch-comparison/runs.yaml

runs.yaml lists each setup's seeds (run folders); missing folders are skipped, so new seeds slot in.
eval   the test set (scripts/rl/compare_policies.py, one deterministic episode per start) for every
       setup whose seeds have a model.zip, into <experiment>/setups/<setup>/results/test_set/
plot   <experiment>/comparison/: learning_curves.png (fixed-start eval success and return vs simulator
       steps, from each run's videos/evals.jsonl; one line per setup, shaded min to max over seeds when
       there are several; top row from 0, bottom row shifted right by a setup's prior_steps), test_set_success.png, cooperation.png, summary.md and summary.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from copush.experiments import repo_path  # noqa: E402

COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")       # categorical slots 1-4, fixed order
STYLES = ("-", "--", "-.", ":")
GRID = 25000                                                 # simulator steps between curve points


def load(runs_yaml: str):
    with open(repo_path(runs_yaml)) as f:
        spec = yaml.safe_load(f)
    exp = os.path.dirname(repo_path(runs_yaml))
    for name, s in spec["setups"].items():
        s["per_step"] = 2 if s["controller"] == "decentral" else 1
        s["runs"] = {int(k): v for k, v in s["seeds"].items() if os.path.isdir(repo_path(v))}
    return spec, exp


def evals(run: str, per_step: int):
    path = os.path.join(repo_path(run), "videos", "evals.jsonl")
    if not os.path.exists(path):
        return []
    rows = [json.loads(ln) for ln in open(path) if ln.strip()]
    return [dict(r, sim_step=r["step"] / per_step) for r in rows]


def on_grid(rows, end):
    """Each grid step's value is the latest eval at or before it (runs eval at different intervals)."""
    grid = np.arange(GRID, end + 1, GRID)
    out = {"step": grid, "success": [], "return": []}
    for g in grid:
        last = [r for r in rows if r["sim_step"] <= g + 1e-6]
        r = last[-1] if last else None
        out["success"].append(np.nan if r is None else float(r["reason"] == "success"))
        out["return"].append(np.nan if r is None else r["return"])
    return out


def cmd_eval(spec, exp) -> int:
    for name, s in spec["setups"].items():
        pol = [f"s{k}={v}/model.zip" + ("@partner" if s["controller"] == "decentral" else "")
               for k, v in sorted(s["runs"].items()) if os.path.exists(repo_path(f"{v}/model.zip"))]
        if not pol:
            print(f"{name}: no models yet")
            continue
        out = os.path.relpath(os.path.join(exp, "setups", name, "results", "test_set"), ROOT)
        cmd = [sys.executable, os.path.join(ROOT, "scripts/rl/compare_policies.py"), "--config", spec["test_config"],
               "--test-set", spec["test_set"], "--out", out] + [x for p in pol for x in ("--policy", p)]
        print(f"{name}: {len(pol)} seed(s) -> {out}", flush=True)
        subprocess.run(cmd, check=True, cwd=ROOT)
    return 0


def cmd_plot(spec, exp, runs_yaml) -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = os.path.join(exp, "comparison")
    os.makedirs(out, exist_ok=True)
    summary = {}
    for name, s in spec["setups"].items():
        seeds = {}
        for k, run in sorted(s["runs"].items()):
            rows = evals(run, s["per_step"])
            if not rows:
                continue
            first = next((r["sim_step"] for r in rows if r["reason"] == "success"), None)
            last = rows[-1]
            seeds[k] = {"run": run, "rows": rows, "first_success": first, "final_reason": last["reason"],
                        "final_return": last["return"], "final_steps": last["steps"],
                        "final_push_share_a": last["push_share"]["duck_a"], "end": last["sim_step"]}
        tpath = os.path.join(exp, "setups", name, "results", "test_set", "comparison.json")
        test = json.load(open(tpath))["episodes"] if os.path.exists(tpath) else {}
        for k, v in seeds.items():
            ep = test.get(f"s{k}")
            if ep:
                v["test"] = {"n": len(ep), "success": float(np.mean([e["reason"] == "success" for e in ep])),
                             "push_share_a": float(np.mean([e["push_share_a"] for e in ep])),
                             "both_touch": float(np.mean([e["both_touch_frac"] for e in ep])),
                             "lazy": int(sum(e["lazy"] for e in ep))}
        summary[name] = {"label": s["label"], "seeds": seeds, "prior": int(s.get("prior_steps", 0))}

    # learning curves. Top row: each run's own steps, all from 0. Bottom row: a setup with prior_steps
    # (training before this run, e.g. the distilled teacher's) starts that far to the right, so every
    # curve is plotted against its total simulator steps of training.
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for row, shift in enumerate((False, True)):
        for i, (name, sm) in enumerate(summary.items()):
            if not sm["seeds"]:
                continue
            end = max(v["end"] for v in sm["seeds"].values())
            g = [on_grid(v["rows"], end) for v in sm["seeds"].values()]
            n, prior = len(g), sm["prior"] if shift else 0
            x = (g[0]["step"] + prior) / 1e6
            label = f"{sm['label']} ({n} seed{'s' if n > 1 else ''})"
            if sm["prior"]:
                label += f"; bottom row: shifted right by its {sm['prior'] / 1e6:.2f}M prior steps"
            for ax, key in zip(axes[row], ("success", "return")):
                y = np.array([v[key] for v in g], dtype=float)
                ax.plot(x, np.nanmean(y, axis=0), color=COLORS[i], ls=STYLES[i], lw=2, label=label)
                if n > 1:
                    ax.fill_between(x, np.nanmin(y, axis=0), np.nanmax(y, axis=0), color=COLORS[i], alpha=0.15, lw=0)
        for ax, key in zip(axes[row], ("success", "return")):
            title = "eval success (share of seeds)" if key == "success" else "eval return"
            ax.set(title=f"Fixed start: {title}" + (", counting prior training" if shift else ", steps in this run"),
                   xlabel="simulator steps of training" + (", including prior training" if shift else " in this run")
                   + " (millions)", ylabel=key)
            if key == "success":
                ax.set_ylim(-0.05, 1.05)
            ax.set_xlim(left=0)
            ax.grid(alpha=0.25)
            ax.spines[["top", "right"]].set_visible(False)
            for i, sm in enumerate(summary.values()):           # bracket: the prior training, not plotted
                if shift and sm["prior"] and sm["seeds"]:
                    lo, hi = ax.get_ylim()
                    yb = lo + 0.06 * (hi - lo)
                    ax.annotate("", xy=(sm["prior"] / 1e6, yb), xytext=(0, yb),
                                arrowprops=dict(arrowstyle="<->", color=COLORS[i], lw=1.5))
                    ax.text(sm["prior"] / 2e6, yb + 0.03 * (hi - lo),
                            f"{sm['label']}: prior training ({sm['prior'] / 1e6:.2f}M steps, not plotted)",
                            ha="center", va="bottom", fontsize=8, color="#444444")
    fig.legend(*axes[0][0].get_legend_handles_labels(), frameon=False, loc="outside lower center", ncol=3, fontsize=9)
    fig.savefig(os.path.join(out, "learning_curves.png"), dpi=120)
    plt.close(fig)

    # test-set success and cooperation: bars (and the number under each label) are the seed mean, dots the seeds
    def bars(fname, panels):
        fig, axes = plt.subplots(1, len(panels), figsize=(4.2 * len(panels), 3.6), constrained_layout=True, squeeze=False)
        for ax, (key, title) in zip(axes[0], panels):
            ticks = []
            for i, name in enumerate(summary):
                vals = [v["test"][key] for v in summary[name]["seeds"].values() if "test" in v]
                ticks.append(summary[name]["label"].replace(", ", "\n") + (f"\n{np.mean(vals):.0%}" if vals else "\nnot run"))
                if not vals:
                    continue
                ax.bar(i, np.mean(vals), width=0.6, color=COLORS[i], edgecolor="white", linewidth=2)
                ax.scatter([i] * len(vals), vals, color="#333333", s=14, zorder=3)
            ax.set_xticks(range(len(summary)), ticks)
            ax.set(title=title, ylim=(0, 1))
            ax.spines[["top", "right"]].set_visible(False)
        fig.savefig(os.path.join(out, fname), dpi=120)
        plt.close(fig)

    n_test = {n: sum("test" in v for v in sm["seeds"].values()) for n, sm in summary.items()}
    bars("test_set_success.png", [("success", "Test set success (50 random box starts)")])
    bars("cooperation.png", [("push_share_a", "Duck A's share of the push (test set)"),
                             ("both_touch", "Steps with both ducks touching the box")])

    md = ["# Setup comparison", "",
          f"Runs: `{runs_yaml}`. Steps are simulator steps. Fixed-start numbers come",
          "from each run's deterministic eval episodes (videos/evals.jsonl); test-set numbers from",
          f"`{spec['test_set']}` (one deterministic episode per start, scripts/rl/compare_policies.py).", "",
          "| setup | seed | first fixed-start success | final fixed-start eval | final push share A | test success | test push share A | both touching | lazy duck |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name, sm in summary.items():
        for k, v in sm["seeds"].items():
            t = v.get("test")
            first = "never" if v["first_success"] is None else f"{v['first_success']:,.0f}"
            md.append(f"| {sm['label']} | {k} | {first} | "
                      f"{v['final_reason']}, {v['final_steps']} steps, return {v['final_return']:+.1f} | "
                      f"{v['final_push_share_a']:.0%} | "
                      + (f"{t['success']:.0%} | {t['push_share_a']:.0%} | {t['both_touch']:.0%} | {t['lazy']}/{t['n']} |"
                         if t else "not run | | | |"))
    md += ["", "Plots: [learning_curves.png](learning_curves.png), [test_set_success.png](test_set_success.png), "
           "[cooperation.png](cooperation.png).", ""]
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write("\n".join(md))
    js = {n: {"label": sm["label"], "seeds": {k: {kk: vv for kk, vv in v.items() if kk != "rows"}
                                              for k, v in sm["seeds"].items()}} for n, sm in summary.items()}
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(js, f, indent=1)
    print(f"wrote {out}: learning_curves.png, test_set_success.png, cooperation.png, summary.md ({n_test} test-set seeds)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=("eval", "plot"))
    p.add_argument("--runs", required=True, help="experiments/<experiment>/runs.yaml")
    args = p.parse_args()
    spec, exp = load(args.runs)
    return cmd_eval(spec, exp) if args.cmd == "eval" else cmd_plot(spec, exp, args.runs)


if __name__ == "__main__":
    sys.exit(main())
