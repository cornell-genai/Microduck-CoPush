"""Rendezvous: two ducks walk from anywhere near the box to their docking spots, then the push policy takes over.

The docking spots are the trained push policy's start poses (copush.env.docking_spots: 0.095 m behind the box centre
on the push side, 0.10 m to either side, facing the push direction), recomputed from the box's current pose every step.
A docking-spot sweep (experiments/d2-steering/docking-sweep, branch docking-sweep) found that a 3 cm shift from these
spots already costs the push policy 11 to 22 points, so arrival is judged to a few centimetres.

    rv = Rendezvous(env)                     # env: a CoPushEnv whose layout has start_mode approach
    st = rv.reset(start, seed)               # start: one entry of a rendezvous set (make_rendezvous_set)
    act = ScriptedRendezvous(rv)
    while not rv.ready() and rv.steps < 50:
        st, info = rv.step(act(None))
    obs, _ = env.begin_push_phase()           # then the push policy runs on env.step as usual

During the rendezvous both ducks stay on velstand (walking), with no automatic switch to Shoe Push on box contact,
and the env's push reward and endings are not used: Rendezvous drives env.sim itself, 10 control steps per 0.2 s step
like CoPushEnv.step, with the same action mapping (vx = 0.15 (a + 1), vyaw = 1.5 a). Collisions are counted per
step: a duck touching the box, or the two ducks touching each other.

Spot assignment (once per episode): the pairing with the shorter total distance; when the two pairings are within
`sym_m` of each other (a near-symmetric start), duck A takes the spot farther from the target, so ties always break the
same way. The push policy runs one shared network per duck, so which duck takes which spot does not matter to it.

RendezvousPairEnv is the training environment (two agents sharing a policy, per-duck rewards); RendezvousVecEnv
flattens N of them for Stable-Baselines3 like copush.decentral.DuckVecEnv, keeping each duck's own reward.
"""
from __future__ import annotations

import copy
import heapq
import math
from typing import Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from copush.env import CoPushEnv, action_to_cmd, cmd_to_action, docking_spots
from copush.sim import BOX_HALF, CONTROL_DT, DUCKS
from copush.state import wrap_angle

DEFAULTS = {
    "pos_tol_m": 0.03, "yaw_tol_deg": 15.0, "hold_s": 0.25,   # arrived: both within these for hold_s (episode end)
    "stop_pos_m": 0.02, "stop_yaw_deg": 10.0,                 # scripted: a duck stops and holds within these
    "max_steps": 100, "handoff_steps": 50,                    # training episode length; pipeline cap before handoff
    "sym_m": 0.05,                                            # near-symmetric start: pairings within this (m)
    "start": {"dist_m": [0.2, 0.8], "kinds": {"uniform": 0.8, "near_symmetric": 0.1, "wrong_side": 0.1},
              "clear_box_m": 0.08, "clear_ducks_m": 0.15, "sym_lateral_m": 0.02, "wrong_side_cone_deg": 60.0},
    "reward": {"w_dist": 10.0, "w_yaw": 1.0, "time": 0.03, "collision": 1.0, "arrive": 5.0, "timeout": 5.0},
}
DUCK_RADIUS_M = 0.08            # clearance kept from the box when walking around it (duck centres are 0.12 m apart at least)
CORNER_OFFSET_M = 0.15          # waypoints this far off each box corner, along the corner's diagonal
STAGE_BACK_M = 0.12             # scripted: approach each spot from a staging point this far behind it
OBS_NAMES = ["spot_dx", "spot_dy", "spot_sin", "spot_cos", "mate_dx", "mate_dy", "mate_sin", "mate_cos",
             "box_dx", "box_dy", "box_sin2", "box_cos2", "own_vx", "own_vy"]


def settings(cfg: dict) -> dict:
    """The config's `rendezvous` block over DEFAULTS (nested dicts merged)."""
    out = copy.deepcopy(DEFAULTS)
    for k, v in (cfg.get("rendezvous") or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **{kk: (dict(out[k][kk], **vv) if isinstance(vv, dict) and isinstance(out[k].get(kk), dict) else vv)
                                    for kk, vv in v.items()}}
        else:
            out[k] = v
    return out


