#!/usr/bin/env python3
"""seed_comparison.svg: test-set success of every training run, one dot per run, in three columns (central from
scratch, D2 from scratch, D2 distilled) with a short line at each mean. Reads the numbers from
experiments/d2-from-scratch-comparison/comparison/summary.json, so rebuild it after new seeds finish:

    python3 docs/media/diagrams/make_seed_comparison.py

Same look as the other diagrams (cream card, amber border, soft flat colors, big plain labels, all text on the
card so it reads on light and dark pages). The palette below matches the other diagrams' diagram_kit.py.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SUMMARY = os.path.join(ROOT, "experiments", "d2-from-scratch-comparison", "comparison", "summary.json")

CREAM, AMBER, INK, INK2 = "#FFF8EC", "#BA7517", "#412402", "#633806"
FONT = 'font-family="Helvetica, Arial, sans-serif"'
COLUMNS = [  # summary.json key, label, dot fill, dot outline
    ("central-scratch", "Central from scratch", "#8DBBEE", "#185FA5"),
    ("d2-scratch", "D2 from scratch", "#F2A68B", "#993C1D"),
    ("d2-distilled", "D2 distilled", "#BDB8F2", "#534AB7"),
]

W, H = 780, 610
PLOT_L, PLOT_R, PLOT_T, PLOT_B = 118, 740, 118, 424          # the 0 to 100% plot area
R = 8                                                         # dot radius


def y_of(pct: float) -> float:
    return PLOT_B - (PLOT_B - PLOT_T) * pct / 100.0


def text(x, y, s, size=17, weight=600, fill=INK, anchor="middle"):
    return f'<text x="{x:g}" y="{y:g}" text-anchor="{anchor}" {FONT} font-size="{size:g}" font-weight="{weight}" fill="{fill}">{s}</text>'


def swarm(pcts, cx):
    """Dots at their success level, nudged sideways just enough that none overlap."""
    placed = []
    for p in sorted(pcts):
        y = y_of(p)
        for k in range(0, 40):
            dx = ((k + 1) // 2) * (2 * R + 3) * (1 if k % 2 else -1) if k else 0
            if all(math.hypot(cx + dx - ox, y - oy) >= 2 * R + 2 for ox, oy in placed):
                placed.append((cx + dx, y))
                break
    return placed


summary = json.load(open(SUMMARY))
body = [f'<rect x="20" y="20" width="{W - 40}" height="{H - 40}" rx="16" fill="{CREAM}" stroke="{AMBER}" stroke-width="1.5"/>',
        text(W / 2, 66, "Success on 50 new starts, one dot per training run", 21, 700)]

# y axis: 0 to 100 %
for pct in range(0, 101, 20):
    y = y_of(pct)
    body.append(f'<line x1="{PLOT_L}" y1="{y:g}" x2="{PLOT_R}" y2="{y:g}" stroke="#E8D5B0" stroke-width="{2 if pct == 0 else 1.2}"/>')
    body.append(text(PLOT_L - 12, y + 5, f"{pct}%", 15, 400, INK2, "end"))

n_cols = len(COLUMNS)
for i, (key, label, fill, edge) in enumerate(COLUMNS):
    cx = PLOT_L + (PLOT_R - PLOT_L) * (i + 0.5) / n_cols - 10
    seeds = summary[key]["seeds"]
    pcts = [100 * s["test"]["success"] for s in seeds.values() if "test" in s]
    mean = sum(pcts) / len(pcts)
    for x, y in swarm(pcts, cx):
        body.append(f'<circle cx="{x:g}" cy="{y:g}" r="{R}" fill="{fill}" fill-opacity="0.9" stroke="{edge}" stroke-width="2"/>')
    ym = y_of(mean)
    body.append(f'<line x1="{cx - 56:g}" y1="{ym:g}" x2="{cx + 56:g}" y2="{ym:g}" stroke="{INK}" stroke-width="3.5" stroke-linecap="round"/>')
    body.append(text(cx + 64, ym + 6, f"{mean:.0f}%", 19, 700, INK, "start"))
    body.append(text(cx, 456, label, 18, 700))
    body.append(text(cx, 480, f"{len(pcts)} seeds", 15, 400, INK2))

body.append(text(W / 2, 534, "Dots overlap: no measurable difference between one brain and two.", 17, 600, INK))
body.append(text(W / 2, 560, "Distilled had 1.38M steps of prior training.", 16, 400, INK2))

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img">'
       "<title>Test-set success of each training run: central from scratch, decentralized (D2) from scratch and D2 distilled, "
       "one dot per run, with the mean marked. The dots overlap, so no measurable difference between one brain and two.</title>\n"
       + "\n".join(body) + "\n</svg>\n")
out = os.path.join(HERE, "seed_comparison.svg")
open(out, "w").write(svg)
print("wrote", out)
