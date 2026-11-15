#!/usr/bin/env python3
"""system_loop.svg: the README's "How it works" diagram, one row: what the ducks see -> coordinator (trained) ->
speed and turn -> frozen walking and pushing policies -> simulator -> a fork into two reward branches (points for
something good, a penalty for something bad) -> PPO update, with a curved arrow back to the coordinator.
Cards are colored by role: trained, frozen, simulator and reward."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram_kit import *  # noqa: E402,F403

W, H = 1324, 384
X0, Y0, CW, CH, GAP = 24, 74, 150, 224, 30
GAPS = [GAP, GAP, GAP, GAP, 52, 52]                    # wider gaps around the reward fork
CY = Y0 + 76                                           # center line of the illustrations
HALF = (CH - 12) / 2                                   # each reward branch is half a card tall


def label(cx, rows, tag):
    top = Y0 + 150 + (11 if len(rows) == 1 else 0)
    return lines(cx, top, rows, 18, 600, INK, 1.22) + text(cx, Y0 + 200, tag, 14, 400, INK2, italic=True)


def mini_scene(cx, cy):
    return (floor(cx, cy + 6, 124, 52) + duck(cx - 30, cy - 2, 0.42) + duck(cx - 10, cy + 4, 0.42)
            + box(cx + 20, cy + 6, 0.62) + target(cx + 40, cy + 22, 0.7))


# columns 0-4, then the two reward branches share column 5, then PPO update in column 6
cards = [
    (WORLD, ["What the", "ducks see"], "box, target, partner",
     lambda cx: duck(cx - 50, CY + 4, 0.55) + duck(cx - 26, CY + 8, 0.55) + box(cx + 8, CY + 16, 0.72) + target(cx + 46, CY + 26, 0.95)),
    (TRAINED, ["Coordinator"], "the part we train", lambda cx: gamepad(cx, CY, 1.12)),
    (TRAINED, ["Speed and turn"], "for each duck", lambda cx: forward_arrow(cx - 28, CY, 1.1) + turn_arrow(cx + 28, CY + 2, 1.1)),
    (FROZEN, ["Walking and", "pushing"], "frozen, pretrained",
     lambda cx: duck(cx - 4, CY - 2, 1.15) + snowflake(cx + 44, CY - 32, 1.2)),
    (WORLD, ["Simulator"], "MuJoCo physics", lambda cx: mini_scene(cx, CY + 4)),
    None,
    (TRAINED, ["PPO update"], "nudges the weights", lambda cx: dial(cx - 20, CY - 2, 1.0) + wrench(cx + 32, CY + 4, 0.95)),
]

body = []
xs = [X0 + sum(CW + g for g in GAPS[:i]) for i in range(len(cards))]
for x, c in zip(xs, cards):
    if c is None:
        continue
    role, rows, tag, art = c
    cx = x + CW / 2
    body += [card(x, Y0, CW, CH, role), art(cx), label(cx, rows, tag)]
for i in (0, 1, 2, 3):
    x = xs[i]
    body.append(arrow(x + CW + 4, CY, x + CW + GAPS[i] - 4, CY, PURPLE, 3))

# the fork: two separate branches
fx, cxf = xs[5], xs[5] + CW / 2
top_y, bot_y = Y0, Y0 + HALF + 12
branches = [
    (top_y, "Reward", True, "+10", "box in the target",
     lambda cx, y: target(cx - 34, y + 62, 0.8) + box(cx - 34, y + 55, 0.5)),
    (bot_y, "Penalty", False, "−10", "a duck fell",
     lambda cx, y: duck_fallen(cx - 34, y + 60, 0.55)),
]
for y, name, good, pts, what, art in branches:
    body += [card(fx, y, CW, HALF, WORLD), text(cxf, y + 28, name, 18, 600, INK), art(cxf, y),
             score_pill(cxf + 32, y + 58, pts, good, 19), text(cxf, y + 92, what, 14, 400, INK2, italic=True)]


def fork(x1, y1, x2, y2, color=PURPLE):
    mx = (x1 + x2) / 2
    return curve(f"M{x1:g},{y1:g} C{mx:g},{y1:g} {mx:g},{y2:g} {x2:g},{y2:g}", color, 3)


sim_r, ppo_l = xs[4] + CW + 4, xs[6] - 4
mid_top, mid_bot = top_y + HALF / 2, bot_y + HALF / 2
body += [fork(sim_r, CY, fx - 4, mid_top), fork(sim_r, CY, fx - 4, mid_bot),
         fork(fx + CW + 4, mid_top, ppo_l, CY), fork(fx + CW + 4, mid_bot, ppo_l, CY)]

# the way back: PPO update changes the coordinator's weights
cx7, cx2 = xs[6] + CW / 2, xs[1] + CW / 2
yb = Y0 + CH
body.append(curve(f"M{cx7:g},{yb + 3} C{cx7:g},{yb + 78} {cx2:g},{yb + 78} {cx2:g},{yb + 5}", PURPLE_D, 3.2, True))
body.append(pill((cx7 + cx2) / 2, yb + 62, "changes the weights", 17, CREAM, PURPLE_D, 16, 600, INK))

# legend
lx, ly = X0, 30
body.append(rect(lx, ly - 22, 548, 40, CREAM, AMBER, 20, 1.3))
for role, name, dx in ((TRAINED, "Trained", 18), (FROZEN, "Frozen (pretrained)", 132), (WORLD, "Simulator and reward", 330)):
    body.append(rect(lx + dx, ly - 10, 24, 20, role["fill"], role["stroke"], 6, 2))
    body.append(text(lx + dx + 34, ly + 6, name, 15, 600, INK, "start"))

save("system_loop", W, H, "How it works: what the ducks see goes to the coordinator network, which picks speed and turn; "
     "frozen walking and pushing policies move the ducks in the simulator; the simulator gives a reward (plus 10 for the "
     "box in the target) or a penalty (minus 10 when a duck falls); a PPO update then changes the coordinator's weights", body)
print("wrote system_loop.svg")
