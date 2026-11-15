#!/usr/bin/env python3
"""curriculum_ladder.svg: the decentralized track's ladder, from exact partner info to realistic sensing (roadmap order)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram_kit import *  # noqa: E402,F403

W, H = 1210, 640
CW, CH, DX, DY = 166, 216, 196, 48


def chirp_duck(cx, cy):
    return duck(cx - 26, cy + 6, 0.62) + chirp_waves(cx + 6, cy - 6, 0.9)


def flipped(cx, cy):
    return (duck(cx - 28, cy + 6, 0.55) + chirp_waves(cx - 2, cy - 4, 0.75, PINK) +
            f'<path d="M{cx + 22},{cy - 18} L{cx + 36},{cy - 4} M{cx + 36},{cy - 18} L{cx + 22},{cy - 4}" stroke="{ORANGE}" stroke-width="3.5" stroke-linecap="round"/>')


def apart(cx, cy):
    return (duck(cx - 44, cy + 6, 0.55) + duck(cx + 44, cy + 6, 0.55, True) +
            arrow(cx - 28, cy + 8, cx + 28, cy + 8, PINK, 2.2, True, "arrowp"))


def seeing(cx, cy):
    return (eye_cone(cx - 6, cy + 2, 0.78) + duck(cx - 34, cy + 6, 0.6) + box(cx + 30, cy + 6, 0.55))


def teacher(cx, cy):
    return (gamepad(cx, cy - 26, 0.62) + arrow(cx, cy - 10, cx, cy + 4, PURPLE, 2.2, True) +
            gamepad(cx - 24, cy + 18, 0.4, True) + gamepad(cx + 24, cy + 18, 0.4, True))


steps = [
    ("Retrain with chirps", "in progress", chirp_duck),
    ("Missed and flipped chirps", "planned", flipped),
    ("Random box mass", "planned", lambda cx, cy: weight(cx - 22, cy, 1.1) + box(cx + 24, cy + 8, 0.7)),
    ("Ducks start apart", "planned", apart),
    ("Vision, box blocks the view", "planned", seeing),
    ("Distill the combined teacher", "planned", teacher),
]
body = []
for i, (name, status, art) in enumerate(steps):
    x, y = 30 + i * DX, 340 - i * DY
    cx = x + CW / 2
    active = status == "in progress"
    body.append(rect(x, y, CW, CH, CREAM, GREEN if active else AMBER, 16, 3 if active else 1.5))
    body.append(art(cx, y + 80))
    body.append(f'<circle cx="{x + 24}" cy="{y + 24}" r="15" fill="{PURPLE_D}"/>' + text(x + 24, y + 30, str(i + 1), 17, 700, "#FFFFFF"))
    words = name.split(" ")
    rows = [" ".join(words[:2]), " ".join(words[2:])] if len(words) > 2 and len(name) > 16 else [name]
    body.append(lines(cx, y + (138 if len(rows) == 2 else 150), rows, 18, 600, INK, 1.22))
    body.append(pill(cx, y + CH - 22, status, 14, "#DDF3EA" if active else CREAM, GREEN if active else AMBER, 10, 600, INK2))
    if i < len(steps) - 1:
        body.append(arrow(x + CW + 5, y + 60, x + DX - 5, y - DY + 80, PURPLE, 3))
body.append(pill(190, 604, "Start: D2 with exact partner info", 16, CREAM, AMBER, 16))
save("curriculum_ladder", W, H, "The decentralized ladder: retrain with chirps, missed and flipped chirps, random box mass, "
     "ducks start apart, vision with the box blocking the view, then distill the combined central teacher", body)
print("wrote curriculum_ladder.svg")
