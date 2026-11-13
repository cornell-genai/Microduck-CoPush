#!/usr/bin/env python3
"""PPO (stable-baselines3) on CoPushEnv, with tensorboard and video-on-change evaluation.

    scripts/rl.sh scripts/rl/train.py --layout close --steps 100000 --name A
    scripts/rl.sh scripts/rl/train.py --layout steer --steps 300000 --name B

Settings come from configs/copush.yaml (`ppo`, `rl`, `video`, `controller`; reward = --version,
default v1.1). --controller picks who decides: central (the default in the YAML: one policy for both),
d2 (each duck runs the shared policy on its own view plus its partner's position) or d1 (own view only).
Decentral steps count duck entries, 2 per simulator step.
Training envs: ppo.n_envs SubprocVecEnv workers (train split) wrapped in VecMonitor, so
tensorboard gets rollout/ep_rew_mean and rollout/ep_len_mean. Every rl.eval_every steps
VideoEvalCallback runs one deterministic episode on rl.eval_seed (the seed scripts/rl/baselines.py
records its videos on) and logs eval/*; videos only on baseline / improved / new_behavior / final.
At the end: --eval-episodes deterministic episodes on rl.eval_seed, rl.eval_seed + 1, ... (the
seeds baselines.py uses) for a table comparable with the baselines.

Writes runs/ppo-<name>-<layout>-<timestamp>/: config.yaml, model.zip, tb/, videos/, results.json,
report.md. Open tensorboard with:  scripts/rl.sh -m tensorboard.main --logdir runs
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from copush.config import dump_config, load_config, with_reward_version  # noqa: E402
from copush.decentral import make_vec_env, policy_action  # noqa: E402
from copush.env import CoPushEnv  # noqa: E402
from copush.rl_callbacks import CurriculumCallback, VideoEvalCallback  # noqa: E402
from copush.rl_eval import run_episodes, summarize  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--layout", default=None, help="env.layout (default: the YAML's)")
    p.add_argument("--version", default="v1.1", help="reward version")
    p.add_argument("--steps", type=int, default=None, help="default: ppo.total_steps")
    p.add_argument("--name", default="run")
    p.add_argument("--eval-episodes", type=int, default=5)
    p.add_argument("--controller", choices=("central", "d1", "d2"), default=None,
                   help="default: the YAML's controller (central)")
    p.add_argument("--stand-still", action="store_true", help="env.stand_still.enabled: vx below the threshold = velstand")
    args = p.parse_args()

    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CallbackList

    cfg = with_reward_version(load_config(), args.version)
    if args.controller:
        cfg["controller"] = ({"mode": "central"} if args.controller == "central"
                             else {"mode": "decentral", "include_partner": args.controller == "d2"})
    if args.layout:
        cfg["env"]["layout"] = args.layout
    if args.stand_still:
        cfg["env"]["stand_still"]["enabled"] = True
    layout = cfg["env"]["layout"]
    pc = cfg["ppo"]
    steps = args.steps or pc["total_steps"]
    run_id = f"ppo-{args.name}-{layout}-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(ROOT, "runs", run_id)
    os.makedirs(run_dir)
    dump_config(cfg, os.path.join(run_dir, "config.yaml"))
    print(f"run dir: runs/{run_id}  ({layout}, reward {args.version}, {steps} steps, {pc['n_envs']} envs, "
          f"controller {cfg['controller']})", flush=True)

    vec = make_vec_env(cfg, pc["n_envs"])
    vec.seed(pc["seed"])
    model = PPO("MlpPolicy", vec, n_steps=pc["n_steps"], batch_size=pc["batch_size"], n_epochs=pc["n_epochs"],
                learning_rate=pc["learning_rate"], gamma=pc["gamma"], gae_lambda=pc["gae_lambda"],
                clip_range=pc["clip_range"], ent_coef=pc["ent_coef"], seed=pc["seed"], device="cpu",
                tensorboard_log=os.path.join(run_dir, "tb"), verbose=0)
    video_cb = VideoEvalCallback(cfg, run_dir, verbose=1)
    cbs = [video_cb] + ([CurriculumCallback(cfg, verbose=1)] if cfg["env"]["curriculum"]["enabled"] else [])
    t0 = time.perf_counter()
    model.learn(total_timesteps=steps, callback=CallbackList(cbs), tb_log_name="ppo")
    wall = time.perf_counter() - t0
    vec.close()
    model.save(os.path.join(run_dir, "model.zip"))

    env = CoPushEnv(cfg, split="eval")
    act = lambda obs: policy_action(model, env, cfg, obs)          # noqa: E731
    stats = run_episodes(env, lambda s: act, args.eval_episodes, seed0=cfg["rl"]["eval_seed"])
    summ = summarize(stats)
    evals = [json.loads(line) for line in open(os.path.join(video_cb.vlog.dir, "evals.jsonl"))]
    curve = [(e["step"], e["return"], e["reason"]) for e in evals]
    at_100k = [c for c in curve if c[0] <= 100_000]
    flat_100k = len(at_100k) >= 2 and max(c[1] for c in at_100k) - min(c[1] for c in at_100k) < 0.5
    best = max((e for e in evals if e["video"]), key=lambda e: e["return"], default=None)
    vids = sorted(f for f in os.listdir(video_cb.vlog.dir) if f.endswith(".mp4"))
    best_video = next((f for f in vids if best and f.startswith(f"step_{best['step']}_")), None)
    vx = {d: sum(s["cmd_vx_mean"][d] for s in stats) / len(stats) for d in ("duck_a", "duck_b")}
    behavior = {"cmd_vx_mean": vx,
                "stands_still": all(v < 0.03 for v in vx.values()),
                "loses_box": summ["box_lost"] > 0,
                "contact_time_mean": summ["contact_time_mean"]}
    res = {"run_id": run_id, "layout": layout, "reward_version": args.version, "steps": steps,
           "wall_s": wall, "summary": summ, "eval_curve": curve, "flat_at_100k": flat_100k,
           "best_eval": best and {"step": best["step"], "return": best["return"], "reason": best["reason"]},
           "best_video": best_video, "behavior": behavior, "videos": vids}
    with open(os.path.join(run_dir, "results.json"), "w") as f:
        json.dump(res, f, indent=1)
    sh = summ["push_share_a_mean"]
    md = [f"# PPO {args.name} ({run_id})", "",
          f"Layout `{layout}`, reward {args.version}, {steps} steps, {pc['n_envs']} envs, wall time {wall / 60:.1f} min.", "",
          f"**Final policy** ({args.eval_episodes} deterministic episodes, seeds from {cfg['rl']['eval_seed']}): "
          f"mean return {summ['return_mean']:+.2f} ± {summ['return_std']:.2f}, success {100 * summ['success_rate']:.0f}%, "
          f"falls {summ['episodes_with_fall']}/{summ['n']}, box lost {summ['box_lost']}/{summ['n']}, "
          f"ends {summ['reasons']}, push share A/B "
          + ("-" if math.isnan(sh) else f"{100 * sh:.0f} / {100 - 100 * sh:.0f}%") + ".", "",
          f"Behavior: mean commanded vx A {vx['duck_a']:.3f}, B {vx['duck_b']:.3f} m/s; contact time "
          f"{summ['contact_time_mean']['duck_a']:.1f} / {summ['contact_time_mean']['duck_b']:.1f} s; "
          f"stands still: {behavior['stands_still']}; loses the box: {behavior['loses_box']}.", "",
          "**Eval curve** (one deterministic episode on the eval seed every "
          f"{cfg['rl']['eval_every']} steps):", "", "| step | return | ends |", "|---|---|---|"]
    md += [f"| {s} | {r:+.2f} | {why} |" for s, r, why in curve]
    md += ["", f"Flat up to 100k: {flat_100k}. Best eval: {res['best_eval']}; video: {best_video}.", "",
           "Videos: [videos/index.md](videos/index.md). Tensorboard: `scripts/rl.sh -m tensorboard.main --logdir runs`", ""]
    with open(os.path.join(run_dir, "report.md"), "w") as f:
        f.write("\n".join(md))
    print("\n".join(md), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
