#!/usr/bin/env python3
"""Figures for docs/results/b0_single_duck_push.md. Deterministic.

Reads docs/results/data/*.json (written by eval_push.py, steering.py, heading_hold.py) and re-runs
the cheap rollouts it needs (trajectories, the no-box speed sweep). Writes docs/results/figures/.

    uv run --project ../microduck_rl python scripts/b0/make_plots.py        # all figures, both robots
"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np

import b0lib as L

RES = os.path.join(L.ROOT, "docs/results")
DATA = os.path.join(RES, "data")
FIG = os.path.join(RES, "figures")
os.makedirs(FIG, exist_ok=True)
ROBOTS = ("backlash", "nobacklash")
ROBOT_LABEL = {"backlash": "backlash robot", "nobacklash": "no-backlash robot"}

# ---- reference palette (light), validated: slots 1-3 all-pairs, 1-5 adjacent ----
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0"
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
NEUTRAL = "#c9c8c2"
ROLE = {"shoe push": BLUE, "velstand v6": ORANGE, "velstand v8": AQUA}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.axisbelow": True,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "legend.frameon": False, "lines.linewidth": 2,
})

CARD = {  # model card, 512 robots, 10 s, 0.2 m/s
    "forward": {"before": 0.22, "after": 0.96, "head_mean": 19},
    "backward": {"before": 0.00, "after": 0.99, "head_mean": -23},
}
# duck-sim (robotd + velstand v8, scene_backlash, position actuators), from rest, 8 s runs,
# scripts/b0/duck_sim_drive.py on 2026-11-02: commanded vx -> achieved along-heading speeds.
DUCK_SIM_V8 = {-0.3: [-0.078, -0.083, -0.080], -0.25: [0.0, 0.0, 0.0], -0.2: [0.0, 0.0, 0.0, 0.0],
               -0.1: [0.0], 0.1: [0.0], 0.15: [0.068, 0.069], 0.2: [0.090, 0.091, 0.090], 0.3: [0.116]}


def save(fig, name):
    p = os.path.join(FIG, name)
    fig.savefig(p, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.relpath(p, L.ROOT))


def load(name):
    return json.load(open(os.path.join(DATA, name)))


# ============================================================ per-robot B0 figures
def b0_figures(robot):
    res = load(f"b0_eval_{robot}.json")
    by = {(r["direction"], r["policy"]): r for r in res["results"]}
    sfx = f"_{robot}"

    # ---- box travel
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), sharex=True)
    for ax, d in zip(axes, ("forward", "backward")):
        rows = [("shoe push", d), ("velstand v6", "velstand v6"), ("velstand v8", "velstand v8")]
        for yi, (role, key) in enumerate(rows):
            v = np.array([x["box_travel"] for x in by[(d, key)]["trials"]])
            jitter = (np.random.default_rng(yi).random(len(v)) - 0.5) * 0.28
            ax.scatter(v, yi + jitter, s=34, color=ROLE[role], alpha=0.75, edgecolor=SURFACE, linewidth=1, zorder=3)
            ax.plot([v.mean()] * 2, [yi - 0.3, yi + 0.3], color=ROLE[role], lw=3, solid_capstyle="round", zorder=4)
            ax.annotate(f"mean {v.mean():.2f} m", (v.mean() + 0.02, yi + 0.3), ha="left", va="center", fontsize=8.5, color=INK)
        for yi, k in ((0, "after"), (1, "before")):
            ax.scatter([CARD[d][k]], [yi], marker="D", s=70, facecolor="none", edgecolor=INK, linewidth=1.5, zorder=5)
            ax.annotate(f"card {CARD[d][k]:.2f}", (CARD[d][k], yi - 0.36), ha="center", va="top", fontsize=8.5, color=INK2)
        ax.axvline(0, color=MUTED, lw=1)
        ax.set_yticks(range(3), [f"shoe push\n({d})", "velstand v6", "velstand v8"])
        ax.set_ylim(2.7, -0.75)
        ax.set_xlim(-0.25, 1.1)
        ax.set_xlabel("box travel along push direction in 10 s (m)")
        ax.set_title(f"{d.capitalize()} scene, {ROBOT_LABEL[robot]}", loc="left")
        ax.grid(axis="y", visible=False)
    axes[1].legend(handles=[
        Line2D([], [], marker="o", ls="", color=MUTED, markersize=6, label="one trial"),
        Line2D([], [], color=MUTED, lw=3, label="mean of 10"),
        Line2D([], [], marker="D", ls="", markerfacecolor="none", markeredgecolor=INK, markersize=7, label="model card"),
    ], loc="lower right", fontsize=8.5)
    save(fig, f"box_travel{sfx}.png")

    # ---- trajectories + heading (re-run with traces; deterministic, same boxes as the eval)
    traces = {}
    for d, sign in (("forward", +1), ("backward", -1)):
        for role, key in (("shoe push", d), ("velstand v6", "velstand v6")):
            r = L.Rollout(L.scene(d, robot), L.POLICY[key])
            traces[(d, role)] = []
            for t in by[(d, key)]["trials"]:
                tr = []
                r.run(sign * 0.2, 10.0, sign, sign * L.BOX_OFFSET, t["box_mass"],
                      math.pi / 2 + math.radians(t["box_yaw_deg"]), trace=tr)
                traces[(d, role)].append(np.array(tr))

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
    for ax, d in zip(axes, ("forward", "backward")):
        bx = L.BOX_OFFSET if d == "forward" else -L.BOX_OFFSET
        ax.add_patch(Rectangle((bx - 0.05, -0.14), 0.10, 0.28, facecolor=NEUTRAL, edgecolor="none", alpha=0.6, zorder=1))
        ax.annotate("box start\n(yaw 0)", (bx, -0.16), ha="center", va="top", fontsize=8, color=INK2)
        for tr in traces[(d, "velstand v6")]:
            ax.plot(tr[:, 1], tr[:, 2], color=ORANGE, lw=1.6, alpha=0.8, zorder=3)
        for tr in traces[(d, "shoe push")]:
            ax.plot(tr[:, 1], tr[:, 2], color=BLUE, lw=1.4, alpha=0.7, zorder=3)
            ax.plot(tr[:, 3], tr[:, 4], color=INK2, lw=1.1, ls=(0, (3, 2)), alpha=0.7, zorder=2)
            ax.scatter(tr[-1, 3], tr[-1, 4], s=16, color=INK2, zorder=4)
        ax.scatter([0], [0], marker="o", s=60, facecolor=SURFACE, edgecolor=INK, zorder=5)
        ax.annotate("robot start", (0, -0.05), ha="center", va="top", fontsize=8, color=INK2)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_xlabel("world x (m)  (robot faces +x at start)")
        ax.set_ylabel("world y (m)")
        ax.set_title(f"{d.capitalize()} policy paths, {ROBOT_LABEL[robot]}", loc="left")
    axes[0].legend(handles=[
        Line2D([], [], color=BLUE, lw=2, label="shoe push trunk"),
        Line2D([], [], color=INK2, lw=1.4, ls=(0, (3, 2)), label="box centre (shoe push)"),
        Line2D([], [], color=ORANGE, lw=2, label="velstand v6 trunk"),
    ], loc="upper left", fontsize=8.5)
    save(fig, f"trajectories{sfx}.png")

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, d in zip(axes, ("forward", "backward")):
        ax.axhline(0, color=MUTED, lw=1)
        for role in ("velstand v6", "shoe push"):
            trs = traces[(d, role)]
            hs = [np.degrees(np.unwrap(np.radians(tr[:, 5]))) for tr in trs]
            for tr, h in zip(trs, hs):
                ax.plot(tr[:, 0], h, color=ROLE[role], lw=1, alpha=0.35)
            T = min(len(h) for h in hs)
            mean = np.mean([h[:T] for h in hs], axis=0)
            ax.plot(trs[0][:T, 0], mean, color=ROLE[role], lw=2.5)
            ax.annotate(f"{role} mean {mean[-1]:+.0f}°", (10.15, mean[-1]), va="center", fontsize=8.5, color=INK,
                        annotation_clip=False)
        cm = CARD[d]["head_mean"]
        ax.scatter([10], [cm], marker="D", s=60, facecolor=SURFACE, edgecolor=INK, linewidth=1.5, zorder=5, clip_on=False)
        ax.annotate(f"card mean {cm:+d}°", (9.7, cm), ha="right", va="center", fontsize=8.5, color=INK2,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor=SURFACE, edgecolor="none"), zorder=6)
        ax.set_xlim(0, 10)
        ax.set_xlabel("time (s)")
        ax.set_title(f"{d.capitalize()} scene, {ROBOT_LABEL[robot]}", loc="left")
    axes[0].set_ylabel("heading change (deg, + = left)")
    fig.subplots_adjust(wspace=0.5)
    save(fig, f"heading_drift{sfx}.png")

    # ---- contact share
    groups = [("hips", BLUE), ("trunk", ORANGE), ("feet", AQUA), ("head", YELLOW), ("thighs", MAGENTA), ("other", NEUTRAL)]

    def ours(d, key):
        s = dict(by[(d, key)]["summary"]["contact_share"])
        return {g: 100 * s.get(g, 0.0) for g, _ in groups}

    def card(dd):
        dd = dict(dd); dd["other"] = 100 - sum(dd.values()); return dd
    bars = {
        "forward": [("card: velstand", card({"feet": 71, "hips": 20, "head": 9})), ("ours: velstand v6", ours("forward", "velstand v6")),
                    ("card: shoe push", card({"hips": 88, "feet": 12})), ("ours: shoe push", ours("forward", "forward"))],
        "backward": [("card: velstand", card({"trunk": 70, "feet": 27})), ("ours: velstand v6", ours("backward", "velstand v6")),
                     ("card: shoe push", card({"trunk": 92, "feet": 6})), ("ours: shoe push", ours("backward", "backward"))],
    }
    fig, axes = plt.subplots(2, 1, figsize=(9, 4.8), sharex=True)
    for ax, d in zip(axes, ("forward", "backward")):
        for yi, (lbl, dd) in enumerate(bars[d]):
            left = 0
            for g, col in groups:
                w = dd.get(g, 0)
                if w <= 0.05:
                    continue
                ax.barh(yi, w, left=left, height=0.62, color=col, edgecolor=SURFACE, linewidth=2)
                if w >= 8:
                    ax.text(left + w / 2, yi, f"{g} {w:.0f}%", ha="center", va="center", fontsize=8, color=INK)
                left += w
        ax.set_yticks(range(4), [b[0] for b in bars[d]])
        ax.set_ylim(3.5, -0.5)
        ax.set_xlim(0, 100)
        ax.grid(axis="y", visible=False)
        ax.set_title(f"{d.capitalize()}: share of robot→box contact force ({ROBOT_LABEL[robot]})", loc="left")
    axes[1].set_xlabel("% of contact impulse")
    axes[0].legend(handles=[Rectangle((0, 0), 1, 1, color=c, label=g) for g, c in groups],
                   loc="upper center", bbox_to_anchor=(0.5, 1.42), ncol=6, fontsize=8.5)
    save(fig, f"contact_share{sfx}.png")

    # ---- mass vs travel
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), sharey=True)
    for ax, d in zip(axes, ("forward", "backward")):
        for role, key in (("shoe push", d), ("velstand v6", "velstand v6")):
            t = by[(d, key)]["trials"]
            m = np.array([x["box_mass"] for x in t]); v = np.array([x["box_travel"] for x in t])
            ax.scatter(m, v, s=48, color=ROLE[role], edgecolor=SURFACE, linewidth=1.5, zorder=3)
            rr = np.corrcoef(m, v)[0, 1]
            ax.annotate(f"{role}: r = {rr:+.2f}", (0.305, v.mean()), fontsize=8.5, va="center", color=INK, annotation_clip=False)
        ax.axhline(0, color=MUTED, lw=1)
        ax.set_xlim(0.04, 0.31)
        ax.set_xlabel("box mass (kg)")
        ax.set_title(f"{d.capitalize()} scene, {ROBOT_LABEL[robot]}", loc="left")
    axes[0].set_ylabel("box travel in 10 s (m)")
    fig.subplots_adjust(wspace=0.5)
    save(fig, f"mass_vs_travel{sfx}.png")


# ============================================================ start threshold (both robots)
def start_threshold():
    speeds = np.round(np.arange(-0.30, 0.301, 0.05), 2)
    sweep = {}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, robot in zip(axes, ROBOTS):
        sweep[robot] = {}
        for role in ("velstand v6", "velstand v8"):
            r = L.Rollout(L.scene(None, robot), L.POLICY[role])
            sweep[robot][role] = [r.run(float(v), 10.0, +1)["robot_dxy"][0] / 10 if v != 0 else 0.0 for v in speeds]
        rf = L.Rollout(L.scene(None, robot), L.POLICY["forward"])
        rb = L.Rollout(L.scene(None, robot), L.POLICY["backward"])
        vals, fell = [], []
        for v in speeds:
            if v == 0:
                vals.append(0.0); fell.append(False); continue
            o = (rf if v > 0 else rb).run(float(v), 10.0, +1)
            vals.append(o["robot_dxy"][0] / (o["fall_t"] or 10.0)); fell.append(o["fell"])
        sweep[robot]["shoe push"] = vals
        sweep[robot]["shoe push fell"] = fell

        ax.plot(speeds, speeds, color=MUTED, lw=1.2, ls=(0, (4, 3)))
        ax.annotate("achieved = commanded", (0.12, 0.2), fontsize=8.5, color=INK2)
        ax.axhline(0, color=MUTED, lw=1)
        for role in ("shoe push", "velstand v8", "velstand v6"):
            ax.plot(speeds, sweep[robot][role], color=ROLE[role], marker="o", markersize=6.5,
                    markeredgecolor=SURFACE, markeredgewidth=1.5, lw=2, label=role if role != "shoe push" else "shoe push (fwd policy >0, bwd <0)")
        fx = [s for s, f in zip(speeds, fell) if f]
        fy = [v for v, f in zip(vals, fell) if f]
        if fx:
            ax.scatter(fx, fy, marker="x", s=70, color=INK, zorder=6, label="shoe push fell (speed until fall)")
        if robot == "backlash":
            xs = sorted(DUCK_SIM_V8)
            ax.scatter(xs, [np.mean(DUCK_SIM_V8[x]) for x in xs], marker="D", s=60, facecolor="none",
                       edgecolor=INK, linewidth=1.5, zorder=7, label="duck-sim robotd + velstand v8")
        ax.set_xlabel("commanded lin_vel_x (m/s), from standstill, no box")
        ax.set_title(ROBOT_LABEL[robot].capitalize(), loc="left")
        ax.set_ylim(-0.3, 0.3)
    axes[0].set_ylabel("achieved speed along x (m/s, 10 s)")
    axes[0].legend(loc="upper left", fontsize=8)
    save(fig, "start_threshold.png")
    json.dump({"speeds": speeds.tolist(), "sweep": sweep, "duck_sim_v8": {str(k): v for k, v in DUCK_SIM_V8.items()}},
              open(os.path.join(DATA, "start_threshold.json"), "w"), indent=1)


# ============================================================ steering response
def steering():
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.axhline(0, color=MUTED, lw=1); ax.axvline(0, color=MUTED, lw=1)
    for robot, col in (("backlash", BLUE), ("nobacklash", AQUA)):
        pts = {}
        for name in (f"steering_{robot}.json", f"steering_wide_{robot}.json"):
            for s in load(name)["summary"]:
                pts[round(s["cmd"], 2)] = s
        xs = sorted(pts)
        ys = [pts[x]["yaw_rate_mean"] for x in xs]
        sd = [pts[x]["yaw_rate_sd"] for x in xs]
        ax.errorbar(xs, ys, yerr=sd, color=col, marker="o", markersize=6.5, markeredgecolor=SURFACE,
                    markeredgewidth=1.5, lw=2, capsize=0, elinewidth=1.2, label=ROBOT_LABEL[robot])
        z = np.polyfit(xs, ys, 1)
        ax.annotate(f"{ROBOT_LABEL[robot]}: slope {z[0]:.2f}, zero at {-z[1] / z[0]:+.2f} rad/s",
                    (1.55, ys[-1]), fontsize=8.5, va="center", color=INK, annotation_clip=False)
    ax.set_xlabel("commanded ang_vel_z (rad/s), vx = 0.2, pushing the box")
    ax.set_ylabel("achieved yaw rate (rad/s), t ≥ 2 s")
    ax.set_title("Steering while pushing: Shoe Push forward (10 boxes per point, ± sd)", loc="left")
    ax.legend(loc="upper left", fontsize=8.5)
    save(fig, "steering_response.png")


# ============================================================ heading hold paths
def heading_hold():
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, robot in zip(axes, ROBOTS):
        d = load(f"heading_hold_{robot}.json")
        tol, goal = d["args"]["tol"], d["args"]["goal"]
        x0, x1 = L.BOX_OFFSET, L.BOX_OFFSET + goal
        ax.axhspan(-tol, tol, color=NEUTRAL, alpha=0.3, lw=0)
        ax.axvline(x1, color=MUTED, lw=1.2, ls=(0, (4, 3)))
        ax.annotate(f"goal: {goal:.0f} m", (x1 + 0.02, 0.6), fontsize=8.5, color=INK2)
        ax.annotate(f"±{tol:.2f} m", (x0, tol + 0.02), fontsize=8, color=INK2)
        for name, col in (("open loop", ORANGE), ("heading hold", BLUE)):
            for o in d["trials"][name]:
                tr = np.array(o["trace"])
                ax.plot(tr[:, 3], tr[:, 4], color=col, lw=1.4, alpha=0.75)
                ax.scatter(tr[-1, 3], tr[-1, 4], s=22, color=col, edgecolor=SURFACE, zorder=4,
                           marker="o" if o["success"] else "X")
        s = d["summary"]
        ax.set_title(f"{ROBOT_LABEL[robot].capitalize()}: hold {s['heading hold']['success']}/10, "
                     f"open loop {s['open loop']['success']}/10", loc="left")
        ax.set_xlabel("box centre x (m)")
        ax.set_xlim(0.1, 1.35)
        ax.set_aspect("equal", adjustable="box")
    axes[0].set_ylabel("box centre y (m)")
    axes[0].set_ylim(-0.4, 0.95)
    axes[0].legend(handles=[Line2D([], [], color=BLUE, lw=2, label="heading hold (5 Hz PI + cross-track)"),
                            Line2D([], [], color=ORANGE, lw=2, label="open loop (vyaw = 0)"),
                            Line2D([], [], marker="o", ls="", color=MUTED, label="end: success"),
                            Line2D([], [], marker="X", ls="", color=MUTED, label="end: miss")],
                   loc="upper left", fontsize=8)
    save(fig, "heading_hold_paths.png")


if __name__ == "__main__":
    L.check_policies()
    for robot in ROBOTS:
        b0_figures(robot)
    start_threshold()
    steering()
    heading_hold()
