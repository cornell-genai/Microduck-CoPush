"""Vision: a duck sees its partner only while the partner is inside its front camera's view.

    visible(st, duck, fov_deg, range_m) -> bool

The camera looks along the duck's heading. The partner is visible when it is within range_m and within
half of fov_deg of the heading (the box does not block the view). In view, the duck gets the exact partner
position and heading, like D2 (copush.decentral.local_obs); out of view it falls back to the last chirp
(copush.chirp), so vision needs chirp.enabled. Settings (cfg["vision"], off by default):
    enabled   fov_deg   range_m
fov_deg and range_m are PLACEHOLDERS until measured on the real ducks' camera.
"""
from __future__ import annotations

import math

DUCKS = ("duck_a", "duck_b")


def visible(st: dict, duck: str, fov_deg: float, range_m: float) -> bool:
    me, mate = st[duck], st[DUCKS[1 - DUCKS.index(duck)]]
    c, s = math.cos(me["yaw"]), math.sin(me["yaw"])
    wx, wy = mate["position"][0] - me["position"][0], mate["position"][1] - me["position"][1]
    x, y = c * wx + s * wy, -s * wx + c * wy                  # partner in the duck's frame (x ahead, y left)
    dist = math.hypot(x, y)
    if dist > range_m:
        return False
    return dist < 1e-9 or abs(math.atan2(y, x)) <= math.radians(fov_deg) / 2.0
