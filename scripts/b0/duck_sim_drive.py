#!/usr/bin/env python3
"""Signed version of `microduck/scripts/duck-sim drive`, for checking B0 findings on the real
robotd controller path (velstand under robotd, duck-sim's body server, backlash scene).

duck-sim's own `drive` reports |displacement| only. This sends the same `robot.move` intent at
10 Hz (robotd expires an intent after 500 ms) and reports travel SIGNED along the duck's initial
heading, lateral drift, and turn, from the simulator's ground truth (body server `read`), not
odometry. Talks to an already running duck-sim; start one first:

    DUCK_SIM_STATE=~/.cache/duck-sim-b0 DUCK_SIM_PORT=7841 DUCK_SIM_DUCKS=1 DUCK_SIM_VIEWER=0 \
        DUCK_SIM_RL=../microduck_rl ../microduck/scripts/duck-sim up

    python3 scripts/b0/duck_sim_drive.py --state ~/.cache/duck-sim-b0 --port 7841 -- -0.3 0 0.2 0
    (pairs of vx vyaw; each run lasts --seconds)
"""
import argparse, json, math, os, socket, time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.expanduser("~/.cache/duck-sim"))
    ap.add_argument("--port", type=int, default=7801, help="body-server port of the duck")
    ap.add_argument("--duck", default="duck-a")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--settle", type=float, default=2.0, help="seconds of zero command between runs")
    ap.add_argument("cmds", nargs="+", type=float, help="vx vyaw [vx vyaw ...]")
    a = ap.parse_args()
    assert len(a.cmds) % 2 == 0, "give vx vyaw pairs"

    body = socket.create_connection(("127.0.0.1", a.port)).makefile("rw")
    body.write(json.dumps({"op": "hello", "protocol": 1, "joints": 15}) + "\n"); body.flush(); body.readline()

    def read():
        body.write('{"op":"read"}\n'); body.flush(); r = json.loads(body.readline())
        w, x, y, z = r["imu"]["quat"]
        return r["trunk"], math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)), r.get("sim_time")

    s = socket.socket(socket.AF_UNIX); s.connect(os.path.join(a.state, f"{a.duck}.sock"))
    f = s.makefile("w")

    def move(vx, vyaw, secs, track=None):
        prev = read()[1]; turned = 0.0
        for _ in range(int(round(secs * 10))):
            f.write(json.dumps({"jsonrpc": "2.0", "method": "robot.move",
                                "params": {"vx": vx, "vy": 0.0, "vyaw": vyaw}}) + "\n"); f.flush()
            time.sleep(0.1)
            yaw = read()[1]
            turned += math.atan2(math.sin(yaw - prev), math.cos(yaw - prev)); prev = yaw
        return turned

    for vx, vyaw in zip(a.cmds[::2], a.cmds[1::2]):
        move(0.0, 0.0, a.settle)
        (p0, yaw0, t0) = read()
        turned = move(vx, vyaw, a.seconds)
        (p1, _, t1) = read()
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        along = dx * math.cos(yaw0) + dy * math.sin(yaw0)
        lateral = -dx * math.sin(yaw0) + dy * math.cos(yaw0)
        sim_dt = (t1 - t0) if (t0 is not None and t1 is not None) else a.seconds
        print(f"vx={vx:+.2f} vyaw={vyaw:+.2f}: along heading {along:+.3f} m ({along / sim_dt:+.3f} m/s), "
              f"lateral {lateral:+.3f} m, turned {math.degrees(turned):+.0f} deg "
              f"({math.degrees(turned) / sim_dt:+.1f} deg/s), trunk z {p1[2]:.3f}, sim {sim_dt:.1f} s")
    move(0.0, 0.0, 0.5)


if __name__ == "__main__":
    main()
