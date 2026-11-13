#!/usr/bin/env python3
"""Train one generalization stage (experiments/<stage>/config.yaml): warm start, auto-widen, videos.

    nohup scripts/rl.sh scripts/rl/stage.py --config experiments/stage1-random-box-pose/config.yaml \
        >> runs/stage1-random-box-pose/train.log 2>&1 &

PPO is loaded from the stage's `warm_start` (its hyperparameters come with it; seed ppo.seed) and
trained on the resolved config (copush.experiments.load_stage) with ppo.n_envs SubprocVecEnv workers
for `steps` steps, counted from 0.
    widen        BoxRangeCallback: the box start range starts at widen.levels[0] of env.box_start and
                 widens one level whenever success on the current range reaches widen.threshold;
                 with `check_set` (a test-set JSON) the checks run on its fixed starts instead
    early stop   on the last level, success >= early_stop.success for early_stop.evals evals in a row
    videos       VideoEvalCallback on rl.eval_seed with the FULL range (one fixed start), capped at
                 max_videos including the final one
    checkpoints  every checkpoint_every steps, newest only, with state.json; a restart resumes there
    controller   the resolved config's `controller` (configs/copush.yaml; stages built on 01_reference
                 inherit central from configs/overnight.yaml). Decentral: each duck is its own SB3 entry
                 running the shared policy on its own view (copush.decentral); steps then count duck
                 entries (2 per sim step) and checks / videos run the policy once per duck
    gate         with `gate: [results.json, ...]` training starts only if at least one of those runs
                 ended its last (fixed-start) eval in success; otherwise exit code 3 (the queue marks
                 the run "gated")

Writes <out>/: config.yaml, state.json, checkpoints/, tb/, videos/, model.zip, results.json. The
exam on the fixed test set is separate: scripts/rl/test_set.py eval.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from copush.config import dump_config  # noqa: E402
from copush.experiments import load_stage, load_test_set, repo_path  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overnight import _prune_after  # noqa: E402


def read_json(path: str, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="experiments/<stage>/config.yaml")
    p.add_argument("--steps", type=int, default=None, help="override the stage's steps (smoke tests)")
    p.add_argument("--out", default=None, help="override the stage's out (smoke tests)")
    args = p.parse_args()

    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CallbackList

    from copush.decentral import make_vec_env
    from copush.rl_callbacks import BoxRangeCallback, VideoEvalCallback, behaviors, decide, run_episode

    stage, cfg = load_stage(args.config)
    if stage.get("gate"):
        passed = [g for g in stage["gate"] if ((read_json(repo_path(g), {}) or {}).get("eval_curve") or [[0, 0, ""]])[-1][2] == "success"]
        if not passed:
            print(f"gate failed: none of {stage['gate']} ended its last fixed-start eval in success; not training", flush=True)
            return 3
        print(f"gate passed: {passed}", flush=True)
    out = repo_path(args.out or stage["out"])
    os.makedirs(os.path.join(out, "checkpoints"), exist_ok=True)
    dump_config(cfg, os.path.join(out, "config.yaml"))
    pc, wd, es = cfg["ppo"], stage["widen"], stage["early_stop"]
    total = int(args.steps or stage["steps"])
    state_path = os.path.join(out, "state.json")
    state = read_json(state_path, {}) or {}
    ckpt = state.get("checkpoint") and os.path.join(out, state["checkpoint"])
    if not (ckpt and os.path.exists(ckpt)):
        state, ckpt = {}, None
    level = state.get("widen", {}).get("level", 0)

    train_cfg = copy.deepcopy(cfg)
    train_cfg["env"]["box_start"]["scale"] = wd["levels"][level]   # first resets already on this level
    video_cfg = copy.deepcopy(cfg)
    video_cfg["env"]["box_start"]["scale"] = 1.0
    video_cfg["env"]["box_start"]["hard_frac"] = 0.0                # the same video start for every stage
    vec = make_vec_env(train_cfg, pc["n_envs"])
    tb = os.path.join(out, "tb")
    if ckpt:
        model = PPO.load(ckpt, env=vec, device="cpu", tensorboard_log=tb)
        vec.seed(pc["seed"] + model.num_timesteps)
        _prune_after(os.path.join(out, "videos"), model.num_timesteps)
        print(f"resuming from {state['checkpoint']} (step {model.num_timesteps} of {total}, widen level {level})", flush=True)
    else:
        model = PPO.load(repo_path(stage["warm_start"]), env=vec, device="cpu", tensorboard_log=tb)
        model.set_random_seed(pc["seed"])
        vec.seed(pc["seed"])
        _prune_after(os.path.join(out, "videos"), -1)          # a fresh start: no stale evals
        print(f"warm start from {stage['warm_start']} ({model.num_timesteps} steps there); training {total} steps, "
              f"{pc['n_envs']} envs, reward {cfg['reward']['version']}, layout {cfg['env']['layout']}, "
              f"box_start {cfg['env']['box_start']}", flush=True)

    class StageVideoCallback(VideoEvalCallback):
        def __init__(self):
            super().__init__(video_cfg, out, verbose=1)
            v = state.get("video", {})
            self.best = v["best"] if v.get("best") is not None else -math.inf
            self.seen = set(v.get("seen", []))
            self.n_evals, self.last_eval = v.get("n_evals", 0), v.get("last_eval", 0)
            self.videos = [tuple(x) for x in v.get("videos", [])]
            self.last_ckpt = state.get("step", 0)
            self.wall0, self.t0 = state.get("wall_s", 0.0), time.perf_counter()

        def wall(self) -> float:
            return self.wall0 + time.perf_counter() - self.t0

        def evaluate(self, final: bool = False):
            stats = run_episode(self.env, self._act, self.seed)
            reason = "final" if final else decide(stats, self.best, self.seen, self.margin, self.n_evals == 0)
            if reason not in (None, "final") and len(self.videos) >= stage["max_videos"] - 1:
                reason = None                                    # cap; one slot is kept for the final video
            if reason is not None:
                self.vlog.record(self.env, self._act, self.num_timesteps, reason, seed=self.seed)
                self.videos.append((self.num_timesteps, reason))
            self.n_evals += 1
            self.best = max(self.best, stats["return"])
            self.seen |= behaviors(stats)
            self.logger.record("eval/return", stats["return"])
            self.logger.record("eval/success", float(stats["reason"] == "success"))
            with open(self.jsonl, "a") as f:
                f.write(json.dumps({"step": self.num_timesteps, "video": reason, **stats}) + "\n")
            print(f"eval @ {self.num_timesteps}: return {stats['return']:+.2f} ({stats['reason']}), video: {reason}, "
                  f"wall {self.wall() / 60:.1f} min", flush=True)
            return stats, reason

        def checkpoint(self) -> None:
            step = self.num_timesteps
            rel = os.path.join("checkpoints", f"ckpt_{step}.zip")
            self.model.save(os.path.join(out, rel))
            write_json(state_path, {
                "step": step, "checkpoint": rel, "wall_s": self.wall(),
                "video": {"best": None if self.best == -math.inf else self.best, "seen": sorted(self.seen),
                          "n_evals": self.n_evals, "last_eval": self.last_eval, "videos": self.videos},
                "widen": {"level": widen.level, "last_eval": widen.last_eval, "streak": widen.streak,
                          "history": widen.history, "reached_full_at": widen.reached_full_at}})
            for f in os.listdir(os.path.join(out, "checkpoints")):
                if f != os.path.basename(rel):
                    os.remove(os.path.join(out, "checkpoints", f))
            self.last_ckpt = step
            print(f"checkpoint at {step}", flush=True)

        def _on_step(self) -> bool:
            super()._on_step()
            if self.num_timesteps - self.last_ckpt >= stage["checkpoint_every"]:
                self.checkpoint()
            return True

    checks = load_test_set(stage["check_set"])["starts"] if stage.get("check_set") else None
    widen = BoxRangeCallback(cfg, wd["levels"], wd["threshold"], wd["eval_every"], wd["episodes"], wd["seed0"],
                             stop_success=es["success"], stop_evals=es["evals"], starts=checks, verbose=1)
    ws = state.get("widen", {})
    widen.level, widen.last_eval, widen.streak = level, ws.get("last_eval", 0), ws.get("streak", 0)
    widen.history, widen.reached_full_at = list(ws.get("history", [])), ws.get("reached_full_at")
    video = StageVideoCallback()
    remaining = total - (model.num_timesteps if ckpt else 0)
    if remaining > 0:
        model.learn(total_timesteps=remaining, callback=CallbackList([video, widen]), tb_log_name="ppo",
                    reset_num_timesteps=ckpt is None)
    else:                                                        # killed between the last step and results.json
        from stable_baselines3.common.logger import configure
        model.set_logger(configure(None, []))                    # learn() never ran, so there is no logger yet
        video.init_callback(model)
        video.num_timesteps = model.num_timesteps                # set by on_step, which never ran
        video.evaluate(final=True)
    video.checkpoint()
    vec.close()
    model.save(os.path.join(out, "model.zip"))

    vdir = os.path.join(out, "videos")
    evals = [json.loads(ln) for ln in open(os.path.join(vdir, "evals.jsonl")) if ln.strip()]
    vids = sorted(f for f in os.listdir(vdir) if f.endswith(".mp4"))
    pick = lambda e: e and next((f for f in vids if f.startswith(f"step_{e['step']}_")), None)   # noqa: E731
    best_v = max((e for e in evals if e["video"]), key=lambda e: e["return"], default=None)
    write_json(os.path.join(out, "results.json"), {
        "name": stage["name"], "change": stage.get("change", ""), "warm_start": stage["warm_start"],
        "steps": int(model.num_timesteps), "steps_planned": total, "wall_s": video.wall(),
        "early_stopped": widen.stopped_early, "final_level": widen.level, "levels": wd["levels"],
        "reached_full_at": widen.reached_full_at, "box_start": cfg["env"]["box_start"],
        "check_set": stage.get("check_set"), "reward_version": cfg["reward"]["version"],
        "controller": cfg["controller"], "gate": stage.get("gate"),
        "widen_history": widen.history, "eval_flags": sorted(k[5:] for k in video.seen if k.startswith("flag:")),
        "eval_endings": sorted(k[4:] for k in video.seen if k.startswith("end:")),
        "eval_curve": [(e["step"], e["return"], e["reason"]) for e in evals],
        "best_video": pick(best_v), "final_video": pick(evals[-1]) if evals else None, "videos": vids})
    print(f"done: {model.num_timesteps} steps in {video.wall() / 60:.1f} min, widen level {widen.level} of "
          f"{len(wd['levels']) - 1} (full range at {widen.reached_full_at}), early stop {widen.stopped_early}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
