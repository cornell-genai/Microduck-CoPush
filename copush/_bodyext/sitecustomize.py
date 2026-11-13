"""Adds one read-only op, `{"op": "objects"}`, to microduck_rl's body server — without editing it.

Why this exists: the body server's protocol (`mjlab_microduck.sim.body_server`) answers only for
the duck on each port: its joints, its trunk, its IMU. A free-joint box in the same world has no
port and no op, so its pose cannot be read from outside the process. We must not edit tracked
upstream files, and `scripts/duck-sim` hard-codes `python -m mjlab_microduck.sim.body_server`.

So this file is put on PYTHONPATH (only by `scripts/sim.sh up`, never globally). Python
imports `sitecustomize` at start-up; this one does nothing unless the process is the body server.
In the body server it wraps `socketserver.BaseServer.__init__` so that the request-handler class
gets one extra op. Every existing op is passed through untouched.

    -> {"op": "objects"}
    <- {"sim_time": 1.23,
        "objects": {"box": {"pos": [x, y, z], "quat": [w, x, y, z], "linvel": [vx, vy, vz],
                            "angvel": [wx, wy, wz]}}}

"objects" are the bodies that own a free joint other than a duck's trunk. Read under the world
lock, like every other read there.

Optional, also opt-in: `COPUSH_PLACE="x,y,yaw_deg;x,y,yaw_deg"` moves duck 0, 1, ... to those
spawn poses before their ports open (upstream spaces ducks a fixed 0.5 m apart along y). Leave an
entry empty to keep upstream's placement, e.g. `COPUSH_PLACE=";0,0.25,0"` moves only duck B.

The upstream fix this stands in for is ~15 lines in `Handler.dispatch` (see docs/archive/WEEK1_STATUS.md).
"""
from __future__ import annotations

import socketserver
import sys

_TARGET = "mjlab_microduck.sim.body_server"


def _is_body_server() -> bool:
    argv = getattr(sys, "orig_argv", None) or sys.argv
    return _TARGET in argv or any(a.endswith("body_server.py") for a in argv)


def _objects(world) -> dict:
    import mujoco

    model, data = world.model, world.data
    out = {}
    with world.lock:
        for joint in range(model.njnt):
            if model.jnt_type[joint] != mujoco.mjtJoint.mjJNT_FREE:
                continue
            name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint) or ""
            if name.endswith("trunk_base_freejoint"):
                continue  # a duck, which its own port already reports
            body = int(model.jnt_bodyid[joint])
            body_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body) or name
            q = int(model.jnt_qposadr[joint])
            v = int(model.jnt_dofadr[joint])
            out[body_name] = {
                "pos": [float(x) for x in data.qpos[q : q + 3]],
                "quat": [float(x) for x in data.qpos[q + 3 : q + 7]],
                "linvel": [float(x) for x in data.qvel[v : v + 3]],
                "angvel": [float(x) for x in data.qvel[v + 3 : v + 6]],
            }
        sim_time = float(data.time)
    return {"sim_time": sim_time, "objects": out}


def _extend(handler_cls):
    if getattr(handler_cls, "_copush_extended", False) or not hasattr(handler_cls, "dispatch"):
        return handler_cls

    class CoPushHandler(handler_cls):  # type: ignore[misc, valid-type]
        _copush_extended = True

        def dispatch(self, body, request):
            if request.get("op") == "objects":
                return _objects(body.world)
            return super().dispatch(body, request)

    CoPushHandler.__name__ = handler_cls.__name__
    CoPushHandler.__qualname__ = handler_cls.__qualname__
    return CoPushHandler


def _placements() -> dict:
    """`COPUSH_PLACE="x,y,yaw_deg;x,y,yaw_deg"` -> {duck index: (x, y, yaw_rad)}. Empty entries skip."""
    import math
    import os

    raw = os.environ.get("COPUSH_PLACE", "").strip()
    out = {}
    if not raw:
        return out
    for index, entry in enumerate(raw.split(";")):
        entry = entry.strip()
        if not entry:
            continue
        x, y, yaw = (float(v) for v in entry.split(","))
        out[index] = (x, y, math.radians(yaw))
    return out


def _place(body, x: float, y: float, yaw: float) -> None:
    """Move a not-yet-enabled duck. Height and pose stay what the keyframe gave it."""
    import math

    import mujoco

    world = body.world
    with world.lock:
        q = body.trunk
        world.data.qpos[q + 0] = x
        world.data.qpos[q + 1] = y
        world.data.qpos[q + 3 : q + 7] = [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]
        body.remember()  # the hold-until-enabled pose is now this one
        mujoco.mj_forward(world.model, world.data)


def _install() -> None:
    original = socketserver.BaseServer.__init__
    original_serve = socketserver.BaseServer.serve_forever
    placements = _placements()

    def __init__(self, server_address, RequestHandlerClass, *args, **kwargs):
        original(self, server_address, _extend(RequestHandlerClass), *args, **kwargs)

    # Placement happens when a duck's port starts serving: `main()` has placed the duck and set
    # `server.body` by then, and no daemon can have connected (so none has enabled it) yet.
    def serve_forever(self, *args, **kwargs):
        body = getattr(self, "body", None)
        if body is not None and getattr(body, "index", None) in placements:
            x, y, yaw = placements[body.index]
            _place(body, x, y, yaw)
            print(f"== copush: duck {body.index} placed at x={x:.3f} y={y:.3f} yaw={yaw:.3f}",
                  file=sys.stderr, flush=True)
        return original_serve(self, *args, **kwargs)

    socketserver.BaseServer.__init__ = __init__
    socketserver.BaseServer.serve_forever = serve_forever
    print("== copush: body server extended with {\"op\": \"objects\"}", file=sys.stderr, flush=True)


if _is_body_server():
    _install()
