"""Vision: a duck sees its partner only while the partner is inside its front camera's view.

    visible(st, duck, fov_deg, range_m) -> bool

The camera looks along the duck's heading. The partner is visible when it is within range_m and within
half of fov_deg of the heading. With box_half given (vision.occlusion), the box also blocks the view: the
partner is hidden when the straight line from the duck to the partner crosses the box. In view, the duck gets the exact partner
position and heading, like D2 (copush.decentral.local_obs); out of view it falls back to the last chirp
(copush.chirp), so vision needs chirp.enabled. Settings (cfg["vision"], off by default):
    enabled   fov_deg   range_m   occlusion
fov_deg and range_m are PLACEHOLDERS until measured on the real ducks' camera.
"""
from __future__ import annotations

import math

DUCKS = ("duck_a", "duck_b")


def blocked(st: dict, duck: str, box_half) -> bool:
    """Does the straight line from the duck to its partner cross the box (a rectangle of half sides box_half,
    centered on st["box"], turned by its yaw)?"""
    me, mate, box = st[duck], st[DUCKS[1 - DUCKS.index(duck)]], st["box"]
    bx, by = box["position"]
    c, s = math.cos(box["yaw"]), math.sin(box["yaw"])

    def to_box(p):                                            # world point -> the box's own frame
        dx, dy = p[0] - bx, p[1] - by
        return c * dx + s * dy, -s * dx + c * dy

    (x0, y0), (x1, y1) = to_box(me["position"]), to_box(mate["position"])
    t0, t1 = 0.0, 1.0                                         # slab test of the segment against |x| <= hx, |y| <= hy
    for p0, d, h in ((x0, x1 - x0, box_half[0]), (y0, y1 - y0, box_half[1])):
        if abs(d) < 1e-12:
            if abs(p0) > h:
                return False
            continue
        ta, tb = sorted(((-h - p0) / d, (h - p0) / d))
        t0, t1 = max(t0, ta), min(t1, tb)
        if t0 > t1:
            return False
    return True


def visible(st: dict, duck: str, fov_deg: float, range_m: float, box_half=None) -> bool:
    me, mate = st[duck], st[DUCKS[1 - DUCKS.index(duck)]]
    c, s = math.cos(me["yaw"]), math.sin(me["yaw"])
    wx, wy = mate["position"][0] - me["position"][0], mate["position"][1] - me["position"][1]
    x, y = c * wx + s * wy, -s * wx + c * wy                  # partner in the duck's frame (x ahead, y left)
    dist = math.hypot(x, y)
    if dist > range_m:
        return False
    if not (dist < 1e-9 or abs(math.atan2(y, x)) <= math.radians(fov_deg) / 2.0):
        return False
    return box_half is None or not blocked(st, duck, box_half)
