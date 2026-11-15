#!/usr/bin/env python3
"""chirp_experiment.svg: what each duck knows about its partner, and when (D2 today vs chirps)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram_kit import *  # noqa: E402,F403

W, H = 960, 680
body = [card(30, 30, 430, 290), card(500, 30, 430, 290), card(30, 350, 900, 300)]
# top left: D2 today
body += [text(245, 70, "D2 today", 22, 700), duck(130, 190, 1.1), duck(360, 190, 1.1, True),
         arrow(176, 190, 316, 190, PINK, 3, False, "arrowp"), arrow(316, 190, 176, 190, PINK, 3, False, "arrowp"),
         lines(245, 245, ["exact position and heading,", "every 0.2 s"], 17, 600, INK, 1.3)]
# top right: with chirps
body += [text(715, 70, "With chirps (planned)", 22, 700), duck(580, 190, 1.1), duck(850, 190, 1.1, True),
         chirp_waves(612, 168, 1.5), pill(715, 120, "a chirp every ~2 s", 15),
         arrow(686, 196, 790, 196, PINK, 2.6, True, "arrowp"),
         lines(715, 245, ["a rough direction, about 30° off.", "The heading is not heard."], 17, 600, INK, 1.3)]
# bottom: the timeline
body += [text(480, 392, "What a duck knows over time", 22, 700)]
x0, k = 215, 95                                           # x of t = 0, pixels per second
lanes = [(450, "duck A", [0, 2, 4, 6]), (520, "duck B", [0, 1.3, 3.3, 5.3])]
for y, name, ts in lanes:
    body.append(duck(100, y + 2, 0.52))
    body.append(text(138, y + 7, name, 15, 600, INK2, "start"))
    for a, b in zip(ts, ts[1:] + [7.0]):
        body.append(rect(x0 + a * k + 20, y - 12, (b - a) * k - 24, 24, "#F6DCE5", PINK, 12, 1.5))
    for t in ts:
        body.append(chirp_waves(x0 + t * k - 4, y - 2, 0.7))
body.append(f'<line x1="{x0}" y1="568" x2="{x0 + 7 * k}" y2="568" stroke="{INK2}" stroke-width="2" stroke-linecap="round"/>')
for t in range(0, 8):
    body.append(f'<line x1="{x0 + t * k}" y1="562" x2="{x0 + t * k}" y2="574" stroke="{INK2}" stroke-width="2"/>' + text(x0 + t * k, 594, f"{t} s", 14, 400, INK2))
body.append(chirp_waves(738, 392, 0.9) + text(790, 397, "= a chirp", 15, 600, INK2, "start"))
body.append(lines(480, 622, ["each pink bar: the last chirp's direction, held until the next one (the two ducks chirp at different times)"], 15, 400, INK2))
save("chirp_experiment", W, H, "The chirp experiment: D2 knows its partner's exact position and heading every 0.2 s; "
     "with chirps a duck hears a rough direction every few seconds and holds it until the next chirp", body)
print("wrote chirp_experiment.svg")
