#!/usr/bin/env python3
"""data_flow.svg: from settings to results: config -> training queue -> runs/ -> test set -> results and docs."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram_kit import *  # noqa: E402,F403

W, H = 1210, 330
CW, CH, GAP, Y0 = 190, 250, 48, 40


def queue(cx, cy):
    back = "".join(rect(cx - 40 + 9 * i, cy - 12 - 9 * i, 64, 32, "#FFFFFF", AMBER, 8, 1.5) for i in (2, 1))
    front = rect(cx - 40, cy - 12, 64, 32, "#FFFFFF", AMBER, 8, 1.5) + text(cx - 8, cy + 10, "run 1", 15, 600, INK2)
    return back + front + gear(cx + 40, cy + 14, 0.8)


items = [
    ("Config file", ["every setting"], lambda cx, cy: scroll(cx, cy, 1.25)),
    ("Training queue", ["one run after", "another"], queue),
    ("runs folder", ["checkpoints, videos,", "logs (not in git)"], lambda cx, cy: folder(cx, cy, 1.3)),
    ("Test set", ["50 starts it never", "trained on"], lambda cx, cy: exam(cx, cy, 1.25)),
    ("Results and docs", ["experiment folder,", "README, ROADMAP"], lambda cx, cy: bars(cx, cy, 1.3)),
]
body = []
for i, (name, sub, art) in enumerate(items):
    x = 30 + i * (CW + GAP)
    cx = x + CW / 2
    body += [card(x, Y0, CW, CH), art(cx, Y0 + 80), text(cx, Y0 + 166, name, 20, 700), lines(cx, Y0 + 196, sub, 15, 400, INK2, 1.3)]
    if i < len(items) - 1:
        body.append(arrow(x + CW + 4, Y0 + 80, x + CW + GAP - 4, Y0 + 80, PURPLE, 3.5))
save("data_flow", W, H, "Data flow: config file, training queue, runs folder, test set, then results and docs", body)
print("wrote data_flow.svg")