# ── geometry ────────────────────────────────────────────────────────────────

def box_pose(st: dict) -> dict:
    x, y = st["box"]["position"]
    return {"x": x, "y": y, "yaw": math.degrees(st["box"]["yaw"])}


def target_xy(st: dict) -> dict:
    gx, gy = st["goal"]["position"]
    return {"x": gx, "y": gy}


def spot_poses(st: dict, setback: float, spacing: float) -> dict:
    """{"left": (x, y, yaw_rad), "right": ...}: the docking spots for the box's current pose (left = duck A's spot in the
    in-contact start, on the left of the push direction)."""
    s = docking_spots(box_pose(st), target_xy(st), setback, spacing)
    return {slot: (s[d][0], s[d][1], math.radians(s[d][2])) for slot, d in (("left", "duck_a"), ("right", "duck_b"))}


def assign_spots(st: dict, spots: dict, sym_m: float) -> dict:
    """{duck: slot}: the pairing with the shorter total distance; within sym_m of a tie, duck A takes the spot farther
    from the target."""
    pos = {d: st[d]["position"] for d in DUCKS}
    straight = math.dist(pos["duck_a"], spots["left"][:2]) + math.dist(pos["duck_b"], spots["right"][:2])
    swapped = math.dist(pos["duck_a"], spots["right"][:2]) + math.dist(pos["duck_b"], spots["left"][:2])
    if abs(straight - swapped) < sym_m:
        g = st["goal"]["position"]
        far = max(("left", "right"), key=lambda s: math.dist(spots[s][:2], g))
        return {"duck_a": far, "duck_b": "right" if far == "left" else "left"}
    return {"duck_a": "left", "duck_b": "right"} if straight <= swapped else {"duck_a": "right", "duck_b": "left"}


def pairing_margin(st: dict, spots: dict) -> float:
    """|total distance of one pairing - the other| (m): small = a near-symmetric start."""
    pos = {d: st[d]["position"] for d in DUCKS}
    straight = math.dist(pos["duck_a"], spots["left"][:2]) + math.dist(pos["duck_b"], spots["right"][:2])
    swapped = math.dist(pos["duck_a"], spots["right"][:2]) + math.dist(pos["duck_b"], spots["left"][:2])
    return abs(straight - swapped)


def _to_box(p, box) -> tuple:
    b = math.radians(box["yaw"])
    dx, dy = p[0] - box["x"], p[1] - box["y"]
    return dx * math.cos(b) + dy * math.sin(b), -dx * math.sin(b) + dy * math.cos(b)


def _from_box(q, box) -> tuple:
    b = math.radians(box["yaw"])
    return box["x"] + q[0] * math.cos(b) - q[1] * math.sin(b), box["y"] + q[0] * math.sin(b) + q[1] * math.cos(b)


def in_box_footprint(p, box, margin: float) -> bool:
    x, y = _to_box(p, box)
    return abs(x) <= BOX_HALF[0] + margin and abs(y) <= BOX_HALF[1] + margin


def segment_hits_box(p, q, box, margin: float) -> bool:
    """Does the segment p-q cross the box rectangle grown by margin (Liang-Barsky clipping in the box frame)?"""
    (x0, y0), (x1, y1) = _to_box(p, box), _to_box(q, box)
    hx, hy = BOX_HALF[0] + margin, BOX_HALF[1] + margin
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, x0 + hx), (dx, hx - x0), (-dy, y0 + hy), (dy, hy - y0)):
        if pp == 0:
            if qq < 0:
                return False
            continue
        r = qq / pp
        if pp < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return False
    return True


