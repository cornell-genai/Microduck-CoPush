"""Offscreen mp4s of CoPush runs, with a text overlay.

VideoRecorder   one mp4 from frames you feed it (scripts/copush_sim.py --record)
record_episode  one CoPushEnv episode -> short mp4 (sped up, small), returns the episode stats
VideoLog        runs/<run_id>/videos/step_<training_step>_<reason>[_<label>].mp4 + index.md

Same camera as the --record videos: free camera behind the ducks, following the midpoint of the
ducks and the box.
"""
from __future__ import annotations

import math
import os
from typing import Callable, Optional

import mediapy
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class VideoRecorder:
    def __init__(self, model: mujoco.MjModel, path: str, fps: int = 25, width: int = 960, height: int = 540):
        self.renderer = mujoco.Renderer(model, height=height, width=width)
        self.cam = mujoco.MjvCamera()
        self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.cam.distance, self.cam.azimuth, self.cam.elevation = 1.6, 40.0, -30.0
        self._lookat = None
        self.writer = mediapy.VideoWriter(path, shape=(height, width), fps=fps)
        self.writer.__enter__()
        self.line_h = min(22, max(14, round(height / 15)))
        try:
            self.font = ImageFont.load_default(size=self.line_h - 4)
        except TypeError:                       # Pillow < 10.1
            self.font = ImageFont.load_default()

    def frame(self, data: mujoco.MjData, state: dict, lines) -> None:
        # follow the midpoint of the ducks and the box, smoothed so the camera does not jitter
        pts = [state["box"]["position"], state["duck_a"]["position"], state["duck_b"]["position"]]
        target = np.array([np.mean([p[0] for p in pts]), np.mean([p[1] for p in pts]), 0.05])
        self._lookat = target if self._lookat is None else 0.9 * self._lookat + 0.1 * target
        self.cam.lookat[:] = self._lookat
        self.renderer.update_scene(data, self.cam)
        img = Image.fromarray(self.renderer.render())
        draw = ImageDraw.Draw(img)
        y = 8
        for line in lines:
            draw.text((11, y + 1), line, font=self.font, fill=(0, 0, 0))
            draw.text((10, y), line, font=self.font, fill=(255, 255, 255))
            y += self.line_h
        self.writer.add_image(np.asarray(img))

    def close(self) -> None:
        self.writer.__exit__(None, None, None)
        self.renderer.close()


# ── episodes (copush.env) ────────────────────────────────────────────────────

REASONS = ("baseline", "improved", "new_behavior", "final")


def overlay_lines(st: dict, ret: float) -> list:
    pol = {"velstand": "walk", "shoepush": "push"}
    return [f"t {st['t']:5.2f}s  reward so far {ret:+.2f}",
            f"box->target {st['box_to_target']:.2f} m  yaw err {math.degrees(st['yaw_error']):.0f} deg"
            + ("  INSIDE" if st["inside"] else ""),
            "  ".join(f"{d[-1].upper()}: {st[d]['policy']} ({pol.get(st[d]['policy'], '?')})"
                      + (" DOWN" if st[d]["down"] else "") for d in ("duck_a", "duck_b"))]


def record_episode(env, act: Callable, path: str, seed: Optional[int] = None,
                   video_cfg: Optional[dict] = None) -> dict:
    """Run one episode of `env` with act(obs) -> action, writing `path`. Returns episode_stats.

    Frames are taken every `speedup / (fps * CONTROL_DT)` control steps, so the video plays
    `speedup` times faster than real time.
    """
    from copush.sim import CONTROL_DT
    vc = {"width": 480, "height": 270, "fps": 25, "speedup": 2, **(video_cfg or {})}
    every = max(1, round(vc["speedup"] / (vc["fps"] * CONTROL_DT)))
    rec = VideoRecorder(env.sim.m, path, fps=vc["fps"], width=vc["width"], height=vc["height"])
    count = [0]

    def hook(st, ret):
        if count[0] % every == 0:
            rec.frame(env.sim.d, st, overlay_lines(st, ret))
        count[0] += 1

    env.frame_hook = hook
    try:
        obs, _ = env.reset(seed=seed)
        while True:
            obs, _, term, trunc, info = env.step(act(obs))
            if term or trunc:
                return info["episode_stats"]
    finally:
        env.frame_hook = None
        rec.close()


def outcome(stats: dict) -> str:
    return {"success": "success", "fall": "fall", "box_lost": "box lost", "box_tipped": "box tipped",
            "timeout": "timeout"}.get(stats["reason"], str(stats["reason"]))


class VideoLog:
    """runs/<run_id>/videos/ and its index.md (one table row per video)."""

    HEADER = ("| video | training step | reason | controller | total reward | outcome | push share A / B | flags |\n"
              "|---|---|---|---|---|---|---|---|\n")

    def __init__(self, run_dir: str, video_cfg: Optional[dict] = None):
        self.dir = os.path.join(run_dir, "videos")
        os.makedirs(self.dir, exist_ok=True)
        self.index = os.path.join(self.dir, "index.md")
        self.video_cfg = video_cfg
        if not os.path.exists(self.index):
            with open(self.index, "w") as f:
                f.write(f"# Videos: {os.path.basename(os.path.normpath(run_dir))}\n\n" + self.HEADER)

    def record(self, env, act: Callable, training_step: int, reason: str, seed: Optional[int] = None,
               label: str = "") -> dict:
        if reason not in REASONS:
            raise ValueError(f"reason must be one of {REASONS}")
        name = f"step_{training_step}_{reason}" + (f"_{label}" if label else "") + ".mp4"
        stats = record_episode(env, act, os.path.join(self.dir, name), seed=seed, video_cfg=self.video_cfg)
        self.add_row(name, training_step, reason, label or "policy", stats)
        return stats

    def add_row(self, name: str, training_step: int, reason: str, controller: str, stats: dict) -> None:
        share = stats["push_share"]
        sh = " / ".join("-" if math.isnan(share[d]) else f"{100 * share[d]:.0f}%" for d in ("duck_a", "duck_b"))
        kinds = sorted({f.split(":")[0] for f in stats["flags"]})
        with open(self.index, "a") as f:
            f.write(f"| [{name}]({name}) | {training_step} | {reason} | {controller} | {stats['return']:+.2f} | "
                    f"{outcome(stats)} ({stats['steps']} steps) | {sh} | {', '.join(kinds) or 'none'} |\n")
