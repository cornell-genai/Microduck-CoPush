#!/usr/bin/env python3
"""Two-duck CoPush sim: interactive viewer, scripted headless runs, offscreen video.

Launch through scripts/copush.sh (it picks mjpython for --viewer on macOS):

    scripts/copush.sh --viewer                                    # drive both ducks from the terminal
    scripts/copush.sh --headless --duration 15 --script push_forward
    scripts/copush.sh --headless --duration 15 --script push_hold --record
    scripts/copush.sh --viewer --box 0.4,0,90 --target 1.2,0,90   # flags override configs/copush.yaml

Scripts (both ducks): walk to the box on velstand, switch to Shoe Push at first box contact, then
  push_forward  push straight ahead (vx 0.2, no steering)
  push_hold     steer with copush.controllers.HeadingHoldPush toward the target (5 Hz)

Keys are read in the TERMINAL, not the viewer window (viewer letter keys fire MuJoCo shortcuts):
  W/S A/D  duck A faster/slower, turn left/right    I/K J/L  same for duck B
  1 / 2    toggle A / B policy (velstand <-> shoepush)
  space    stop both     X  stop A     M  stop B
  R        reset scene   N  note marker in events.log   Q  quit
A movement key during a script hands control to the keyboard.

Every run writes runs/<timestamp>/ (config.yaml, state.csv, events.log, notes.md, video.mp4).
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from copush.config import add_config_args, config_from_args  # noqa: E402
from copush.controllers import HeadingHoldPush  # noqa: E402
from copush.rewards import REWARDS, RewardMonitor  # noqa: E402
from copush.rundir import RunDir  # noqa: E402
from copush.sim import CONTROL_DT, DUCKS, CoPushSim  # noqa: E402
from copush.upstream import infer_policy  # noqa: E402

LABEL = {"duck_a": "A", "duck_b": "B"}
APPROACH_VX = 0.2      # velstand: walks from rest at >= 0.15 (B0 §2)
PUSH_VX = 0.2          # Shoe Push was trained on 0.1-0.3
HOLD_EVERY = 5         # HeadingHoldPush at 5 Hz, as in B0 Test 3


class PushScript:
    """Each duck: velstand at APPROACH_VX until it first touches the box, then Shoe Push."""

    def __init__(self, sim: CoPushSim, hold: bool):
        self.sim, self.hold = sim, hold
        self.reset()

    def reset(self) -> None:
        self.phase = {d: "approach" for d in DUCKS}
        self.cmd = {d: (APPROACH_VX, 0.0, 0.0) for d in DUCKS}
        self.ctl = {}
        self.k = 0
        if self.hold:
            cfg = self.sim.cfg
            box0 = (cfg["box"]["x"], cfg["box"]["y"])
            line = math.atan2(cfg["target"]["y"] - box0[1], cfg["target"]["x"] - box0[0])
            self.ctl = {d: HeadingHoldPush(vx=PUSH_VX, duck=d, line_yaw=line, line_origin=box0) for d in DUCKS}

    def commands(self, state: dict) -> dict:
        for d in DUCKS:
            if self.phase[d] == "approach" and state["contact"][d]["in_contact"]:
                self.phase[d] = "push"
                self.sim.set_policy(d, "shoepush")
                self.cmd[d] = (PUSH_VX, 0.0, 0.0)
            if self.phase[d] == "push" and self.hold and self.k % HOLD_EVERY == 0:
                self.cmd[d] = tuple(self.ctl[d].get_actions(state)[d])
        self.k += 1
        return {LABEL[d]: self.cmd[d] for d in DUCKS}

    def label(self) -> str:
        return "/".join(self.phase[d] for d in DUCKS)


class Keyboard:
    MOVE = {"w": ("duck_a", 0, +1), "s": ("duck_a", 0, -1), "a": ("duck_a", 2, +1), "d": ("duck_a", 2, -1),
            "i": ("duck_b", 0, +1), "k": ("duck_b", 0, -1), "j": ("duck_b", 2, +1), "l": ("duck_b", 2, -1)}

    def __init__(self, kb: dict):
        self.kb = kb
        self.stop()

    def stop(self, duck=None) -> None:
        if duck is None:
            self.cmd = {d: [0.0, 0.0, 0.0] for d in DUCKS}
        else:
            self.cmd[duck] = [0.0, 0.0, 0.0]

    def move(self, key: str) -> None:
        duck, axis, sign = self.MOVE[key]
        kb, c = self.kb, self.cmd[duck]
        if axis == 0:
            c[0] = round(min(kb["vx_max"], max(kb["vx_min"], c[0] + sign * kb["vx_step"])), 4)
        else:
            c[2] = round(min(kb["vyaw_max"], max(-kb["vyaw_max"], c[2] + sign * kb["vyaw_step"])), 4)

    def commands(self) -> dict:
        return {LABEL[d]: tuple(self.cmd[d]) for d in DUCKS}


def contact_str(c: dict) -> str:
    if not c["by_part"]:
        return "no contact"
    return "touch " + ",".join(sorted(c["by_part"], key=c["by_part"].get, reverse=True))


def status_line(st: dict, reward: float, cum: float) -> str:
    parts = [f"t {st['t']:6.2f}", f"box->target {st['box_to_target']:.2f} m",
             f"inside {'YES' if st['inside'] else 'no '}"]
    for d in DUCKS:
        s, c = st[d], st["contact"][d]
        cmd = s["cmd"]
        parts.append(f"{LABEL[d]} {s['policy']:<8} cmd({cmd[0]:+.2f},{cmd[2]:+.2f}) {contact_str(c)}"
                     + (" FALLEN" if s["fallen"] else ""))
    parts.append(f"R {cum:+.2f}")
    return " | ".join(parts)


def overlay(st: dict, reward: float, cum: float) -> list:
    lines = [f"t {st['t']:5.2f} s   box->target {st['box_to_target']:.2f} m   "
             f"yaw err {math.degrees(st['yaw_error']):.0f} deg   inside {'YES' if st['inside'] else 'no'}"]
    for d in DUCKS:
        s, c = st[d], st["contact"][d]
        lines.append(f"{LABEL[d]}: {s['policy']}  cmd vx {s['cmd'][0]:+.2f} vyaw {s['cmd'][2]:+.2f}  "
                     f"{contact_str(c)}  (total {c['total']:.2f} N.s)" + ("  FALLEN" if s["fallen"] else ""))
    lines.append(f"reward {reward:+.3f}   cumulative {cum:+.2f}")
    return lines


class Summary:
    """What notes.md's Outcome section and the final terminal block report (current episode)."""

    def __init__(self):
        self.reset(None)

    def reset(self, st) -> None:
        self.start, self.last, self.min_dist, self.inside_s = st, st, math.inf, 0.0
        self.falls, self.switches, self.flags = [], [], {}

    def step(self, st) -> None:
        if self.start is None:
            self.start = st
        self.last = st
        self.min_dist = min(self.min_dist, st["box_to_target"])
        self.inside_s += CONTROL_DT if st["inside"] else 0.0

    def markdown(self, cum: float, wall: float, episodes: int) -> str:
        s0, s1 = self.start, self.last
        if s0 is None:
            return "No steps were run."
        b0, b1 = s0["box"]["position"], s1["box"]["position"]
        travel = math.dist(b0, b1)
        out = [f"- Simulated {s1['t']:.2f} s in {wall:.1f} s wall time ({s1['t'] / max(wall, 1e-9):.1f}x real time)"
               + (f"; {episodes - 1} reset(s), numbers are for the last episode" if episodes > 1 else ""),
               f"- Box: ({b0[0]:.3f}, {b0[1]:+.3f}) -> ({b1[0]:.3f}, {b1[1]:+.3f}), moved {travel:.3f} m, "
               f"turned {math.degrees(math.atan2(math.sin(s1['box']['yaw'] - s0['box']['yaw']), math.cos(s1['box']['yaw'] - s0['box']['yaw']))):+.0f} deg",
               f"- Box to target: {s0['box_to_target']:.3f} -> {s1['box_to_target']:.3f} m (closest {self.min_dist:.3f} m); "
               f"yaw error at end {math.degrees(s1['yaw_error']):.0f} deg; inside at end: {'yes' if s1['inside'] else 'no'} "
               f"({self.inside_s:.2f} s inside in total)",
               "- Falls: " + (", ".join(self.falls) if self.falls else "none"),
               "- Policy switches: " + (", ".join(self.switches) if self.switches else "none")]
        for d in DUCKS:
            c = s1["contact"][d]
            tot = c["total"]
            shares = ", ".join(f"{g} {100 * v / tot:.0f}%" for g, v in sorted(c["total_by_part"].items(), key=lambda kv: -kv[1])) if tot else "no box contact"
            out.append(f"- Duck {LABEL[d]}: box contact {tot:.2f} N.s ({shares}); ended at "
                       f"({s1[d]['position'][0]:.3f}, {s1[d]['position'][1]:+.3f}), heading {math.degrees(s1[d]['yaw']):+.0f} deg")
        out.append(f"- Cumulative reward: {cum:+.3f}")
        out.append("- Suspicious flags: " + (", ".join(f"{k} x{v}" for k, v in sorted(self.flags.items())) or "none"))
        return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--viewer", action="store_true", help="MuJoCo viewer + terminal keys (real time)")
    mode.add_argument("--headless", action="store_true", help="no window, as fast as possible (default)")
    p.add_argument("--duration", type=float, help="seconds of sim time (headless default 15; viewer: until Q)")
    p.add_argument("--script", choices=("push_forward", "push_hold"), help="scripted ducks instead of keys")
    p.add_argument("--record", action="store_true", help="write runs/<ts>/video.mp4 (offscreen, 25 fps)")
    p.add_argument("--reward", choices=sorted(REWARDS), default="progress")
    p.add_argument("--quiet", action="store_true", help="no status lines (headless)")
    add_config_args(p)
    args = p.parse_args(argv)
    duration = args.duration if args.duration is not None else (None if args.viewer else 15.0)

    cfg = config_from_args(args)
    sim = CoPushSim(cfg)
    monitor = RewardMonitor(REWARDS[args.reward])
    run = RunDir(cfg, reward_name=args.reward, video=args.record)
    print(f"run dir: {os.path.relpath(run.path, os.getcwd())}")
    script = PushScript(sim, hold=args.script == "push_hold") if args.script else None
    keys = Keyboard(cfg["keyboard"])
    video = None
    if args.record:
        from copush.video import VideoRecorder
        video = VideoRecorder(sim.m, run.file("video.mp4"))
    summary = Summary()
    episode, cum, reward = 1, 0.0, 0.0
    status_every = 0.5 if args.viewer else 1.0

    viewer = term = None
    if args.viewer:
        import mujoco.viewer
        viewer = mujoco.viewer.launch_passive(sim.m, sim.d, show_left_ui=False, show_right_ui=False)
        viewer.cam.lookat[:] = [cfg["box"]["x"], 0.0, 0.05]
        viewer.cam.distance, viewer.cam.azimuth, viewer.cam.elevation = 1.8, 40.0, -30.0
        term = infer_policy().TerminalInput().__enter__()
        print("keys (in this terminal): W/S A/D duck A, I/K J/L duck B, 1/2 policy, space/X/M stop, "
              "R reset, N note, Q quit")

    def say(text: str) -> None:
        print(("\r\033[K" if viewer else "") + text, flush=True)

    def log_events() -> None:
        for t, kind, msg in sim.pop_events():
            run.event(t, kind, msg)
            say(f"[{kind}] t={t:.2f} {msg}")
            if kind == "fall":
                summary.falls.append(f"{msg} at {t:.2f} s")
            elif kind == "policy":
                summary.switches.append(f"{msg} at {t:.2f} s")

    sim.pop_events()                     # the constructor's reset
    st = sim.get_state()
    run.event(0.0, "start", f"episode 1, script={args.script or 'keyboard'}, reward={args.reward}")
    wall0 = time.perf_counter()
    sim_wall0, last_sync, last_status = wall0, 0.0, -1.0
    try:
        while True:
            # ── input ──
            if term is not None:
                for key in term.get_keys():
                    if key == "q":
                        raise KeyboardInterrupt
                    if key in Keyboard.MOVE:
                        if script is not None:
                            script = None
                            keys.cmd = {d: list(sim.pol[d].cmd) for d in DUCKS}
                            say("[keys] manual control (script stopped)")
                        keys.move(key)
                    elif key in ("1", "2"):
                        sim.toggle_policy("A" if key == "1" else "B")
                    elif key == " ":
                        keys.stop()
                        script = None
                    elif key == "x":
                        keys.stop("duck_a")
                    elif key == "m":
                        keys.stop("duck_b")
                    elif key == "n":
                        k = run.note_marker(sim.t)
                        say(f"[note] marker #{k} at t={sim.t:.2f} (describe it in {os.path.relpath(run.file('notes.md'))})")
                    elif key == "r":
                        with viewer.lock():
                            st = sim.reset()
                        episode += 1
                        monitor.reset()
                        keys.stop()
                        if script is not None:
                            script.reset()
                        summary.reset(None)
                        cum = 0.0
                        run.event(0.0, "start", f"episode {episode}")
                        sim_wall0 = time.perf_counter()
            # ── control step ──
            cmds = script.commands(st) if script is not None else keys.commands()
            if viewer is not None:
                with viewer.lock():
                    st = sim.step(cmds)
            else:
                st = sim.step(cmds)
            reward, flags = monitor.update(st)
            cum = monitor.cum
            run.log_step(st, reward, cum, episode, script.label() if script else "keyboard")
            summary.step(st)
            log_events()
            for f in flags:
                run.event(st["t"], "SUSPECT", f)
                say(f"[suspect] t={st['t']:.2f} {f}")
                key = f.split(":")[0]
                summary.flags[key] = summary.flags.get(key, 0) + 1
            if video is not None and round(st["t"] / CONTROL_DT) % 2 == 0:
                video.frame(sim.d, st, overlay(st, reward, cum))
            # ── viewer / pacing ──
            if viewer is not None:
                if not viewer.is_running():
                    break
                now = time.perf_counter()
                if now - last_sync > 1 / 60:
                    viewer.sync()
                    last_sync = now
                ahead = (sim_wall0 + st["t"]) - time.perf_counter()
                if ahead > 0:
                    time.sleep(ahead)
                if time.perf_counter() - last_status >= status_every:
                    last_status = time.perf_counter()
                    print("\r\033[K" + status_line(st, reward, cum), end="", flush=True)
            elif not args.quiet and st["t"] - last_status >= status_every - 1e-9:
                last_status = st["t"]
                print(status_line(st, reward, cum), flush=True)
            if duration is not None and st["t"] >= duration - 1e-9:
                break
    except KeyboardInterrupt:
        pass
    finally:
        wall = time.perf_counter() - wall0
        if term is not None:
            term.__exit__(None, None, None)
        if viewer is not None:
            viewer.close()
        if video is not None:
            video.close()
        md = summary.markdown(cum, wall, episode)
        run.close(md)
        print("\n" + md)
        print(f"\nwrote {os.path.relpath(run.path, os.getcwd())}/ (config.yaml, state.csv, events.log, notes.md"
              + (", video.mp4)" if video is not None else ")"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