def corner_waypoints(box) -> list:
    """Four points CORNER_OFFSET_M off the box corners along their 45-degree diagonals (world frame)."""
    d = CORNER_OFFSET_M / math.sqrt(2)
    return [_from_box((sx * (BOX_HALF[0] + d), sy * (BOX_HALF[1] + d)), box) for sx in (1, -1) for sy in (1, -1)]


def plan_path(p, goal, box, margin: float = DUCK_RADIUS_M) -> list:
    """Shortest route p -> goal around the box: straight when the line clears the grown box, else via the corner
    waypoints (a small visibility graph). Returns the waypoints after p, ending with goal."""
    if not segment_hits_box(p, goal, box, margin):
        return [goal]
    nodes = [tuple(p)] + corner_waypoints(box) + [tuple(goal)]
    start_inside = in_box_footprint(p, box, margin)

    def free(i, j):
        if i == 0 and start_inside:                     # already brushing the box: leave by the nearest free edge
            return not segment_hits_box(nodes[j], nodes[j], box, margin)
        return not segment_hits_box(nodes[i], nodes[j], box, margin)
    dist = {0: 0.0}
    prev = {}
    heap = [(0.0, 0)]
    while heap:
        d0, i = heapq.heappop(heap)
        if i == len(nodes) - 1:
            break
        if d0 > dist.get(i, math.inf):
            continue
        for j in range(1, len(nodes)):
            if j != i and free(i, j):
                nd = d0 + math.dist(nodes[i], nodes[j])
                if nd < dist.get(j, math.inf):
                    dist[j], prev[j] = nd, i
                    heapq.heappush(heap, (nd, j))
    last = len(nodes) - 1
    if last not in prev:
        return [goal]
    path, k = [], last
    while k != 0:
        path.append(nodes[k])
        k = prev[k]
    return path[::-1]


# ── stepping ────────────────────────────────────────────────────────────────

