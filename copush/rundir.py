"""Everything one run writes, under runs/<timestamp>/ (gitignored):

    config.yaml   the resolved config (YAML + flags), reloadable with --config
    state.csv     copush.recorder format, one row per duck per 0.02 s control step, plus the columns
                  in EXTRA_COLUMNS: policy, contact by body part, fall, reward next to the true
                  outcome (box_to_target, yaw_error_deg, inside)
    events.log    resets, policy switches, falls, suspicious-reward flags, NOTE markers
    video.mp4     with --record
    notes.md      a template for writing down what happened; the outcome summary is filled in at
                  the end of the run
"""
from __future__ import annotations

import datetime as _dt
import math
import os
import shlex
import sys
from typing import Optional

from copush.config import dump_config
from copush.recorder import CsvRecorder
from copush.sim import GROUPS
from copush.upstream import ROOT

RUNS = os.path.join(ROOT, "runs")
DUCK_COLUMNS = ["policy", "fallen", "tilt_deg", "contact_impulse"] + [f"contact_{g}" for g in GROUPS]
COMMON_COLUMNS = ["episode", "reward", "cum_reward", "box_to_target", "yaw_error_deg", "inside"]
EXTRA_COLUMNS = COMMON_COLUMNS + DUCK_COLUMNS
_PENDING = "_(filled in when the run ends)_"

NOTES = """# Run {name}

- Command: `{cmd}`
- Ducks: A at ({a[x]}, {a[y]}, {a[yaw]} deg) on {a[policy]}, B at ({b[x]}, {b[y]}, {b[yaw]} deg) on {b[policy]}
- Box: ({box[x]}, {box[y]}, {box[yaw]} deg), {box[mass]} kg. Target: ({tg[x]}, {tg[y]}, {tg[yaw]} deg), {tg[size][0]} x {tg[size][1]} m
- Reward: `{reward}`. Files: config.yaml, state.csv, events.log{video}

## Outcome (automatic)

{pending}

## Observations (fill in)

**What did the ducks do?**


**Was it what you expected? If not, what was different?**


**Was the reward gamed?** Compare the `reward` / `cum_reward` columns in state.csv with
`box_to_target` and `inside`, and check the flags in events.log (contact_share, bad_part, spin,
reward_vs_dist, fall, edge). Did the reward go up without the box getting closer?


**Markers** (each N press is a `NOTE #k` line in events.log; say what you saw at each):

"""


class RunDir:
    def __init__(self, cfg: dict, reward_name: str = "progress", video: bool = False,
                 root: str = RUNS, name: Optional[str] = None):
        self.name = name or _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = os.path.join(root, self.name)
        n = 1
        while os.path.exists(self.path):          # two runs in the same second
            n += 1
            self.path = os.path.join(root, f"{self.name}-{n}")
        os.makedirs(self.path)
        dump_config(cfg, self.file("config.yaml"))
        self.csv = CsvRecorder(self.file("state.csv"), with_box=True, extra_columns=EXTRA_COLUMNS)
        self._events = open(self.file("events.log"), "w")
        self.markers = 0
        with open(self.file("notes.md"), "w") as f:
            f.write(NOTES.format(name=os.path.basename(self.path),
                                 cmd=" ".join(shlex.quote(a) for a in sys.argv),
                                 a=cfg["duck_a"], b=cfg["duck_b"], box=cfg["box"], tg=cfg["target"],
                                 reward=reward_name, video=", video.mp4" if video else "",
                                 pending=_PENDING))

    def file(self, name: str) -> str:
        return os.path.join(self.path, name)

    def log_step(self, state: dict, reward: float, cum_reward: float, episode: int, phase: str = "") -> None:
        extra = {"episode": episode, "reward": reward, "cum_reward": cum_reward,
                 "box_to_target": state["box_to_target"],
                 "yaw_error_deg": math.degrees(state["yaw_error"]), "inside": int(state["inside"])}
        for duck in ("duck_a", "duck_b"):
            c = state["contact"][duck]
            extra[duck] = {"policy": state[duck]["policy"], "fallen": int(state[duck]["fallen"]),
                           "tilt_deg": state[duck]["tilt_deg"], "contact_impulse": c["impulse"],
                           **{f"contact_{g}": c["by_part"].get(g, 0.0) for g in GROUPS}}
        actions = {d: state[d]["cmd"] for d in ("duck_a", "duck_b")}
        self.csv.record(state["t"], state, actions, phase, extra)

    def event(self, t: float, kind: str, msg: str) -> None:
        self._events.write(f"{_dt.datetime.now():%H:%M:%S} t={t:7.2f}  {kind:<10} {msg}\n")
        self._events.flush()

    def note_marker(self, t: float) -> int:
        self.markers += 1
        self.event(t, "NOTE", f"#{self.markers} (describe it under Markers in notes.md)")
        with open(self.file("notes.md"), "a") as f:
            f.write(f"- #{self.markers} (t={t:.2f} s): \n")
        return self.markers

    def close(self, summary_md: str) -> None:
        self.csv.close()
        self._events.close()
        p = self.file("notes.md")
        with open(p) as f:
            text = f.read()
        with open(p, "w") as f:
            f.write(text.replace(_PENDING, summary_md, 1))
