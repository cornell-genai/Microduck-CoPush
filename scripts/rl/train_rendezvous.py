#!/usr/bin/env python3
"""Train the rendezvous coordinator (copush.rendezvous.RendezvousPairEnv) from scratch with PPO, one shared network per
duck, and check it on the fixed rendezvous check set every eval_every steps.

    scripts/rl.sh scripts/rl/train_rendezvous.py --config experiments/d2-rendezvous/config.yaml --seed 1 \
        --out runs/d2-rendezvous-r1-delta-reward/s1

PPO hyperparameters: the config's ppo block (random weights; no warm start, this is a new behavior). Steps count duck
entries (2 per simulator step), as scripts/rl/stage.py counts decentral runs. Every eval_every steps: a checkpoint
(newest only, with state.json, unless --keep-checkpoints keeps them all; a restart resumes from the newest) and scripts/rl/rendezvous_eval.py on the eval set, rendezvous
alone with the training ending (100 steps), appended to <out>/evals.jsonl. Writes <out>/model.zip and results.json,
and keeps <out>/best.zip (+ best.json) = the evaluated checkpoint with the most arrivals (ties: lower mean heading
error, then lower position error).

--eval-set: the starts those evals (and so best.zip) use. Default: the check set
(experiments/test_sets/rendezvous_check.json), never the test set, so best.zip is not picked on the starts results are
reported on. Runs r1-r6 picked on the test set (rendezvous_large.json); their run scripts pass it explicitly so they
reproduce.

--init <zip>: start from that zip's policy weights (network and action log-std; the config's PPO hyperparameters
still apply) instead of random ones, and evaluate them at step 0 (so best.zip can be the warm start itself if PPO
never beats it). Steps still count from 0, so --early-stop-step counts PPO steps only.

--early-stop-step (0 disables, the default): if an eval at or after this step finds 0 arrivals, training stops there
(not a crash: results.json is still written, with "aborted": true, and <out>/abort.json with the reason) instead of
running to the full step budget. Curriculum level changes (copush.rendezvous RendezvousPairEnv, cfg rendezvous.
curriculum.enabled) are printed as "curriculum: ..." lines when any worker's level changes, and each eval prints and
logs (evals.jsonl "train_by_level", "train_by_level_total") the training episodes' docking rate per curriculum level.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


CHECK_SET = "experiments/test_sets/rendezvous_check.json"
TEST_SET = "experiments/test_sets/rendezvous_large.json"


def eval_cmd(path, out_dir, episode_steps, workers, eval_set=CHECK_SET, starts=0):
    """The training-time eval: rendezvous alone on eval_set with the training ending."""
    cmd = [sys.executable, os.path.join(ROOT, "scripts/rl/rendezvous_eval.py"), "eval", "--rendezvous", path,
           "--set", eval_set, "--no-push", "--episode-steps", str(episode_steps), "--workers", str(workers), "--out", out_dir]
    return cmd + (["--starts", str(starts)] if starts else [])


def prune_checkpoints(ckpt_dir, newest, keep_all=False):
    """Delete every checkpoint in ckpt_dir except newest (the file name), unless keep_all (--keep-checkpoints)."""
    if keep_all:
        return
    for f in os.listdir(ckpt_dir):
        if f != newest:
            os.remove(os.path.join(ckpt_dir, f))


def best_key(row):
    """Order of checkpoints for best.zip: most arrivals, then lower mean heading error, then lower position error."""
    return (row["arrived"], -row["yaw_err_deg_mean"], -row["pos_err_cm_mean"])


def early_stop_reason(step, arrived, n, at_step):
    """None, or why to stop: an eval at/after at_step (duck steps; 0 disables) found 0 of n arrivals."""
    if at_step and step >= at_step and n and arrived == 0:
        return f"docking rate 0% (0/{n}) at step {step} (early-stop step {at_step})"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--steps", type=int, default=None, help="override the config's steps (dry runs)")
    ap.add_argument("--eval-every", type=int, default=None)
    ap.add_argument("--eval-starts", type=int, default=0, help="0 = the whole eval set")
    ap.add_argument("--eval-workers", type=int, default=6)
    ap.add_argument("--keep-checkpoints", action="store_true", help="keep every eval's checkpoint (checkpoints/ckpt_<step>.zip); "
                    "default keeps only the newest, as runs r1-r6")
    ap.add_argument("--eval-set", default=CHECK_SET, help="starts for the training evals and best.zip (default the check set)")
    ap.add_argument("--init", default=None, help="a PPO zip (e.g. bc_rendezvous.py's bc.zip) whose policy weights start "
                    "a scratch run instead of random ones; evaluated once at step 0")
    ap.add_argument("--early-stop-step", type=int, default=0, help="stop if an eval at/after this step finds 0 arrivals (0 disables)")
    a = ap.parse_args()

    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback

    from copush.config import dump_config
    from copush.experiments import load_stage
    from copush.rendezvous import make_rendezvous_vec_env

    stage, cfg = load_stage(a.config)
    cfg["ppo"]["seed"] = a.seed
    pc = cfg["ppo"]
    total = int(a.steps or stage["steps"])
    every = int(a.eval_every or stage["eval_every"])
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(os.path.join(out, "checkpoints"), exist_ok=True)
    dump_config(cfg, os.path.join(out, "config.yaml"))
    state_path = os.path.join(out, "state.json")
    state = read_json(state_path, {}) or {}
    ckpt = state.get("checkpoint") and os.path.join(out, state["checkpoint"])
    if not (ckpt and os.path.exists(ckpt)):
        state, ckpt = {}, None
    vec = make_rendezvous_vec_env(cfg, pc["n_envs"])
    if ckpt:
        model = PPO.load(ckpt, env=vec, device="cpu", tensorboard_log=os.path.join(out, "tb"))
        vec.seed(pc["seed"] + model.num_timesteps)
        print(f"resuming from {state['checkpoint']} (step {model.num_timesteps} of {total})", flush=True)
    else:
        model = PPO("MlpPolicy", vec, n_steps=pc["n_steps"], batch_size=pc["batch_size"], n_epochs=pc["n_epochs"],
                    learning_rate=pc["learning_rate"], gamma=pc["gamma"], gae_lambda=pc["gae_lambda"],
                    clip_range=pc["clip_range"], ent_coef=pc["ent_coef"], seed=pc["seed"], device="cpu",
                    tensorboard_log=os.path.join(out, "tb"), verbose=0)
        vec.seed(pc["seed"])
        if a.init:
            init = a.init if os.path.isabs(a.init) else os.path.join(ROOT, a.init)
            model.policy.load_state_dict(PPO.load(init, device="cpu").policy.state_dict())
            print(f"policy weights from {os.path.relpath(init, ROOT)}", flush=True)
        for stale in ("evals.jsonl", "best.json", "best.zip", "abort.json"):
            if os.path.exists(os.path.join(out, stale)):
                os.remove(os.path.join(out, stale))
        print(f"scratch: training {total} duck steps, seed {pc['seed']}, {pc['n_envs']} envs, eval every {every}", flush=True)
    wall0, t0 = state.get("wall_s", 0.0), time.perf_counter()
    abort = {"reason": None}
    by_level = {}                                       # training episodes since the last eval: level -> [episodes, arrived]
    by_level_total = {}                                 # the same over the whole run

    def evaluate(path, step):
        d = os.path.join(out, "evals", f"step_{step}")
        cmd = eval_cmd(os.path.relpath(path, ROOT), os.path.relpath(d, ROOT), cfg["rendezvous"]["max_steps"],
                       a.eval_workers, a.eval_set, a.eval_starts)
        subprocess.run(cmd, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        s = json.load(open(os.path.join(d, "results.json")))["summary"]["all"]
        row = {"step": step, "eval_set": a.eval_set, "arrival_rate": s["arrival_rate"], "arrived": s["arrived"], "n": s["n"],
               "mean_steps_to_arrive": s["mean_steps_to_arrive"], "pos_err_cm_mean": s["pos_err_cm_mean"],
               "yaw_err_deg_mean": s["yaw_err_deg_mean"], "duck_box_hits": s["duck_box_hits"],
               "duck_duck_hits": s["duck_duck_hits"], "falls": s["falls_rv"], "wall_s": round(wall0 + time.perf_counter() - t0, 1),
               "train_by_level": {str(k): {"episodes": v[0], "arrived": v[1]} for k, v in sorted(by_level.items())},
               "train_by_level_total": {str(k): {"episodes": v[0], "arrived": v[1]} for k, v in sorted(by_level_total.items())}}
        if by_level:
            print("training docking by curriculum level since the last eval: " + ", ".join(
                f"level {k}: {v[1]}/{v[0]} ({100 * v[1] / max(v[0], 1):.1f}%)" for k, v in sorted(by_level.items())), flush=True)
        by_level.clear()
        with open(os.path.join(out, "evals.jsonl"), "a") as f:
            f.write(json.dumps(row) + "\n")
        best = read_json(os.path.join(out, "best.json"))
        if best is None or best_key(row) > best_key(best):
            shutil.copy(path, os.path.join(out, "best.zip"))
            write_json(os.path.join(out, "best.json"), row)
        print(f"eval @ {step}: arrived {s['arrived']}/{s['n']}, position error {s['pos_err_cm_mean']:.1f} cm, "
              f"heading error {s['yaw_err_deg_mean']:.1f} deg, wall {row['wall_s'] / 60:.1f} min", flush=True)
        if abort["reason"] is None:
            r = early_stop_reason(step, s["arrived"], s["n"], a.early_stop_step)
            if r:
                abort["reason"] = r
                print(f"early-stop: {r}", flush=True)

    def checkpoint(step):
        rel = os.path.join("checkpoints", f"ckpt_{step}.zip")
        model.save(os.path.join(out, rel))
        write_json(state_path, {"step": step, "checkpoint": rel, "wall_s": wall0 + time.perf_counter() - t0})
        prune_checkpoints(os.path.join(out, "checkpoints"), os.path.basename(rel), a.keep_checkpoints)
        return os.path.join(out, rel)

    class EvalCallback(BaseCallback):
        def __init__(self):
            super().__init__()
            self.last = state.get("step", 0)
            self.last_level = {}

        def _on_step(self) -> bool:
            # curriculum_level is the same for both duck entries of one worker; dedupe by position in the list.
            for i, info in enumerate(self.locals.get("infos") or []):
                lvl = info.get("curriculum_level")
                if lvl is None:
                    continue
                w = i // 2
                prev = self.last_level.get(w, lvl)
                if prev != lvl:
                    print(f"curriculum: worker {w} level {prev} -> {lvl} at step {self.num_timesteps}", flush=True)
                self.last_level[w] = lvl
                if i % 2 == 0 and info.get("reason") is not None and "episode_level" in info:
                    for tally in (by_level, by_level_total):
                        c = tally.setdefault(int(info["episode_level"]), [0, 0])
                        c[0] += 1
                        c[1] += int(info["reason"] == "arrived")
            if self.num_timesteps - self.last >= every:
                self.last = self.num_timesteps
                evaluate(checkpoint(self.num_timesteps), self.num_timesteps)
            return abort["reason"] is None

    if a.init and not ckpt:                             # the warm start's own score, the curve's step 0
        evaluate(checkpoint(0), 0)
    remaining = total - (model.num_timesteps if ckpt else 0)
    if remaining > 0:
        model.learn(total_timesteps=remaining, callback=EvalCallback(), tb_log_name="ppo", reset_num_timesteps=ckpt is None)
    final = checkpoint(model.num_timesteps)
    vec.close()
    model.save(os.path.join(out, "model.zip"))
    evals = [json.loads(ln) for ln in open(os.path.join(out, "evals.jsonl"))] if os.path.exists(os.path.join(out, "evals.jsonl")) else []
    if not evals or evals[-1]["step"] != model.num_timesteps:
        if abort["reason"] is None:                         # an aborted run already has its final eval logged
            evaluate(final, model.num_timesteps)
            evals = [json.loads(ln) for ln in open(os.path.join(out, "evals.jsonl"))]
    write_json(os.path.join(out, "results.json"), {
        "name": stage["name"], "init": os.path.relpath(a.init, ROOT) if a.init and os.path.isabs(a.init) else (a.init or "scratch"), "eval_set": a.eval_set, "seed": pc["seed"], "steps": int(model.num_timesteps), "steps_planned": total,
        "wall_s": wall0 + time.perf_counter() - t0, "ppo": pc, "rendezvous": cfg["rendezvous"], "eval_curve": evals,
        "aborted": abort["reason"] is not None, "abort_reason": abort["reason"]})
    if abort["reason"]:
        write_json(os.path.join(out, "abort.json"), {"reason": abort["reason"], "step": int(model.num_timesteps)})
        print(f"aborted early: {abort['reason']}", flush=True)
    else:
        print(f"done: {model.num_timesteps} steps in {(wall0 + time.perf_counter() - t0) / 60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