class Rendezvous:
    """The rendezvous phase on a CoPushEnv (layout with start_mode approach): reset from a start, step with the usual
    4-vector action, keep both ducks on velstand, count collisions, report errors to the assigned spots."""

    def __init__(self, env: CoPushEnv, rcfg: Optional[dict] = None):
        if env.start_mode != "approach":
            raise ValueError("Rendezvous needs a layout with start_mode approach (the ducks start where the start puts them)")
        self.env, self.sim = env, env.sim
        self.r = rcfg or settings(env.cfg)
        self.setback, self.spacing = env.ecfg["contact_setback"], env.ecfg["contact_spacing"]
        self.pos_tol, self.yaw_tol = self.r["pos_tol_m"], math.radians(self.r["yaw_tol_deg"])
        self.episode = 0
        self.frame_hook = None          # callable(state, steps) after every control step (videos)

    def reset(self, start: dict, seed: Optional[int] = None) -> dict:
        env = self.env
        for d in DUCKS:
            env.cfg[d].update({"x": float(start[d]["x"]), "y": float(start[d]["y"]), "yaw": float(start[d]["yaw"]),
                               "policy": "velstand"})
        env.reset(seed=seed, options={"box": start["box"]})
        st = self.sim.step({"A": (0, 0, 0), "B": (0, 0, 0)}, duration=env.ecfg["settle_s"])
        st = self.sim.mark_start()
        env.state = st
        self.spots = spot_poses(st, self.setback, self.spacing)
        self.assign = assign_spots(st, self.spots, self.r["sym_m"])
        self.steps, self.arrived_s, self.episode = 0, 0.0, self.episode + 1
        self.collisions = {"box": {d: 0 for d in DUCKS}, "ducks": 0}
        self.start = start
        return st

    @property
    def state(self) -> dict:
        return self.env.state

    def target(self, duck: str, st: Optional[dict] = None) -> tuple:
        """The duck's assigned spot (x, y, yaw_rad) for the box's pose in st (default: now)."""
        st = st or self.env.state
        return spot_poses(st, self.setback, self.spacing)[self.assign[duck]]

    def errors(self, st: Optional[dict] = None) -> dict:
        """{duck: (position error m, heading error rad)} to the assigned spot."""
        st = st or self.env.state
        spots = spot_poses(st, self.setback, self.spacing)
        out = {}
        for d in DUCKS:
            x, y, yaw = spots[self.assign[d]]
            out[d] = (math.dist(st[d]["position"], (x, y)), abs(wrap_angle(st[d]["yaw"] - yaw)))
        return out

    def within(self, st: Optional[dict] = None, pos_tol: Optional[float] = None, yaw_tol: Optional[float] = None) -> bool:
        st = st or self.env.state
        pt, yt = pos_tol or self.pos_tol, yaw_tol or self.yaw_tol
        e = self.errors(st)
        return all(e[d][0] <= pt and e[d][1] <= yt and not st[d]["down"] for d in DUCKS)

    def ready(self) -> bool:
        """Handoff test at a step boundary: both ducks within pos_tol_m and yaw_tol_deg of their spots, upright."""
        return self.within()

    def arrived(self) -> bool:
        """Episode-end test: ready() held for hold_s (checked every control step)."""
        return self.arrived_s >= self.r["hold_s"] - 1e-9

    def ducks_touching(self) -> bool:
        d, owner = self.sim.d, self.sim.geom_owner
        for g1, g2 in d.contact.geom[:d.ncon]:
            o1, o2 = owner.get(int(g1)), owner.get(int(g2))
            if o1 and o2 and o1[0] != o2[0]:
                return True
        return False

    def step(self, action) -> tuple:
        cmds = action_to_cmd(action)
        for d in DUCKS:
            if self.sim.pol[d].policy != "velstand":
                self.sim.set_policy(d, "velstand")
        hit_box = {d: False for d in DUCKS}
        hit_ducks = False
        st = self.env.state
        for k in range(self.env.n_ctrl):
            st = self.sim.step(cmds if k == 0 else None)
            for d in DUCKS:
                hit_box[d] |= st["contact"][d]["in_contact"]
            hit_ducks |= self.ducks_touching()
            self.arrived_s = self.arrived_s + CONTROL_DT if self.within(st) else 0.0
            if self.frame_hook is not None:
                self.frame_hook(st, self.steps)
        self.env.state = st
        self.steps += 1
        for d in DUCKS:
            self.collisions["box"][d] += hit_box[d]
        self.collisions["ducks"] += hit_ducks
        info = {"hit_box": hit_box, "hit_ducks": hit_ducks, "arrived": self.arrived(),
                "fell": any(st[d]["down"] for d in DUCKS), "errors": self.errors(st)}
        return st, info


# ── scripted coordinator ────────────────────────────────────────────────────

