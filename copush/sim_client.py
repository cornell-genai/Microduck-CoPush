"""Talk to two simulated MicroDucks started by Pollen's `scripts/duck-sim`.

Each duck is two endpoints:

  * its **robotd socket** (`~/.cache/duck-sim/duck-a.sock`), where velocity intents go as JSON-RPC
    `robot.move` notifications. robotd expires an intent ~500 ms after the last one, so a command
    has to be resent at ~10 Hz for as long as it should hold — that is the controller loop's job
    (`copush.runner`), this module just sends.
  * its **body port** (7801 for duck A, 7802 for duck B), the simulator's own TCP protocol. After a
    `hello`, `{"op":"read"}` returns the duck's sensors plus ground truth no robot has: `trunk`
    (world x, y, z), `trunk_z`, `sim_time`, and `imu.quat` / `imu.gravity` (gravity in the trunk
    frame; upright is [0, 0, -1]).

The box (when the scene has one) is read with `{"op":"objects"}`, which only exists when the body
server was launched with `copush/_bodyext` on PYTHONPATH (`scripts/sim_up.sh` does that). Without
it, `state["box"]` is None and `SimClient.box_supported` is False.

Ground truth comes from the simulator, not from robotd's odometry — the point of a twin is to check
the estimate, not to trust it.
"""
from __future__ import annotations

import json
import math
import os
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

from copush.state import DUCKS, STOP, Command, GoalState, State, validate_actions

DEFAULT_STATE_DIR = Path(os.environ.get("DUCK_SIM_STATE", Path.home() / ".cache" / "duck-sim"))
DEFAULT_BASE_PORT = int(os.environ.get("DUCK_SIM_PORT", "7801"))
# state key -> duck-sim name. Duck i is on body port base + i.
DUCK_NAMES = {"duck_a": "duck-a", "duck_b": "duck-b"}
PROTOCOL = 1
JOINTS = 15

START_HINT = (
    "Start two ducks first, e.g.\n"
    "    scripts/sim_up.sh            # headless, 2 ducks\n"
    "or  DUCK_SIM_DUCKS=2 DUCK_SIM_VIEWER=0 $MICRODUCK/scripts/duck-sim"
)


class SimNotRunning(RuntimeError):
    """A duck's robotd socket or body port is not there."""


def quat_to_yaw(quat) -> float:
    """MuJoCo (w, x, y, z) quaternion -> yaw about world +z."""
    w, x, y, z = quat
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


class BodyLink:
    """One connection to a body port (newline-delimited JSON, one answer per request)."""

    def __init__(self, port: int, host: str = "127.0.0.1", timeout: float = 2.0):
        self.port = port
        try:
            self.sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as error:
            raise SimNotRunning(f"no body server on {host}:{port} ({error})") from error
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.file = self.sock.makefile("rw")
        answer = self.request({"op": "hello", "protocol": PROTOCOL, "joints": JOINTS})
        if answer.get("protocol") != PROTOCOL:
            raise SimNotRunning(f"body server on {port} answered hello with {answer!r}")

    def request(self, message: dict) -> dict:
        self.file.write(json.dumps(message) + "\n")
        self.file.flush()
        line = self.file.readline()
        if not line:
            raise SimNotRunning(f"body server on port {self.port} closed the connection")
        return json.loads(line)

    def read(self) -> dict:
        return self.request({"op": "read"})

    def objects(self) -> Optional[dict]:
        """Free-joint objects, or None if the body server has no `objects` op."""
        answer = self.request({"op": "objects"})
        if "error" in answer:
            return None
        return answer

    def close(self) -> None:
        try:
            self.file.close()
            self.sock.close()
        except OSError:
            pass


