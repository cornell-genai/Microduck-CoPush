"""Per-tick CSV logging, one row per duck per tick (long format).

Columns: t, duck, x, y, yaw, trunk_z, gravity_z, cmd_vx, cmd_vy, cmd_vyaw, phase
         + box_x, box_y, box_z, box_yaw when the run has a box.

`t` is simulator time in seconds since the episode started. `phase` is a free-form label set by
the controller (empty if it has none). Box columns repeat on both ducks' rows of a tick, so either
row can be read on its own.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from copush.state import DUCKS

BASE_COLUMNS = ["t", "duck", "x", "y", "yaw", "trunk_z", "gravity_z",
                "cmd_vx", "cmd_vy", "cmd_vyaw", "phase"]
BOX_COLUMNS = ["box_x", "box_y", "box_z", "box_yaw"]


class CsvRecorder:
    def __init__(self, path: Path, with_box: bool):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.with_box = with_box
        self.columns = BASE_COLUMNS + (BOX_COLUMNS if with_box else [])
        self._file = self.path.open("w", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=self.columns)
        self._writer.writeheader()

    def record(self, t: float, state: dict, actions: dict, phase: str = "") -> None:
        box: Optional[dict] = state.get("box")
        for duck in DUCKS:
            d = state[duck]
            cmd = actions[duck]
            row = {
                "t": f"{t:.3f}",
                "duck": duck,
                "x": f"{d['position'][0]:.5f}",
                "y": f"{d['position'][1]:.5f}",
                "yaw": f"{d['yaw']:.5f}",
                "trunk_z": f"{d['trunk_z']:.5f}",
                "gravity_z": f"{d['gravity'][2]:.5f}",
                "cmd_vx": f"{cmd[0]:.3f}",
                "cmd_vy": f"{cmd[1]:.3f}",
                "cmd_vyaw": f"{cmd[2]:.3f}",
                "phase": phase,
            }
            if self.with_box:
                if box is None:
                    row.update({c: "" for c in BOX_COLUMNS})
                else:
                    row.update({
                        "box_x": f"{box['position'][0]:.5f}",
                        "box_y": f"{box['position'][1]:.5f}",
                        "box_z": f"{box['z']:.5f}",
                        "box_yaw": f"{box['yaw']:.5f}",
                    })
            self._writer.writerow(row)

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "CsvRecorder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