class ScriptedRendezvous:
    """Scripted baseline: each duck independently walks onto the line behind its spot and follows it in.

    travel  toward the next waypoint (plan_path around the box, to a staging point STAGE_BACK_M behind the spot): if the
            bearing is more than turn_deg off the heading, rotate in place toward it; else walk at walk_vx, steering
            toward it. As soon as the duck is behind its spot with a clear line to it, it switches to final.
    final   line following onto the spot: the heading target is the push direction bent toward the line by the
            sideways error (pure pursuit with a lookahead that shrinks as the spot nears, at most +-70 deg), rotating in
            place first if the heading is more than 45 deg off; walk at walk_vx, then creep_vx for the last 6 cm
            (velstand keeps creeping at a low command once it walks; from rest it needs about 0.25 m/s). Stop when the
            spot is reached along the push direction, or when within stop_pos_m and stop_yaw_deg.
    hold    zero command (velstand stands still). A duck more than stop_yaw_deg off the push heading turns in place
            toward it; one pushed more than restage_m off its spot goes back to travel.
    A travelling duck waits (zero command) while its partner is within yield_m in front of it and closer to its own
    staging point, so the two do not walk into each other.
    """

    def __init__(self, rv: Rendezvous, walk_vx: float = 0.3, creep_vx: float = 0.12, turn_deg: float = 20.0,
                 restage_m: float = 0.05, yield_m: float = 0.18):
        self.rv = rv
        self.walk_vx, self.creep_vx, self.turn = walk_vx, creep_vx, math.radians(turn_deg)
        self.restage_m, self.yield_m = restage_m, yield_m
        self.stop_pos, self.stop_yaw = rv.r["stop_pos_m"], math.radians(rv.r["stop_yaw_deg"])
        self.episode = None

    def _reset(self):
        self.phase = {d: "travel" for d in DUCKS}
        self.episode = self.rv.episode

    def _staging(self, spot):
        x, y, yaw = spot
        return x - STAGE_BACK_M * math.cos(yaw), y - STAGE_BACK_M * math.sin(yaw)

    def _rotate(self, err):
        return 0.0, math.copysign(1.2 if abs(err) > math.radians(25) else 0.8, err)

    def _duck(self, d, st):
        rv = self.rv
        me = st[d]
        p, h = me["position"], me["yaw"]
        spot = rv.target(d, st)
        stage = self._staging(spot)
        u = (math.cos(spot[2]), math.sin(spot[2]))
        dx, dy = spot[0] - p[0], spot[1] - p[1]
        s = dx * u[0] + dy * u[1]                      # along the push direction, to go
        lat = -dx * u[1] + dy * u[0]                   # sideways error (> 0: the spot is to the duck's left of the line)
        pos_err = math.dist(p, spot[:2])
        herr = wrap_angle(spot[2] - h)
        box = box_pose(st)
        if self.phase[d] == "hold":
            if pos_err > self.restage_m:
                self.phase[d] = "travel"
            elif abs(herr) > self.stop_yaw:
                return self._rotate(herr)
            else:
                return 0.0, 0.0
        if self.phase[d] == "travel":
            if s > 0.06 and abs(lat) < 0.6 * s + 0.05 and not segment_hits_box(p, stage, box, DUCK_RADIUS_M):
                self.phase[d] = "final"
            else:
                wp = plan_path(p, stage, box)[0]
                if self._blocked(d, st, wp):
                    return 0.0, 0.0
                e = wrap_angle(math.atan2(wp[1] - p[1], wp[0] - p[0]) - h)
                if abs(e) > self.turn:
                    return self._rotate(e)
                return self.walk_vx, max(-1.0, min(1.0, 2.0 * e))
        if s <= 0.006 or (pos_err <= self.stop_pos and abs(herr) <= self.stop_yaw):
            self.phase[d] = "hold"
            return (0.0, 0.0) if abs(herr) <= self.stop_yaw else self._rotate(herr)
        if s < -0.03 or segment_hits_box(p, (p[0] + 0.5 * dx, p[1] + 0.5 * dy), box, 0.0):
            self.phase[d] = "travel"                   # overshot, or the box is in the way: go round again
            return 0.0, 0.0
        look = max(0.04, min(0.25, 0.8 * s))
        want = spot[2] + max(-1.22, min(1.22, math.atan2(lat, look)))
        e = wrap_angle(want - h)
        if abs(e) > math.radians(45):
            return self._rotate(e)
        fwd = me["velocity"][0] * math.cos(h) + me["velocity"][1] * math.sin(h)
        vx = self.walk_vx if (s > 0.06 or fwd < 0.02) else self.creep_vx
        return vx, max(-1.0, min(1.0, 2.0 * e))

    def _blocked(self, d, st, wp) -> bool:
        mate = DUCKS[1 - DUCKS.index(d)]
        p, q = st[d]["position"], st[mate]["position"]
        if math.dist(p, q) > self.yield_m or self.phase[mate] == "hold":
            return False
        ahead = math.atan2(wp[1] - p[1], wp[0] - p[0])
        if abs(wrap_angle(math.atan2(q[1] - p[1], q[0] - p[0]) - ahead)) > math.radians(60):
            return False
        mine = math.dist(p, self._staging(self.rv.target(d, st)))
        theirs = math.dist(q, self._staging(self.rv.target(mate, st)))
        return mine > theirs or (mine == theirs and d == "duck_b")

    def __call__(self, obs=None):
        if self.episode != self.rv.episode:
            self._reset()
        st = self.rv.state
        cmd = {d: self._duck(d, st) for d in DUCKS}
        return cmd_to_action(cmd["duck_a"][0], cmd["duck_a"][1], cmd["duck_b"][0], cmd["duck_b"][1])


