#!/usr/bin/env python3
"""Compare PPO policies on a stage's fixed test set, per box angle side, with turning and idling metrics.

    scripts/rl.sh scripts/rl/compare_policies.py --test-set experiments/test_sets/stage1.json \
        --config experiments/stage1-random-box-pose/config.yaml \
        --policy stage1=runs/stage1-random-box-pose/model.zip --policy d2=runs/.../model.zip@partner \
        --out experiments/stage1b-turn-direction-fix/results

Every policy runs one deterministic episode per start under the --config env (its reward only
changes the returns, which this script does not compare). A policy spec ending in @own or @partner is
decentralized (copush.decentral: the shared policy once per duck, without / with the partner in view).
After @partner, @chirp:<interval_s>:<direction_noise_deg>[:<distance_noise>] turns on chirps for that
policy only (copush.chirp; the distance is heard when the third number is given), for example
    --policy d2_chirp=runs/decentral-p2-d2/model.zip@partner@chirp:2:30
and a final @trueheading fills in the exact partner heading every step, @heldheading the true heading at each
chirp, held until the next one (both diagnostics).
Per episode:
    turn before push   box rotation (deg, > 0 the way the start needs: toward aiming the push face
                       at the target) done before the box has made PUSH_M of progress toward the target
    total turn         the same, over the whole episode; `needed` is the rotation that aims the push
                       face at the target (copush diagnose_turn.needed)
    overshoot          the episode ends with the box farther from the target than it started
    idle               commanded forward speed below IDLE_VX for both ducks; box path length; episodes
                       whose box moved less than STILL_M net (standing still / wandering)
    cooperation        fraction of steps where both ducks touch the box; lazy-duck episodes, where one
                       duck has less than LAZY_SHARE of the box contact time
Writes <out>/comparison.md and <out>/comparison.json.

--workers N      evaluate each policy's starts on N worker processes (the starts are dealt out round robin, each
                 worker builds its env and loads the policy once), one policy after another, and report the wall
                 time per policy (also in comparison.json as wall_s). The results are identical to the sequential
                 run (every episode is seeded by its start). Without it, one process per policy, as before.
@standstill      (last tag) run that policy with the stand-still action on (env.stand_still: a commanded forward speed
                 below the threshold holds that duck on velstand at zero speed); the other policies run without it.
Per episode the hold state is also recorded: hold_a_frac / hold_b_frac (share of steps a duck is held),
both_hold_steps, one_hold_steps (exactly one duck held), hold_a_alone / hold_b_alone (which duck holds while the
other does not), rot_one_hold_deg (box rotation toward the needed direction during those steps) and max_pivot_run
(the longest run of steps with exactly one duck held). Scripted controllers such as pivot_push hold too.
@sample:K        (the very last tag, after @standstill) SAMPLE the policy's actions from its Gaussian instead of using
                 the mean; K is the sampling seed (torch is seeded per episode from K and the episode seed)
--max-steps N    the episode time limit in env steps (the config's, 100, when not given); 150 is a diagnostic only
--baseline NAME  a scripted controller (stand, random, push_forward, push_steer, pivot_push) instead of a model.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from multiprocessing import Pool

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copush.experiments import load_stage, load_test_set, repo_path  # noqa: E402

PUSH_M, IDLE_VX, STILL_M, LAZY_SHARE = 0.20, 0.05, 0.10, 0.20
SIDES = ("< -15", "-15 to +15", "> +15")


def side_of(dyaw: float) -> str:
    return SIDES[0] if dyaw < -15 else (SIDES[2] if dyaw > 15 else SIDES[1])


def _run(job):
    cfg_path, ts_path, name, spec, *rest = job
    only = rest[0] if rest else None                 # with --workers: the start indices this worker evaluates
    max_steps = rest[1] if len(rest) > 1 else None   # --max-steps: the episode time limit
    from copush.env import CoPushEnv, action_to_cmd
    from test_set import make_act_factory
    from copush.state import wrap_angle
    from diagnose_turn import needed
    _, cfg = load_stage(cfg_path)
    if max_steps:
        cfg["env"]["max_steps"] = int(max_steps)
    if isinstance(spec, dict) and spec.get("standstill"):
        cfg["env"]["stand_still"] = {**cfg["env"]["stand_still"], "enabled": True}
    ch = spec["decentral"].get("chirp") if isinstance(spec, dict) and spec.get("decentral") else None
    if ch:
        cfg["chirp"] = {**cfg["chirp"], "enabled": True, **ch}
    starts = load_test_set(ts_path)["starts"]
    need = {n["id"]: n for n in needed(cfg, starts)}
    make_act = make_act_factory(name, spec)
    env = CoPushEnv(cfg, split="eval")
    seed0 = cfg["env"]["heldout_seeds"][0]
    out = []
    for i, s in enumerate(starts):
        if only is not None and i not in only:
            continue
        act = make_act(env, seed0 + i)
        obs, _ = env.reset(seed=seed0 + i, options={"box": s})
        st = env.state
        d0, yaw, pos = st["box_to_target"], st["box"]["yaw"], st["box"]["position"]
        p0 = pos
        sign = 1.0 if need[s["id"]]["aim_deg"] >= 0 else -1.0
        turned = before = path_len = 0.0
        pushed, idle, n, both = False, 0, 0, 0
        hold_a = hold_b = both_hold = one_hold = a_alone = b_alone = run = max_run = 0
        rot_one = 0.0
        touch = {"duck_a": 0.0, "duck_b": 0.0}
        while True:
            a = act(obs)
            c = action_to_cmd(a)
            idle += c["A"][0] < IDLE_VX and c["B"][0] < IDLE_VX
            obs, _, te, tr, info = env.step(a)
            st = env.state
            dyaw = math.degrees(wrap_angle(st["box"]["yaw"] - yaw))
            turned += dyaw
            yaw = st["box"]["yaw"]
            ha, hb = env.hold["duck_a"], env.hold["duck_b"]            # held on velstand during this step
            hold_a, hold_b, both_hold = hold_a + ha, hold_b + hb, both_hold + (ha and hb)
            if ha != hb:                                               # one duck holds while the other works
                one_hold += 1
                a_alone, b_alone = a_alone + ha, b_alone + hb
                rot_one += sign * dyaw
                run += 1
                max_run = max(max_run, run)
            else:
                run = 0
            path_len += math.dist(pos, st["box"]["position"])
            pos = st["box"]["position"]
            n += 1
            both += all(info["contact_time"][d] > 0 for d in touch)
            for d in touch:
                touch[d] += info["contact_time"][d]
            if not pushed and d0 - st["box_to_target"] >= PUSH_M:
                pushed, before = True, sign * turned
            if te or tr:
                break
        es = info["episode_stats"]
        out.append({"id": s["id"], "side": side_of(s["dyaw"]), "reason": es["reason"],
                    "fell": any(es["fell"].values()), "box_lost": es["reason"] in ("box_lost", "box_tipped"),
                    "push_share_a": es["push_share"]["duck_a"],
                    "contact_share_a": es["contact_share"]["duck_a"], "cooperative": es["cooperative"],
                    "cooperative_threshold": es["cooperative_threshold"], "flags": sorted({f.split(":")[0] for f in es["flags"]}),
                    "needed_deg": abs(need[s["id"]]["aim_deg"]), "turn_before_push": before if pushed else sign * turned,
                    "reached_push": pushed, "total_turn": sign * turned, "overshoot": st["box_to_target"] > d0,
                    "idle_frac": idle / n, "box_path_m": path_len, "box_net_m": math.dist(p0, pos),
                    "steps": es["steps"], "final_dist": es["final_dist"], "both_touch_frac": both / n,
                    "lazy": min(touch.values()) < LAZY_SHARE * max(1e-9, sum(touch.values())),
                    "hold_a_frac": hold_a / n, "hold_b_frac": hold_b / n, "both_hold_steps": int(both_hold),
                    "one_hold_steps": one_hold, "hold_a_alone": int(a_alone), "hold_b_alone": int(b_alone),
                    "rot_one_hold_deg": rot_one, "max_pivot_run": max_run})
    return name, out


def _pct(rows, key) -> str:
    return f"{sum(bool(r[key]) for r in rows)}/{len(rows)}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="the env config the episodes run under")
    p.add_argument("--test-set", required=True)
    p.add_argument("--policy", action="append", default=[], help="name=path/to/model.zip")
    p.add_argument("--baseline", action="append", default=[], help="a scripted controller name")
    p.add_argument("--workers", type=int, default=0, help="processes per policy (one start per task); 0 = one process per policy")
    p.add_argument("--max-steps", type=int, default=None, help="episode time limit in env steps (diagnostics, e.g. 150)")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    jobs = []
    for spec in args.policy:
        name, path = spec.split("=", 1)
        dc = None
        smp = re.search(r"@sample:(\d+)$", path)
        if smp:
            path = path[: smp.start()]
        stand = path.endswith("@standstill")
        if stand:
            path = path[: -len("@standstill")]
        heading = "zero"
        for tag, mode in (("@trueheading", "true"), ("@heldheading", "true_held")):
            if path.endswith(tag):
                path, heading = path[: -len(tag)], mode
        chirp = re.search(r"@chirp:([\d.]+):([\d.]+)(?::([\d.]+))?$", path)
        if chirp:
            path = path[: chirp.start()]
        for tag in ("@own", "@partner"):
            if path.endswith(tag):
                path, dc = path[: -len(tag)], {"include_partner": tag == "@partner"}
        if chirp:
            if not (dc and dc["include_partner"]):
                p.error(f"{name}: @chirp needs @partner")
            dc["chirp"] = {"interval_s": float(chirp[1]), "direction_noise_deg": float(chirp[2]),
                           "heading": heading,
                           "distance": chirp[3] is not None, **({"distance_noise": float(chirp[3])} if chirp[3] else {})}
        if os.path.exists(repo_path(path)):
            jobs.append((args.config, args.test_set, name,
                         {"path": path, **({"decentral": dc} if dc else {}), **({"standstill": True} if stand else {}),
                          **({"sample": int(smp[1])} if smp else {})}
                         if (dc or stand or smp) else path))
        else:
            print(f"skipping {name}: {path} not found")
    jobs += [(args.config, args.test_set, b, None) for b in args.baseline]
    if args.max_steps:
        jobs = [j + (None, args.max_steps) for j in jobs]
    walls = {}
    n = len(load_test_set(args.test_set)["starts"])
    if args.workers > 1:
        res = {}
        with Pool(args.workers) as pool:
            for job in jobs:
                t0 = time.time()
                parts = pool.map(_run, [job[:4] + (set(range(w, n, args.workers)), args.max_steps) for w in range(args.workers)])
                res[job[2]] = sorted((r for _, part in parts for r in part), key=lambda r: r["id"])
                walls[job[2]] = round(time.time() - t0, 1)
                print(f"{job[2]}: {n} starts on {args.workers} workers in {walls[job[2]]} s", flush=True)
    else:
        with Pool(len(jobs)) as pool:
            res = dict(pool.map(_run, jobs))
        res = {j[2]: res[j[2]] for j in jobs}
    os.makedirs(repo_path(args.out), exist_ok=True)
    with open(os.path.join(repo_path(args.out), "comparison.json"), "w") as f:
        json.dump({"test_set": args.test_set, "config": args.config, "wall_s": walls, "episodes": res}, f, indent=1)

    md = [f"# Policy comparison on {args.test_set}", "",
          f"One deterministic episode per start, env from `{args.config}`. Success is compared, not return.", "",
          "## Success by box angle side", "", "| policy | overall | " + " | ".join(f"{s} deg" for s in SIDES) + " |",
          "|---|---|---|---|---|"]
    for name, rows in res.items():
        cells = [f"{sum(r['reason'] == 'success' for r in rows if r['side'] == s)}/{sum(r['side'] == s for r in rows)}"
                 for s in SIDES]
        ok = sum(r["reason"] == "success" for r in rows)
        md.append(f"| {name} | {100 * ok / len(rows):.0f}% ({ok}/{len(rows)}) | " + " | ".join(cells) + " |")
    md += ["", f"## Long-turn starts (> +15 deg): turning", "",
           f"Turn before push = rotation toward the needed direction before the box has made {PUSH_M:.2f} m of "
           "progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.", "",
           "| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |",
           "|---|---|---|---|---|---|"]
    for name, rows in res.items():
        h = [r for r in rows if r["side"] == SIDES[2]]
        tb = [r["turn_before_push"] for r in h]
        md.append(f"| {name} | {np.mean([r['needed_deg'] for r in h]):.0f} | {np.mean(tb):.0f} ({min(tb):.0f} to {max(tb):.0f}) | "
                  f"{np.mean([r['total_turn'] for r in h]):.0f} | {_pct(h, 'reached_push')} | "
                  f"{sum(r['reason'] == 'success' for r in h)}/{len(h)} |")
    md += ["", f"## Failure modes and idling (all {n} starts)", "",
           f"Idle = steps where both ducks are commanded below {IDLE_VX} m/s. Still = the box ends less than {STILL_M} m "
           "from where it started.", "",
           f"Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under {LAZY_SHARE:.0%} "
           "of the box contact time.", "",
           "| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, rows in res.items():
        flags = {}
        for r in rows:
            for f_ in r["flags"]:
                flags[f_] = flags.get(f_, 0) + 1
        sh = [r["push_share_a"] for r in rows if not math.isnan(r["push_share_a"])]
        md.append(f"| {name} | {_pct(rows, 'fell')} | {_pct(rows, 'box_lost')} | {_pct(rows, 'overshoot')} | "
                  f"{sum(r['reason'] == 'timeout' for r in rows)}/{len(rows)} | {100 * np.mean(sh):.0f}% | "
                  f"{100 * np.mean([r['both_touch_frac'] for r in rows]):.0f}% | {_pct(rows, 'lazy')} | "
                  f"{100 * np.mean([r['idle_frac'] for r in rows]):.1f}% | {np.mean([r['box_path_m'] for r in rows]):.2f} | "
                  f"{sum(r['box_net_m'] < STILL_M for r in rows)}/{len(rows)} | {np.mean([r['steps'] for r in rows]):.0f} | "
                  f"{', '.join(f'{k} {v}' for k, v in sorted(flags.items())) or 'none'} |")
    from copush import cooperation
    md += [""] + cooperation.report_lines(
        {name: cooperation.summarize([dict(r, i=r["id"], success=r["reason"] == "success") for r in rows],
                                     rows[0]["cooperative_threshold"]) for name, rows in res.items()})
    with open(os.path.join(repo_path(args.out), "comparison.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
