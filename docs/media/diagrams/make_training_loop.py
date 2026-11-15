#!/usr/bin/env python3
"""training_loop.svg: how the reward changes the network's weights. Four steps in a loop; step 3 forks into two
separate branches, a reward (good: points) and a penalty (bad: minus points), which both feed the PPO update."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram_kit import *  # noqa: E402,F403

W, H = 840, 710
CW, CH, BW = 320, 250, 150                       # big card, card height, branch card width
TOP, BOT = 40, 370                               # y of the two rows
A_X, B_X = 470, 640                              # the two branch cards share the bottom-right slot


def title(cx, y, rows, sub):
    top = y + 140 + (13 if len(rows) == 1 else 0)
    return lines(cx, top, rows, 21, 600, INK, 1.25) + lines(cx, y + 196 + (0 if len(sub) == 2 else 8), sub, 15, 400, INK2, 1.3)


def badge(x, y, n):
    return f'<circle cx="{x}" cy="{y}" r="15" fill="{PURPLE_D}"/>' + text(x, y + 6, str(n), 17, 700, "#FFFFFF")


def scene(cx, cy):
    return (floor(cx, cy + 6, 170, 66) + duck(cx - 34, cy - 4, 0.62) + duck(cx - 4, cy + 4, 0.62)
            + box(cx + 34, cy + 6, 0.9) + target(cx + 62, cy + 24, 1.0))


big = {
    1: (50, TOP, TRAINED, lambda cx, cy: gamepad(cx, cy, 1.35), ["The network picks", "speed and turn"], ["random weights at first,", "or a copy of a trained one"]),
    2: (470, TOP, WORLD, scene, ["The ducks try it", "in the simulator"], ["up to 100 steps", "per try"]),
    4: (50, BOT, TRAINED, lambda cx, cy: dial(cx - 26, cy, 1.25) + wrench(cx + 40, cy + 6, 1.1), ["PPO nudges the weights"], ["do more of what scored well"]),
}
body = []
for n, (x, y, role, art, rows, sub) in big.items():
    cx = x + CW / 2
    body += [card(x, y, CW, CH, role), art(cx, y + 76), title(cx, y, rows, sub), badge(x + 26, y + 26, n)]

# step 3: two separate branches
for x, name, good, pts, what, art in (
        (A_X, "Reward", True, "+10", "box in the target", lambda cx, y: target(cx, y + 112, 1.3) + box(cx, y + 99, 0.85)),
        (B_X, "Penalty", False, "−10", "a duck fell", lambda cx, y: duck_fallen(cx, y + 108, 0.85))):
    cx = x + BW / 2
    body += [card(x, BOT, BW, CH, WORLD), badge(x + 24, BOT + 24, 3), text(cx, BOT + 78, name, 21, 600, INK), art(cx, BOT + 18),
             score_pill(cx, BOT + 180, pts, good, 23), text(cx, BOT + 228, what, 15, 400, INK2, italic=True)]

# arrows around the loop
body += [arrow(50 + CW + 8, 165, 470 - 8, 165, PURPLE, 4),                          # 1 -> 2
         arrow(210, BOT - 8, 210, TOP + CH + 8, PURPLE, 4)]                          # 4 -> 1
fork_y0, fork_y1 = TOP + CH + 8, BOT - 8
for x0, x1 in ((600, A_X + BW / 2), (660, B_X + BW / 2)):                            # 2 -> the two branches
    mid = (fork_y0 + fork_y1) / 2
    body.append(curve(f"M{x0},{fork_y0} C{x0},{mid} {x1},{mid} {x1},{fork_y1}", PURPLE, 4))
body.append(arrow(A_X - 8, BOT + CH / 2, 50 + CW + 8, BOT + CH / 2, PURPLE, 4))      # reward -> 4
bx = B_X + BW / 2                                                                    # penalty -> 4, under the reward card
body.append(curve(f"M{bx},{BOT + CH + 4} C{bx},{BOT + CH + 70} 210,{BOT + CH + 70} 210,{BOT + CH + 8}", PURPLE, 4))
body.append(pill(370, (TOP + CH + BOT) / 2, "repeat, over and over", 18, CREAM, PURPLE_D, 18))
save("training_loop", W, H, "The training loop: the network picks speed and turn, the ducks try it in the simulator, "
     "the result is either a reward (plus 10 for the box in the target) or a penalty (minus 10 when a duck falls), "
     "and PPO nudges the weights; then it repeats", body)
print("wrote training_loop.svg")