# ── starts ──────────────────────────────────────────────────────────────────

def _valid(ducks: dict, box: dict, sc: dict) -> bool:
    if any(in_box_footprint(ducks[d][:2], box, sc["clear_box_m"]) for d in DUCKS):
        return False
    return math.dist(ducks["duck_a"][:2], ducks["duck_b"][:2]) >= sc["clear_ducks_m"]


def _push_dir(box: dict, target: dict, setback: float, spacing: float) -> tuple:
    s = docking_spots(box, target, setback, spacing)
    yaw = math.radians(s["duck_a"][2])
    return math.cos(yaw), math.sin(yaw)


def sample_ducks(rng: np.random.Generator, box: dict, target: dict, kind: str, sc: dict, setback: float, spacing: float,
                 max_tries: int = 1000) -> dict:
    """Duck poses {duck: (x, y, yaw_deg)} for one start of `kind`, relative to the box centre:
    uniform         each duck independently: distance dist_m uniform, bearing and heading uniform over 360 deg
    near_symmetric  both ducks within sym_lateral_m of the box's push axis (equally far from both spots), in front of or
                    behind the box, distance as above, heading uniform
    wrong_side      both ducks on the target side: bearing within wrong_side_cone_deg of the push direction
    Redrawn until neither duck is within clear_box_m of the box and the ducks are clear_ducks_m apart."""
    lo, hi = sc["dist_m"]
    u = _push_dir(box, target, setback, spacing)
    left = (-u[1], u[0])
    push_bearing = math.atan2(u[1], u[0])
    for _ in range(max_tries):
        ducks = {}
        for d in DUCKS:
            r = float(rng.uniform(lo, hi))
            if kind == "uniform":
                a = float(rng.uniform(-math.pi, math.pi))
                x, y = box["x"] + r * math.cos(a), box["y"] + r * math.sin(a)
            elif kind == "near_symmetric":
                s = 1.0 if rng.uniform() < 0.5 else -1.0
                lat = float(rng.uniform(-sc["sym_lateral_m"], sc["sym_lateral_m"]))
                x, y = box["x"] + s * r * u[0] + lat * left[0], box["y"] + s * r * u[1] + lat * left[1]
            elif kind == "wrong_side":
                c = math.radians(sc["wrong_side_cone_deg"])
                a = push_bearing + float(rng.uniform(-c, c))
                x, y = box["x"] + r * math.cos(a), box["y"] + r * math.sin(a)
            else:
                raise ValueError(f"unknown start kind {kind!r}")
            ducks[d] = (x, y, float(rng.uniform(-180.0, 180.0)))
        if _valid(ducks, box, sc):
            return ducks
    raise RuntimeError(f"no valid {kind} start in {max_tries} tries")


def start_flags(ducks: dict, box: dict, target: dict, setback: float, spacing: float) -> dict:
    """Pairing margin (m) and how many ducks start on the target side of the box (in front of its push face)."""
    s = docking_spots(box, target, setback, spacing)
    spots = {"left": s["duck_a"][:2], "right": s["duck_b"][:2]}
    a, b = ducks["duck_a"][:2], ducks["duck_b"][:2]
    margin = abs((math.dist(a, spots["left"]) + math.dist(b, spots["right"]))
                 - (math.dist(a, spots["right"]) + math.dist(b, spots["left"])))
    u = _push_dir(box, target, setback, spacing)
    front = sum(1 for p in (a, b) if (p[0] - box["x"]) * u[0] + (p[1] - box["y"]) * u[1] > BOX_HALF[1])
    return {"pairing_margin_m": round(margin, 4), "ducks_on_target_side": front}


