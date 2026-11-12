"""Stable-Baselines3 callback: periodic evaluation episodes, video only when something changed.

    from copush.rl_callbacks import VideoEvalCallback
    model.learn(total_timesteps, callback=VideoEvalCallback(cfg, run_dir))

Every `rl.eval_every` training steps it runs ONE deterministic episode on `rl.eval_seed` (a
held-out seed, env split "eval") and saves runs/<run_id>/videos/step_<n>_<reason>.mp4 only when:

    baseline      the first evaluation
    improved      eval return beats the best so far by more than rl.improve_margin
    new_behavior  the episode shows an ending (success / fall / box_lost / box_tipped / timeout)
                  or a RewardMonitor flag kind that no earlier evaluation showed
    final         always, when training ends

Evaluation is deterministic (fixed seed, deterministic policy, exact env resets), so the episode
is first run without rendering and re-run with the camera only when a video is due. Every
evaluation is logged to SB3's logger (eval/*) and appended to videos/evals.jsonl.
"""
from __future__ import annotations

import json
import math
import os
from typing import Optional, Set, Tuple

from stable_baselines3.common.callbacks import BaseCallback

from copush.env import CoPushEnv
from copush.video import VideoLog


def behaviors(stats: dict) -> Set[str]:
    return {f"end:{stats['reason']}"} | {f"flag:{f.split(':')[0]}" for f in stats["flags"]}


def decide(stats: dict, best: float, seen: Set[str], margin: float, first: bool) -> Optional[str]:
    """Which video to save for this evaluation (None = none). Priority baseline > improved > new_behavior."""
    if first:
        return "baseline"
    if stats["return"] > best + margin:
        return "improved"
    if behaviors(stats) - seen:
        return "new_behavior"
    return None


def run_episode(env: CoPushEnv, act, seed: int) -> dict:
    obs, _ = env.reset(seed=seed)
    while True:
        obs, _, term, trunc, info = env.step(act(obs))
        if term or trunc:
            return info["episode_stats"]


class VideoEvalCallback(BaseCallback):
    def __init__(self, cfg: dict, run_dir: str, every: Optional[int] = None, seed: Optional[int] = None,
                 margin: Optional[float] = None, verbose: int = 0):
        super().__init__(verbose)
        rl = cfg["rl"]
        self.cfg, self.run_dir = cfg, run_dir
        self.every = int(every if every is not None else rl["eval_every"])
        self.seed = int(seed if seed is not None else rl["eval_seed"])
        self.margin = float(margin if margin is not None else rl["improve_margin"])
        self.best = -math.inf
        self.seen: Set[str] = set()
        self.n_evals = 0
        self.last_eval = 0
        self.videos = []

    def _init_callback(self) -> None:
        self.env = CoPushEnv(self.cfg, split="eval")
        self.vlog = VideoLog(self.run_dir, self.cfg["video"])
        self.jsonl = os.path.join(self.vlog.dir, "evals.jsonl")

    def _act(self, obs):
        return self.model.predict(obs, deterministic=True)[0]

    def _on_step(self) -> bool:
        if self.num_timesteps - self.last_eval >= self.every:
            self.last_eval = self.num_timesteps
            self.evaluate()
        return True

    def _on_training_end(self) -> None:
        self.evaluate(final=True)

    def evaluate(self, final: bool = False) -> Tuple[dict, Optional[str]]:
        stats = run_episode(self.env, self._act, self.seed)
        reason = "final" if final else decide(stats, self.best, self.seen, self.margin, self.n_evals == 0)
        if reason is not None:
            vstats = self.vlog.record(self.env, self._act, self.num_timesteps, reason, seed=self.seed)
            if abs(vstats["return"] - stats["return"]) > 1e-6:     # should not happen: eval is deterministic
                print(f"warning: video episode return {vstats['return']:.4f} != eval {stats['return']:.4f}")
            self.videos.append((self.num_timesteps, reason))
        self.n_evals += 1
        self.best = max(self.best, stats["return"])
        self.seen |= behaviors(stats)
        share = stats["push_share"]
        self.logger.record("eval/return", stats["return"])
        self.logger.record("eval/success", float(stats["reason"] == "success"))
        self.logger.record("eval/final_dist", stats["final_dist"])
        self.logger.record("eval/push_share_a", 0.0 if math.isnan(share["duck_a"]) else share["duck_a"])
        with open(self.jsonl, "a") as f:
            f.write(json.dumps({"step": self.num_timesteps, "video": reason, **{k: v for k, v in stats.items()}}) + "\n")
        if self.verbose:
            print(f"eval @ {self.num_timesteps}: return {stats['return']:+.2f} ({stats['reason']}), video: {reason}")
        return stats, reason
