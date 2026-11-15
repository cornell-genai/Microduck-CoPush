"""Partner sensing by chirps: each duck hears a noisy direction (and optionally a rough distance) to
its partner, once per chirp, instead of the partner's exact position.

    sensor = ChirpSensor(cfg["chirp"], env.dt)
    st["chirp"] = sensor.reset(st, rng)          # at reset: both ducks hear a chirp at t = 0
    st["chirp"] = sensor.update(st, rng)         # after every control step

st["chirp"][duck] is (dx, dy), the partner's position in that duck's own frame (x along its heading,
y to its left), in the same units and place as D2's exact partner position (copush.decentral), so the
observation keeps its size. It is held fixed in the duck's frame until that duck's next chirp.

Settings (cfg["chirp"], all off by default):
    enabled                 the env fills st["chirp"]; a decentral controller with include_partner reads it
    interval_s              seconds between one duck's chirps (a chirp is heard at the first control step
                            at or after its time, so an interval of one control step or less is every step)
    direction_noise_deg     the bearing to the partner gets Gaussian noise with this standard deviation
    distance                on: the distance is heard too, with Gaussian relative noise; off: no distance
                            is heard and the vector gets a fixed length (nominal_distance_m)
    distance_noise          standard deviation of the relative distance noise (0.3 = about 30%)
    nominal_distance_m      the length used when distance is off (the ducks start 0.20 m apart)
    miss_prob               chance that a scheduled chirp is lost (the duck keeps its last value); the chirp at
                            t = 0 is always heard. 0 = never lost
    front_back_flip_prob    chance that a heard chirp's direction is mirrored front to back (x -> -x, as sound
                            localization with two ears confuses front and back). 0 = never
    heading                 zero (default, the real case): the partner's heading is not heard, so D2's two
                            heading entries are 0; true: the exact partner heading is filled in at every
                            step (a diagnostic, not something a duck could hear)
miss_prob and front_back_flip_prob are PLACEHOLDERS (0 = off) until measured on the real ducks.
The two ducks' chirps are staggered: each duck's chirp times are shifted by its own random offset in
[0, interval_s), drawn at every reset (copush.decentral.local_obs puts the heading entries in).
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

DUCKS = ("duck_a", "duck_b")
HEADINGS = ("zero", "true")
_EPS = 1e-9


class ChirpSensor:
    def __init__(self, ccfg: dict, dt: float):
        self.interval = float(ccfg["interval_s"])
        self.sigma = math.radians(float(ccfg["direction_noise_deg"]))
        self.use_distance = bool(ccfg["distance"])
        self.dist_noise = float(ccfg["distance_noise"])
        self.nominal = float(ccfg["nominal_distance_m"])
        self.heading = str(ccfg.get("heading", "zero"))
        self.miss_prob = float(ccfg.get("miss_prob", 0.0))
        self.flip_prob = float(ccfg.get("front_back_flip_prob", 0.0))
        self.dt = float(dt)
        if self.interval <= 0 or self.nominal <= 0:
            raise ValueError("chirp.interval_s and chirp.nominal_distance_m must be positive")
        if not (0.0 <= self.miss_prob <= 1.0 and 0.0 <= self.flip_prob <= 1.0):
            raise ValueError("chirp.miss_prob and chirp.front_back_flip_prob must be between 0 and 1")
        if self.heading not in HEADINGS:
            raise ValueError(f"chirp.heading must be one of {HEADINGS}, not {self.heading!r}")
        if self.sigma < 0 or self.dist_noise < 0:
            raise ValueError("chirp.direction_noise_deg and chirp.distance_noise must not be negative")

    # ── episode ─────────────────────────────────────────────────────────────
    def reset(self, st: dict, rng) -> Dict[str, Tuple[float, float]]:
        self.k = 0
        self.offset = {d: float(rng.uniform(0.0, self.interval)) for d in DUCKS}
        self.n_heard = {d: 0 for d in DUCKS}                  # scheduled chirps already heard
        self.held = {d: self._hear(st, d, rng) for d in DUCKS}   # everyone hears one at t = 0
        self.last_chirp_step = {d: 0 for d in DUCKS}
        return dict(self.held)

    def update(self, st: dict, rng) -> Dict[str, Tuple[float, float]]:
        self.k += 1
        t = self.k * self.dt
        for d in DUCKS:
            due = False
            while self.offset[d] + self.n_heard[d] * self.interval <= t + _EPS:
                self.n_heard[d] += 1
                due = True
            if due and self.miss_prob > 0 and rng.random() < self.miss_prob:
                continue                                       # the chirp was lost: keep the last value
            if due:
                self.held[d] = self._hear(st, d, rng)
                self.last_chirp_step[d] = self.k
        return dict(self.held)

    # ── one chirp ───────────────────────────────────────────────────────────
    def _hear(self, st: dict, duck: str, rng) -> Tuple[float, float]:
        me = st[duck]
        mate = st[DUCKS[1 - DUCKS.index(duck)]]
        c, s = math.cos(me["yaw"]), math.sin(me["yaw"])
        wx, wy = mate["position"][0] - me["position"][0], mate["position"][1] - me["position"][1]
        x, y = c * wx + s * wy, -s * wx + c * wy               # partner in this duck's frame
        bearing = math.atan2(y, x) + float(rng.normal(0.0, self.sigma))
        if self.use_distance:
            dist = math.hypot(x, y) * max(0.2, 1.0 + float(rng.normal(0.0, self.dist_noise)))
        else:
            dist = self.nominal
        x, y = dist * math.cos(bearing), dist * math.sin(bearing)
        if self.flip_prob > 0 and rng.random() < self.flip_prob:
            x = -x                                             # front-back confusion: mirrored across the lateral axis
        return (x, y)