def as_start(i: int, kind: str, box: dict, ducks: dict, target: dict, setback: float, spacing: float) -> dict:
    return {"id": i, "kind": kind, "box": {k: round(float(box[k]), 5) for k in ("x", "y", "yaw")},
            **{d: {"x": round(ducks[d][0], 5), "y": round(ducks[d][1], 5), "yaw": round(ducks[d][2], 3)} for d in DUCKS},
            "flags": start_flags(ducks, box, target, setback, spacing)}


def make_rendezvous_set(base_starts: list, target: dict, n_kind: dict, rng_seed: int, sc: dict,
                        setback: float, spacing: float) -> list:
    """One start per base box pose (in order); the kinds are dealt to the poses by a seeded shuffle so each kind spans
    the box range."""
    rng = np.random.default_rng(rng_seed)
    kinds = [k for k, c in n_kind.items() for _ in range(c)]
    if len(kinds) != len(base_starts):
        raise ValueError(f"{len(kinds)} kinds for {len(base_starts)} box poses")
    kinds = [kinds[j] for j in rng.permutation(len(kinds))]
    out = []
    for i, (b, kind) in enumerate(zip(base_starts, kinds)):
        box = {"x": b["x"], "y": b["y"], "yaw": b["yaw"]}
        out.append(as_start(i, kind, box, sample_ducks(rng, box, target, kind, sc, setback, spacing), target, setback, spacing))
    return out


def sample_start(rng: np.random.Generator, cfg: dict, sc: dict) -> dict:
    """A training start from the same distribution as the eval set: box pose uniform over env.box_start's full range
    around the nominal box, kind drawn with start.kinds' probabilities."""
    bs, b0, e = cfg["env"]["box_start"], cfg["box"], cfg["env"]
    box = {"x": b0["x"] + float(rng.uniform(-bs["dx"], bs["dx"])), "y": b0["y"] + float(rng.uniform(-bs["dy"], bs["dy"])),
           "yaw": b0["yaw"] + float(rng.uniform(-bs["dyaw"], bs["dyaw"]))}
    names = list(sc["kinds"])
    p = np.array([sc["kinds"][k] for k in names], dtype=float)
    kind = names[int(rng.choice(len(names), p=p / p.sum()))]
    tg = {"x": cfg["target"]["x"], "y": cfg["target"]["y"]}
    return as_start(-1, kind, box, sample_ducks(rng, box, tg, kind, sc, e["contact_setback"], e["contact_spacing"]),
                    tg, e["contact_setback"], e["contact_spacing"])


# ── observations and the training env ──────────────────────────────────────

def local_obs(rv: Rendezvous, st: dict, duck: str) -> np.ndarray:
    """One duck's view, in its own frame (x along its heading): its assigned spot (position, heading as sin/cos), its
    partner (position, heading), the box (position, yaw as sin/cos of 2x; 180-degree symmetric), its own velocity."""
    me = st[duck]
    h = me["yaw"]
    c, s = math.cos(h), math.sin(h)

    def tf(x, y):
        return c * x + s * y, -s * x + c * y
    mx, my = me["position"]
    sx, sy, syaw = rv.target(duck, st)
    mate = st[DUCKS[1 - DUCKS.index(duck)]]
    px, py = mate["position"]
    bx, by = st["box"]["position"]
    dh, ph, bh = wrap_angle(syaw - h), wrap_angle(mate["yaw"] - h), wrap_angle(st["box"]["yaw"] - h)
    o = [*tf(sx - mx, sy - my), math.sin(dh), math.cos(dh), *tf(px - mx, py - my), math.sin(ph), math.cos(ph),
         *tf(bx - mx, by - my), math.sin(2 * bh), math.cos(2 * bh), *tf(*me["velocity"])]
    return np.asarray(o, dtype=np.float32)


def pair_obs(rv: Rendezvous, st: dict) -> np.ndarray:
    return np.stack([local_obs(rv, st, d) for d in DUCKS])