class RobotdLink:
    """One duck's robotd JSON-RPC socket, used for fire-and-forget notifications."""

    def __init__(self, path: Path, timeout: float = 2.0):
        self.path = path
        if not path.exists():
            raise SimNotRunning(f"no robotd socket at {path}")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        try:
            self.sock.connect(str(path))
        except OSError as error:
            raise SimNotRunning(f"robotd socket {path} refused ({error}): stale socket?") from error
        self._next_id = 1

    def notify(self, method: str, params: dict) -> None:
        # A notification (no "id"): robotd sends no answer, so nothing piles up unread.
        self.sock.sendall((json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n").encode())

    def call(self, method: str, params: dict) -> dict:
        """A request with an id; reads lines until the matching answer."""
        rid = self._next_id
        self._next_id += 1
        self.sock.sendall((json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n").encode())
        buffer = b""
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            chunk = self.sock.recv(65536)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                answer = json.loads(line)
                if answer.get("id") == rid:
                    return answer
        raise TimeoutError(f"no answer to {method} from {self.path}")

    def move(self, command: Command) -> None:
        vx, vy, vyaw = command
        self.notify("robot.move", {"vx": vx, "vy": vy, "vyaw": vyaw})

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


@dataclass
class _Track:
    """Previous sample, for finite-difference velocity."""
    t: Optional[float] = None
    xy: Tuple[float, float] = (0.0, 0.0)


@dataclass
class SimClient:
    """Both ducks (and the box, if any) of one running duck-sim world.

        with SimClient() as sim:
            state = sim.read_state()
            sim.send({"duck_a": (0.3, 0, 0), "duck_b": (0, 0, 0)})
    """

    state_dir: Path = DEFAULT_STATE_DIR
    base_port: int = DEFAULT_BASE_PORT
    goal: Optional[GoalState] = None
    box_name: str = "box"
    host: str = "127.0.0.1"

    bodies: Dict[str, BodyLink] = field(default_factory=dict, init=False)
    robotd: Dict[str, RobotdLink] = field(default_factory=dict, init=False)
    box_supported: bool = field(default=False, init=False)
    last_raw: Dict[str, dict] = field(default_factory=dict, init=False)
    _tracks: Dict[str, _Track] = field(default_factory=dict, init=False)

    # ── lifecycle ────────────────────────────────────────────────────────────

    def connect(self) -> "SimClient":
        problems = []
        for index, key in enumerate(DUCKS):
            name = DUCK_NAMES[key]
            port = self.base_port + index
            try:
                self.robotd[key] = RobotdLink(Path(self.state_dir) / f"{name}.sock")
            except SimNotRunning as error:
                problems.append(f"  {name}: {error}")
            try:
                self.bodies[key] = BodyLink(port, self.host)
            except SimNotRunning as error:
                problems.append(f"  {name}: {error}")
        if problems:
            self.close()
            raise SimNotRunning(
                "a duck is not running:\n" + "\n".join(problems) + "\n" + START_HINT
            )
        self.box_supported = self.bodies["duck_a"].objects() is not None
        return self

    def close(self) -> None:
        for link in list(self.robotd.values()) + list(self.bodies.values()):
            link.close()
        self.robotd.clear()
        self.bodies.clear()

    def __enter__(self) -> "SimClient":
        return self.connect()

    def __exit__(self, *exc) -> None:
        try:
            if self.robotd:
                self.stop()
        finally:
            self.close()

    # ── commands ─────────────────────────────────────────────────────────────

    def send(self, actions) -> dict:
        """Send one `robot.move` per duck. Must be called at ~10 Hz to keep an intent alive."""
        actions = validate_actions(actions)
        for key in DUCKS:
            self.robotd[key].move(actions[key])
        return actions

    def stop(self) -> None:
        for key in DUCKS:
            self.robotd[key].move(STOP)

    def rpc(self, key: str, method: str, params: dict) -> dict:
        return self.robotd[key].call(method, params)

    # ── state ────────────────────────────────────────────────────────────────

    def _velocity(self, key: str, t: float, xy) -> Tuple[float, float]:
        track = self._tracks.setdefault(key, _Track())
        velocity = (0.0, 0.0)
        if track.t is not None and t > track.t:
            dt = t - track.t
            velocity = ((xy[0] - track.xy[0]) / dt, (xy[1] - track.xy[1]) / dt)
        track.t, track.xy = t, (xy[0], xy[1])
        return velocity

    def read_duck(self, key: str) -> dict:
        raw = self.bodies[key].read()
        self.last_raw[key] = raw
        x, y, z = raw["trunk"]
        t = float(raw["sim_time"])
        return {
            "position": (x, y),
            "yaw": quat_to_yaw(raw["imu"]["quat"]),
            "velocity": self._velocity(key, t, (x, y)),
            "z": z,
            "trunk_z": float(raw["trunk_z"]),
            "gravity": tuple(raw["imu"]["gravity"]),
            "sim_time": t,
        }

    def read_box(self) -> Optional[dict]:
        if not self.box_supported:
            return None
        answer = self.bodies["duck_a"].objects()
        if not answer or self.box_name not in answer["objects"]:
            return None
        obj = answer["objects"][self.box_name]
        x, y, z = obj["pos"]
        return {
            "position": (x, y),
            "yaw": quat_to_yaw(obj["quat"]),
            "velocity": (obj["linvel"][0], obj["linvel"][1]),
            "z": z,
            "sim_time": answer["sim_time"],
        }

    def read_state(self) -> State:
        """The shared state dict (copush.state), plus `time` = simulator time in seconds."""
        duck_a = self.read_duck("duck_a")
        duck_b = self.read_duck("duck_b")
        state = {
            "duck_a": duck_a,
            "duck_b": duck_b,
            "box": self.read_box(),
            "goal": self.goal,
            "time": duck_a["sim_time"],
        }
        return state  # type: ignore[return-value]

    def sim_time(self) -> float:
        return float(self.bodies["duck_a"].read()["sim_time"])
