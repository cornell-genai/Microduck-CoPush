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


def run_episode(env: CoPushEnv, act, seed: int, options: Optional[dict] = None) -> dict:
    obs, _ = env.reset(seed=seed, options=options)
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


# ── curriculum (env.curriculum, off by default) ──────────────────────────────

def next_level(level: int, success_rate: float, threshold: float, n_levels: int) -> int:
    return level + 1 if success_rate >= threshold and level + 1 < n_levels else level


class CurriculumCallback(BaseCallback):
    """Every `every` steps: eval_episodes deterministic episodes at the current level (held-out
    seeds, split "eval"); success rate >= success_threshold moves every training env (and the eval
    env) to the next level of env.curriculum (target further along the push line / sideways)."""

    def __init__(self, cfg: dict, every: Optional[int] = None, verbose: int = 0):
        super().__init__(verbose)
        self.cfg = cfg
        self.cur = cfg["env"]["curriculum"]
        self.every = int(every if every is not None else cfg["rl"]["eval_every"])
        self.level, self.last_eval, self.history = 0, 0, []

    def _init_callback(self) -> None:
        self.env = CoPushEnv(self.cfg, split="eval")
        self.env.set_curriculum_level(self.level)

    def _act(self, obs):
        return self.model.predict(obs, deterministic=True)[0]

    def _on_step(self) -> bool:
        if self.num_timesteps - self.last_eval < self.every:
            return True
        self.last_eval = self.num_timesteps
        seed0 = self.cfg["env"]["heldout_seeds"][0]
        wins = sum(run_episode(self.env, self._act, seed0 + i)["reason"] == "success"
                   for i in range(self.cur["eval_episodes"]))
        rate = wins / self.cur["eval_episodes"]
        new = next_level(self.level, rate, self.cur["success_threshold"], len(self.cur["distances"]))
        self.history.append({"step": self.num_timesteps, "level": self.level, "success_rate": rate})
        self.logger.record("curriculum/level", self.level)
        self.logger.record("curriculum/success_rate", rate)
        if new != self.level:
            self.level = new
            self.training_env.env_method("set_curriculum_level", new)
            self.env.set_curriculum_level(new)
            if self.verbose:
                print(f"curriculum: level {new} at step {self.num_timesteps} (success {rate:.0%})")
        return True


# ── auto-widen the box start range (env.box_start) ───────────────────────────

class BoxRangeCallback(BaseCallback):
    """Every `every` steps: `episodes` deterministic episodes on held-out seeds seed0, seed0 + 1, ...
    with the box sampled from the current range (env.box_start scaled by levels[level]). Success
    >= threshold widens every training env (and the eval env) one level. On the last level,
    success >= stop_success for stop_evals evaluations in a row stops training (stop_evals 0: never).
    With `starts` (a fixed check set of explicit box poses, copush.experiments) each evaluation runs
    one episode per start instead (seed seed0 + i), and the range only matters for training.
    `history` has one dict per evaluation."""

    def __init__(self, cfg: dict, levels, threshold: float, every: int, episodes: int, seed0: int,
                 stop_success: float = 1.1, stop_evals: int = 0, starts=None, verbose: int = 0):
        super().__init__(verbose)
        self.starts = list(starts) if starts else None
        self.cfg, self.levels, self.threshold = cfg, list(levels), threshold
        self.every, self.episodes, self.seed0 = int(every), int(episodes), int(seed0)
        self.stop_success, self.stop_evals = stop_success, int(stop_evals)
        self.level, self.last_eval, self.streak, self.history = 0, 0, 0, []
        self.reached_full_at = None
        self.stopped_early = False

    def _init_callback(self) -> None:
        self.env = CoPushEnv(self.cfg, split="eval")
        self.env.set_box_range(self.levels[self.level])
        self.training_env.env_method("set_box_range", self.levels[self.level])

    def _act(self, obs):
        return self.model.predict(obs, deterministic=True)[0]

    def _on_step(self) -> bool:
        if self.num_timesteps - self.last_eval < self.every:
            return True
        self.last_eval = self.num_timesteps
        if self.starts:
            stats = [run_episode(self.env, self._act, self.seed0 + i, {"box": s}) for i, s in enumerate(self.starts)]
        else:
            stats = [run_episode(self.env, self._act, self.seed0 + i) for i in range(self.episodes)]
        rate = sum(s["reason"] == "success" for s in stats) / len(stats)
        full = self.level == len(self.levels) - 1
        self.streak = self.streak + 1 if full and rate >= self.stop_success else 0
        new = next_level(self.level, rate, self.threshold, len(self.levels))
        self.history.append({"step": self.num_timesteps, "level": self.level, "scale": self.levels[self.level],
                             "success_rate": rate, "falls": sum(any(s["fell"].values()) for s in stats),
                             "box_lost": sum(s["reason"] in ("box_lost", "box_tipped") for s in stats)})
        if self.starts:                                  # success per box angle side: < -15, -15..+15, > +15 deg
            side = lambda d: 0 if d < -15 else (2 if d > 15 else 1)          # noqa: E731
            by = [[0, 0], [0, 0], [0, 0]]
            for st0, s in zip(self.starts, stats):
                by[side(st0["dyaw"])][0] += s["reason"] == "success"
                by[side(st0["dyaw"])][1] += 1
            self.history[-1]["by_side"] = by
        self.logger.record("widen/level", self.level)
        self.logger.record("widen/scale", self.levels[self.level])
        self.logger.record("widen/success_rate", rate)
        if self.verbose:
            print(f"widen @ {self.num_timesteps}: level {self.level} (scale {self.levels[self.level]:.2f}) "
                  f"success {rate:.0%}" + (f", full-range streak {self.streak}" if full else "")
                  + (" (by side " + " / ".join(f"{w}/{n}" for w, n in self.history[-1]["by_side"]) + ")"
                     if self.starts else ""), flush=True)
        if new != self.level:
            self.level = new
            self.training_env.env_method("set_box_range", self.levels[new])
            self.env.set_box_range(self.levels[new])
            if new == len(self.levels) - 1:
                self.reached_full_at = self.num_timesteps
            if self.verbose:
                print(f"widen: level {new} (scale {self.levels[new]:.2f}) at step {self.num_timesteps}", flush=True)
        if self.stop_evals and self.streak >= self.stop_evals:
            self.stopped_early = True
            return False
        return True
