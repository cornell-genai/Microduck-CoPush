"""Reward functions, and a monitor that flags behaviour that looks like reward hacking.

A reward function is any callable `(prev_state, state) -> float`, called once per control step
with two consecutive `CoPushSim.get_state()` dicts (prev_state is None on the first step after a
reset). Plug one in by name (`REWARDS`, `--reward` in scripts/copush_sim.py) or pass your own:

    monitor = RewardMonitor(my_reward)
    reward, flags = monitor.update(state)       # every control step

The run logger writes the reward next to the true outcome (box_to_target, yaw_error, inside) in
state.csv, so a rising reward can be checked against what the box really did. The monitor's
`flags` are short strings that go to events.log, each logged when its condition starts (rising
edge) so a long-lasting condition is one line, not thousands:

    contact_share   one duck has > 80% of the box contact impulse over the window
    bad_part        a duck touches the box more with trunk/head than with hips
    spin            box rotates > 15 deg over the window but its centre moves < 3 cm
    reward_vs_dist  reward summed over the window is > 0.05 while box_to_target did not fall
    fall            a duck fell
    edge            box crossed the target boundary >= 3 times within the window
"""
from __future__ import annotations

import math
from collections import deque
from typing import Callable, Dict, List, Optional, Tuple

RewardFn = Callable[[Optional[dict], dict], float]


def progress_reward(prev: Optional[dict], state: dict) -> float:
    """Example: 10 x (metres of box progress toward the target this step) + 0.02 per step
    inside the target - 1 when a duck newly falls. Deliberately simple (and gameable)."""
    if prev is None:
        return 0.0
    r = 10.0 * (prev["box_to_target"] - state["box_to_target"])
    if state["inside"]:
        r += 0.02
    for duck, fell in state["fallen"].items():
        if fell and not prev["fallen"][duck]:
            r -= 1.0
    return r


REWARDS: Dict[str, RewardFn] = {"progress": progress_reward}

WINDOW_S = 2.0           # sliding window the flags look at
MIN_IMPULSE = 0.5        # N*s of box contact in the window before contact flags are judged (a steady push is ~2-3)
SHARE = 0.80
SPIN_DEG, SPIN_MOVE = 15.0, 0.03
REWARD_RISE, DIST_EPS = 0.05, 0.005
EDGE_CROSSINGS = 3
REARM_S = 1.0            # a flag must be clear this long before it is logged again


class RewardMonitor:
    def __init__(self, reward_fn: RewardFn = progress_reward, window_s: float = WINDOW_S):
        self.reward_fn, self.window_s = reward_fn, window_s
        self.reset()

    def reset(self) -> None:
        self.prev: Optional[dict] = None
        self.cum = 0.0
        self.hist: deque = deque()
        self.active: Dict[str, float] = {}

    def update(self, state: dict) -> Tuple[float, List[str]]:
        r = float(self.reward_fn(self.prev, state))
        self.cum += r
        contact = {d: dict(c["by_part"]) for d, c in state["contact"].items()}
        self.hist.append((state["t"], r, state["box_to_target"], state["box"]["position"],
                          state["box"]["yaw"], state["inside"], contact))
        while self.hist and self.hist[0][0] < state["t"] - self.window_s:
            self.hist.popleft()
        flags = []
        t = state["t"]
        for key, msg in self._conditions(state):
            # self.active[key] = last time the condition held; a flag re-arms after REARM_S clear,
            # so a value hovering at a threshold does not log every other step
            if msg:
                if t - self.active.get(key, -math.inf) > REARM_S:
                    flags.append(f"{key}: {msg}")
                self.active[key] = t
        self.prev = state
        return r, flags

    def _conditions(self, state):
        h = self.hist
        full = h[-1][0] - h[0][0] >= self.window_s - 0.05
        out = []

        # contact: one duck dominating, and which body part
        imp = {d: {} for d in state["contact"]}
        for row in h:
            for d, parts in row[6].items():
                for p, v in parts.items():
                    imp[d][p] = imp[d].get(p, 0.0) + v
        tot = {d: sum(p.values()) for d, p in imp.items()}
        both = sum(tot.values())
        msg = ""
        if both > MIN_IMPULSE:
            for d, v in tot.items():
                if v / both > SHARE:
                    msg = f"{d} has {100 * v / both:.0f}% of box contact over {self.window_s:.0f} s"
        out.append(("contact_share", msg))
        for d, parts in imp.items():
            msg = ""
            if tot[d] > MIN_IMPULSE:
                th = parts.get("trunk", 0.0) + parts.get("head", 0.0)
                if th > parts.get("hips", 0.0):
                    msg = (f"{d} pushes with trunk/head ({100 * th / tot[d]:.0f}%) more than hips "
                           f"({100 * parts.get('hips', 0.0) / tot[d]:.0f}%)")
            out.append((f"bad_part_{d}", msg))

        # box rotating in place
        msg = ""
        if full:
            dyaw = 0.0
            for a, b in zip(h, list(h)[1:]):
                dyaw += math.atan2(math.sin(b[4] - a[4]), math.cos(b[4] - a[4]))
            move = math.dist(h[0][3], h[-1][3])
            if abs(math.degrees(dyaw)) > SPIN_DEG and move < SPIN_MOVE:
                msg = f"box turned {math.degrees(dyaw):+.0f} deg but moved {100 * move:.1f} cm"
        out.append(("spin", msg))

        # reward going up while the true distance does not go down
        msg = ""
        if full:
            rsum = sum(row[1] for row in h)
            ddist = h[-1][2] - h[0][2]
            if rsum > REWARD_RISE and ddist > -DIST_EPS:
                msg = f"reward +{rsum:.2f} over {self.window_s:.0f} s while box_to_target changed {100 * ddist:+.1f} cm"
        out.append(("reward_vs_dist", msg))

        for d, fell in state["fallen"].items():
            out.append((f"fall_{d}", f"{d} fell" if fell else ""))

        # in/out of the target several times
        crossings = sum(1 for a, b in zip(h, list(h)[1:]) if a[5] != b[5])
        out.append(("edge", f"box crossed the target edge {crossings}x in {self.window_s:.0f} s"
                    if crossings >= EDGE_CROSSINGS else ""))
        return out
