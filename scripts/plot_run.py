#!/usr/bin/env python3
"""Turn one run CSV into a figure: x-y paths, yaw over time, trunk height over time.

    uv run python scripts/plot_run.py data/runs/<timestamp>.csv          # -> data/plots/<timestamp>.png
    uv run python scripts/plot_run.py data/sample/mock_run.csv --out /tmp/mock.png
    uv run python scripts/plot_run.py --latest                            # newest run in data/runs/

Phases (from the CSV's `phase` column) are shaded on the time plots. The box path, when present,
is drawn dashed and labelled. The trunk-height plot shows the fall threshold from copush.metrics.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from copush.metrics import TRUNK_Z_MIN, load_run  # noqa: E402
from copush.state import wrap_angle  # noqa: E402

# Categorical slots 1-3 of the reference palette, fixed order (validated: CVD dE >= 9.2).
COLORS = {"duck_a": "#2a78d6", "duck_b": "#eb6834", "box": "#1baf7a"}
LABELS = {"duck_a": "duck A", "duck_b": "duck B", "box": "box"}
INK, INK_2, GRID, SURFACE = "#1f1f1e", "#5f5e58", "#e6e5e0", "#fcfcfb"
PHASE_FILL = ("#f1f0ec", "#fcfcfb")


def unwrap_deg(yaws):
    out, total = [], 0.0
    for i, y in enumerate(yaws):
        if i:
            total += wrap_angle(y - yaws[i - 1])
        out.append(math.degrees(yaws[0] + total))
    return out


def phase_spans(t, phases):
    spans, start = [], 0
    for i in range(1, len(t) + 1):
        if i == len(t) or phases[i] != phases[start]:
            end = t[i] if i < len(t) else t[-1]
            spans.append((phases[start], t[start], end))
            start = i
    return [s for s in spans if s[0]]


def style(ax, title):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="bold", pad=18)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_2)
    ax.tick_params(colors=INK_2, labelsize=9)


def shade_phases(ax, spans):
    for k, (name, t0, t1) in enumerate(spans):
        ax.axvspan(t0, t1, color=PHASE_FILL[k % 2], zorder=0, linewidth=0)
        ax.text((t0 + t1) / 2, 1.0, name, transform=ax.get_xaxis_transform(), ha="center",
                va="bottom", fontsize=8, color=INK_2)


def plot(csv_path: Path, out: Path) -> Path:
    run = load_run(csv_path)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), gridspec_kw={"width_ratios": [1.15, 1, 1]})
    fig.patch.set_facecolor(SURFACE)
    ax_xy, ax_yaw, ax_z = axes

    # x-y paths
    style(ax_xy, "Top-down paths (world frame)")
    for key, s in run.ducks.items():
        c = COLORS.get(key, INK)
        ax_xy.plot(s.x, s.y, color=c, linewidth=2, label=LABELS.get(key, key), solid_capstyle="round")
        ax_xy.plot(s.x[0], s.y[0], "o", color=c, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
        ax_xy.plot(s.x[-1], s.y[-1], "s", color=c, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
        # heading arrow at the end
        L = 0.08
        ax_xy.annotate("", xy=(s.x[-1] + L * math.cos(s.yaw[-1]), s.y[-1] + L * math.sin(s.yaw[-1])),
                       xytext=(s.x[-1], s.y[-1]), arrowprops=dict(arrowstyle="->", color=c, lw=1.5))
        ax_xy.annotate(LABELS.get(key, key), (s.x[0], s.y[0]), textcoords="offset points",
                       xytext=(-8, 10), ha="right", fontsize=9, color=INK)
    if run.box is not None:
        b = run.box
        c = COLORS["box"]
        ax_xy.plot(b.x, b.y, color=c, linewidth=2, linestyle=(0, (4, 2)), label="box")
        ax_xy.plot(b.x[0], b.y[0], "D", color=c, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
        ax_xy.annotate("box", (b.x[0], b.y[0]), textcoords="offset points", xytext=(8, -14), fontsize=9, color=INK)
    ax_xy.set_aspect("equal", adjustable="datalim")
    ax_xy.set_xlabel("x (m)", color=INK_2)
    ax_xy.set_ylabel("y (m)", color=INK_2)
    ax_xy.margins(0.15)
    ax_xy.plot([], [], "o", color=INK_2, label="start")
    ax_xy.plot([], [], "s", color=INK_2, label="end")
    ax_xy.legend(loc="best", fontsize=8, frameon=False)

    any_series = next(iter(run.ducks.values()))
    spans = phase_spans(any_series.t, any_series.phase)

    # yaw over time
    style(ax_yaw, "Yaw over time (unwrapped)")
    shade_phases(ax_yaw, spans)
    for key, s in run.ducks.items():
        yaw = unwrap_deg(s.yaw)
        ax_yaw.plot(s.t, yaw, color=COLORS.get(key, INK), linewidth=2, label=LABELS.get(key, key))
        ax_yaw.annotate(f"{LABELS.get(key, key)} {yaw[-1] - yaw[0]:+.0f}°", (s.t[-1], yaw[-1]),
                        textcoords="offset points", xytext=(4, 0), va="center", fontsize=9, color=INK)
    ax_yaw.set_xlabel("time (s)", color=INK_2)
    ax_yaw.set_ylabel("yaw (deg)", color=INK_2)
    ax_yaw.legend(loc="upper left", fontsize=8, frameon=False)

    # trunk height over time
    style(ax_z, "Trunk height over time")
    shade_phases(ax_z, spans)
    for key, s in run.ducks.items():
        ax_z.plot(s.t, s.trunk_z, color=COLORS.get(key, INK), linewidth=2, label=LABELS.get(key, key))
    ax_z.axhline(TRUNK_Z_MIN, color=INK_2, linewidth=1, linestyle=(0, (3, 3)))
    ax_z.annotate(f"fall threshold {TRUNK_Z_MIN} m", (0, TRUNK_Z_MIN), xycoords=("axes fraction", "data"),
                  textcoords="offset points", xytext=(4, 4), fontsize=8, color=INK_2)
    lo = min(min(s.trunk_z) for s in run.ducks.values())
    hi = max(max(s.trunk_z) for s in run.ducks.values())
    ax_z.set_ylim(min(lo, TRUNK_Z_MIN) - 0.01, hi + 0.01)
    ax_z.set_xlabel("time (s)", color=INK_2)
    ax_z.set_ylabel("trunk z (m)", color=INK_2)
    ax_z.legend(loc="lower left", fontsize=8, frameon=False)

    fig.suptitle(csv_path.name, x=0.01, ha="left", fontsize=10, color=INK_2)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    plt.close(fig)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("csv", nargs="?", type=Path)
    parser.add_argument("--latest", action="store_true", help="plot the newest CSV in data/runs/")
    parser.add_argument("--out", type=Path, help="PNG path (default data/plots/<csv name>.png)")
    args = parser.parse_args()
    if args.latest:
        runs = sorted((ROOT / "data" / "runs").glob("*.csv"), key=lambda p: p.stat().st_mtime)
        if not runs:
            parser.error("no CSVs in data/runs/")
        args.csv = runs[-1]
    if args.csv is None:
        parser.error("give a CSV path or --latest")
    out = args.out or ROOT / "data" / "plots" / f"{args.csv.stem}.png"
    print(plot(args.csv, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