def policy_act(model, rv: Rendezvous, deterministic: bool = True):
    """obs -> the 4-vector action, from a shared per-duck policy trained on RendezvousPairEnv."""
    def act(obs=None):
        a, _ = model.predict(pair_obs(rv, rv.state), deterministic=deterministic)
        return np.clip(np.asarray(a, dtype=np.float32), -1.0, 1.0).reshape(4)
    return act


class RendezvousPairEnv(gym.Env):
    """Rendezvous training: one simulation as two agents sharing a policy. Observation (2, 14), action (2, 2), reward
    (2,): each duck's own reward per step,
        w_dist x (decrease in its distance to its spot) + w_yaw x (decrease in its heading error, rad) - time
        - collision (if it touched the box or its partner this step)
    plus arrive to both when both ducks are within pos_tol_m and yaw_tol_deg of their spots for hold_s (terminated),
    and -timeout to both at max_steps (truncated) or when a duck falls (terminated, info reason "fall").
    Starts: options={"start": ...} (an eval-set entry), else sample_start from the env's own seeded RNG."""
    metadata = {"render_modes": []}

    def __init__(self, cfg: dict, split: str = "train"):
        super().__init__()
        self.env = CoPushEnv(cfg, split=split)
        self.rv = Rendezvous(self.env)
        self.rw = self.rv.r["reward"]
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(2, len(OBS_NAMES)), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(2, 2), dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        start = (options or {}).get("start") or sample_start(self.np_random, self.env.cfg, self.rv.r["start"])
        st = self.rv.reset(start, seed=seed)
        self._prev = self.rv.errors(st)
        return pair_obs(self.rv, st), {"start": start}

    def step(self, action):
        st, info = self.rv.step(np.asarray(action, dtype=np.float32).reshape(4))
        err, rw = info["errors"], self.rw
        r = np.zeros(2, dtype=np.float32)
        for k, d in enumerate(DUCKS):
            r[k] = (rw["w_dist"] * (self._prev[d][0] - err[d][0]) + rw["w_yaw"] * (self._prev[d][1] - err[d][1])
                    - rw["time"] - rw["collision"] * float(info["hit_box"][d] or info["hit_ducks"]))
        self._prev = err
        terminated, truncated, reason = False, False, None
        if info["arrived"]:
            r += rw["arrive"]
            terminated, reason = True, "arrived"
        elif info["fell"]:
            r -= rw["timeout"]
            terminated, reason = True, "fall"
        elif self.rv.steps >= self.rv.r["max_steps"]:
            r -= rw["timeout"]
            truncated, reason = True, "timeout"
        info = {"reason": reason, "steps": self.rv.steps, "collisions": self.rv.collisions,
                "errors": {d: [float(v) for v in err[d]] for d in DUCKS}}
        return pair_obs(self.rv, st), r, terminated, truncated, info

    def close(self):
        self.env.close()


def make_rendezvous_pair_env(cfg: dict, split: str = "train"):
    def _thunk():
        return RendezvousPairEnv(cfg, split)
    return _thunk


def make_rendezvous_vec_env(cfg: dict, n_envs: int, split: str = "train"):
    from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor
    return VecMonitor(RendezvousVecEnv(SubprocVecEnv([make_rendezvous_pair_env(cfg, split) for _ in range(n_envs)])))


def _vec_base():
    from copush.decentral import DuckVecEnv
    return DuckVecEnv


class RendezvousVecEnv(_vec_base()):
    """N RendezvousPairEnv workers -> 2N single-duck entries, like DuckVecEnv, but each duck keeps its own reward."""

    def step_wait(self):
        obs, rew, done, infos = self.venv.step_wait()
        out = []
        for info in infos:
            for k in range(2):
                d = dict(info)
                if "terminal_observation" in info:
                    d["terminal_observation"] = info["terminal_observation"][k]
                out.append(d)
        return obs.reshape(self.num_envs, -1), np.asarray(rew, dtype=np.float32).reshape(-1), np.repeat(done, 2), out

