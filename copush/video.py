"""Offscreen mp4 of a CoPushSim run, with a text overlay (distance, inside, contacts, reward)."""
from __future__ import annotations

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
        try:
            self.font = ImageFont.load_default(size=18)
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
            y += 22
        self.writer.add_image(np.asarray(img))

    def close(self) -> None:
        self.writer.__exit__(None, None, None)
        self.renderer.close()
