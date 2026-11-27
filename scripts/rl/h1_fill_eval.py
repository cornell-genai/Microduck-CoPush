#!/usr/bin/env python3
"""h1 heavy box: top the four heavy test sets up to 200 starts and re-evaluate on them.

    scripts/rl.sh scripts/rl/h1_fill_eval.py sets      # write experiments/test_sets/stage1_heavy_<k>_200.json (never overwrites)
    scripts/rl.sh scripts/rl/h1_fill_eval.py eval      # frozen L2-s2 and the three h1 picks, three modes, on the four 200 sets
    scripts/rl.sh scripts/rl/h1_fill_eval.py all       # both, in order

The 200-start sets keep the 141 (noisy: 142) starts of the existing heavy sets unchanged (same ids, same episode seeds
10000 + id) and add new starts drawn like the original ones: Latin hypercube box poses over stage 1's range from a new
rng seed, kept only if the box must travel more than 0.507 m to enter the target. Clean, L1 and L2 share their box poses
(as the originals do); noisy has its own, as its original does. Evaluation uses the functions of
run_h1_heavy_finetune.py unchanged. Per-eval results are cached in runs/d2-heavybox-h1/evals200/ (restart-safe).
Writes (new files only) results_200.md, results_200.json, episodes_200.json, targets_200.json in
experiments/d2-heavybox/h1-heavy-finetune/results/.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_h1_heavy_finetune as H  # noqa: E402

C, rp = H.C, H.rp
KEYS = list(H.LIGHT)                                                   # clean, noisy, L1, L2
SET200 = {k: f"experiments/test_sets/stage1_heavy_{k}_200.json" for k in KEYS}
SKEY = {k: f"heavy200_{k}" for k in KEYS}
OUT = os.path.join(H.E, "results")
EVALS200 = "evals200"
SEED_GROUPS = {"clean": 20261127, "noisy": 20261128}                   # new rng seeds (originals: 20261115 and 20261116)
DRAW = 150                                                             # Latin hypercube size per attempt
OTHER_SETS = ["stage1", "stage1_checks", "stage1_noisy_checks", "stage1_large", "stage1_noisy_large", "stage1_L1_large",
              "stage1_L2_large", "stage1_heavy_checks", "rendezvous_check", "rendezvous_large"]
POLS = {"frozen": H.FROZEN, **{f"s{i}": f"runs/d2-heavybox-h1/s{i}/best.zip" for i in (1, 2, 3)}}
for _k in KEYS:
    H.SETS[SKEY[_k]] = (SET200[_k], H.LIGHT[_k][1], True)


def _init200(config):                                                  # runs in each worker (spawn re-imports this module)
    for k in KEYS:
        H.SETS[SKEY[k]] = (SET200[k], H.LIGHT[k][1], True)
    H._init(config)


class Evaluator200(H.Evaluator):
    subdir = EVALS200
    init_fn = staticmethod(_init200)


def pose(s):                                                           # the key cmd_sets uses for the check set
    return (round(s["x"], 3), round(s["y"], 3), round(s["yaw"], 1))


def poses_of(name):
    d = H.load_test_set(f"experiments/test_sets/{name}.json")
    return {pose(s) for s in d["starts"] if all(k in s for k in ("x", "y", "yaw"))}


# ── step 1: the 200-start sets ───────────────────────────────────────────────

def cmd_sets(a) -> int:
    stage, cfg = H.load_stage(H.CONFIG)
    reach, size = stage["h1"]["solo_reach_m"], cfg["target"]["size"]
    _, l2cfg = H.load_stage(H.LIGHT["L2"][1])
    taken = {n: poses_of(n) for n in OTHER_SETS}
    light = {k: H.load_test_set(H.LIGHT[k][0]) for k in KEYS}
    old = {k: H.load_test_set(H.HEAVY[k]) for k in KEYS}
    tg = light["clean"]["target"]
    assert all(light[k]["target"] == tg for k in KEYS)
    shared = [old[k]["starts"] for k in ("clean", "L1", "L2")]
    assert shared[0] == shared[1] == shared[2], "clean, L1 and L2 no longer share their kept starts"
    assert light["clean"]["starts"] == light["L1"]["starts"] == light["L2"]["starts"]
    new, info = {}, {}
    for group, members in (("clean", ("clean", "L1", "L2")), ("noisy", ("noisy",))):
        need = 200 - len(old[members[0]]["starts"])
        seed = SEED_GROUPS[group]
        for attempt in range(20):
            drawn = H.make_test_set(l2cfg, DRAW, seed)
            kept, rejected = [], 0
            for s in drawn:
                if len(kept) == need:
                    break
                if H.target_entry_m(s, tg, size) > reach:
                    kept.append(s)
                else:
                    rejected += 1
            examined = len(kept) + rejected
            if len(kept) < need:
                seed += 1
                continue
            keys = [pose(s) for s in kept]
            clash = {n: sorted(set(keys) & p) for n, p in taken.items() if set(keys) & p}
            if group == "noisy":
                clash.update({"new clean/L1/L2 starts": sorted(set(keys) & {pose(s) for s in new["clean"]})} if set(keys) & {pose(s) for s in new["clean"]} else {})
            if len(set(keys)) != len(keys) or clash:
                print(f"{group}: seed {seed} collides ({clash}); next seed")
                seed += 1
                continue
            break
        else:
            raise SystemExit(f"{group}: no usable seed")
        new[group] = [dict(s, id=200 + i, drawn_id=s["id"]) for i, s in enumerate(kept)]
        info[group] = {"rng_seed": seed, "seed_tried_first": SEED_GROUPS[group], "lhs_size": DRAW, "examined": examined,
                       "rejected": rejected, "kept": len(kept), "needed": need}
        print(group, info[group])
    for k in KEYS:
        g = "noisy" if k == "noisy" else "clean"
        base = old[k]
        starts = base["starts"] + new[g]
        assert len({s["id"] for s in starts}) == len(starts) == 200 and min(s["id"] for s in new[g]) >= 200
        assert all(H.target_entry_m(s, tg, size) > reach for s in starts)
        doc = {key: v for key, v in base.items() if key != "starts"}
        doc.update(stage=base["stage"] + "-200", created=time.strftime("%Y-%m-%d"), n=200, base_set=H.HEAVY[k], light_base_set=H.LIGHT[k][0],
                   removed=None, config=H.CONFIG, filter=f"box centre must travel more than {reach} m to enter the target (target_entry_m)",
                   old_starts=len(base["starts"]), new_starts=len(new[g]), added=info[g],
                   note=(f"{H.HEAVY[k]} (the {len(base['starts'])} heavy-box starts, unchanged: same ids, same episode seeds 10000 + id) plus "
                         f"{len(new[g])} new starts with ids 200 and up, to reach the 200 the repo rule asks for. New box poses: a Latin hypercube "
                         f"of {DRAW} over stage 1's full range (rng seed {info[g]['rng_seed']}), in draw order, keeping only draws whose box centre "
                         f"must travel more than {reach} m to enter the target ({info[g]['rejected']} rejected on the way, {info[g]['kept']} kept; "
                         "drawn_id is the index in the draw). "
                         + ("The noisy set has its own new box poses (as its original has its own), none shared with the clean, L1 and L2 sets. "
                            if k == "noisy" else "Clean, L1 and L2 share these new box poses, as their originals share theirs; only the duck start noise differs. ")
                         + "No new box pose (x, y to 3 decimals, yaw to 1) repeats one in the check set, the light 200-start sets, the other "
                           "stage 1 check and test sets, or the rendezvous sets. Never used in training."),
                   starts=starts)
        doc.pop("removed")
        if os.path.exists(rp(SET200[k])) and not a.force:
            print(f"{SET200[k]} exists; --force to rebuild")
            continue
        H.write_json(SET200[k], doc, indent=1)
        print(f"wrote {SET200[k]}: {len(base['starts'])} old + {len(new[g])} new")
    return 0


# ── steps 2 and 3 ────────────────────────────────────────────────────────────

def quant(xs):
    xs = sorted(xs)

    def q(p):
        k = (len(xs) - 1) * p
        f = int(k)
        c = min(f + 1, len(xs) - 1)
        return xs[f] + (xs[c] - xs[f]) * (k - f)
    return {"n": len(xs), "min": xs[0], "p10": q(.1), "p50": q(.5), "p90": q(.9), "max": xs[-1], "mean": sum(xs) / len(xs)} if xs else {"n": 0}


def cmd_eval(a) -> int:
    stage, cfg = H.load_stage(H.CONFIG)
    th = C.threshold_of(cfg)
    if H.sha256(H.FROZEN) != H.FROZEN_SHA:
        raise SystemExit("frozen policy file is not the official L2-s2")
    H.RUN = "runs/d2-heavybox-h1"
    ev = Evaluator200(H.RUN, H.CONFIG, a.workers)
    t0 = time.time()
    names = H.read_json(os.path.join(OUT, "results.json"))["names"]
    docs = {k: H.load_test_set(SET200[k]) for k in KEYS}
    assert all(len(d["starts"]) == 200 for d in docs.values())
    E = {SKEY[k]: {p: {m: ev(p, POLS[p], SKEY[k], m) for m in H.MODES} for p in POLS} for k in KEYS}
    H.log(f"evals200 done in {(time.time() - t0) / 60:.1f} min")

    # sanity: the old starts must reproduce results/episodes.json exactly
    old = H.read_json(os.path.join(OUT, "episodes.json"))
    repro = {"fields": ["id", "reason", "steps", "contact_share_a", "push_share_a", "fell"], "checked": 0, "different": []}
    for k in KEYS:
        okey, nkey = f"heavy_{k}", SKEY[k]
        for p in POLS:
            for m in H.MODES:
                new = {e["id"]: e for e in E[nkey][p][m]}
                for o in old[okey][p][m]:
                    repro["checked"] += 1
                    if any(new[o["id"]][f] != o[f] for f in repro["fields"]):
                        repro["different"].append([okey, p, m, o["id"]])
    H.log(f"reproduction: {repro['checked']} episodes checked, {len(repro['different'])} different")

    S = {key: {p: {m: H.summarize(e, th) for m, e in v.items()} for p, v in d.items()} for key, d in E.items()}
    picks = [p for p in POLS if p != "frozen"]
    pair = {key: H.paired_all({p: E[key][p]["both"] for p in POLS}, tuple(picks), "frozen", th) for key in E}

    # step 3
    tg0 = docs["clean"]["target"]
    size = cfg["target"]["size"]
    T = cfg["env"]["max_steps"] * cfg["env"]["step_s"]
    reach1, reach2 = H.SPEED_ONE * T, H.SPEED_TWO * T
    targets = {"time_limit_s": T, "speed_one_m_s": H.SPEED_ONE, "speed_two_m_s": H.SPEED_TWO, "one_duck_reach_m": reach1,
               "two_duck_reach_m": reach2, "sets": {}, "h1_success_vs_timeout_centre_m": {}}
    for k in KEYS:
        st = docs[k]["starts"]
        cen = [math.hypot(s["x"] - tg0["x"], s["y"] - tg0["y"]) for s in st]
        ent = [H.target_entry_m(s, tg0, size) for s in st]
        c90, e90 = quant(cen)["p90"], quant(ent)["p90"]
        targets["sets"][SET200[k]] = {
            "n": len(st), "centre_m": quant(cen), "entry_m": quant(ent),
            "two_duck_margin_on_p90_centre": reach2 / c90 - 1, "two_duck_margin_on_p90_entry": reach2 / e90 - 1,
            "one_duck_could_reach_by_centre": sum(c <= reach1 for c in cen), "one_duck_could_reach_by_entry": sum(e <= reach1 for e in ent),
            "two_duck_could_reach_by_centre": sum(c <= reach2 for c in cen), "two_duck_could_reach_by_entry": sum(e <= reach2 for e in ent)}
    cen_of = {k: {s["id"]: math.hypot(s["x"] - tg0["x"], s["y"] - tg0["y"]) for s in docs[k]["starts"]} for k in KEYS}
    for p in picks + ["frozen"]:
        row = {}
        for k in KEYS:
            eps = E[SKEY[k]][p]["both"]
            row[k] = {"success": quant([cen_of[k][e["id"]] for e in eps if e["success"]]),
                      "timeout": quant([cen_of[k][e["id"]] for e in eps if e["reason"] == "timeout"]),
                      "other_failure": quant([cen_of[k][e["id"]] for e in eps if not e["success"] and e["reason"] != "timeout"])}
        pooled = lambda kind: quant([cen_of[k][e["id"]] for k in KEYS for e in E[SKEY[k]][p]["both"]      # noqa: E731
                                     if (e["success"] if kind == "success" else e["reason"] == "timeout")])
        row["all_four_sets"] = {"success": pooled("success"), "timeout": pooled("timeout")}
        targets["h1_success_vs_timeout_centre_m"][p] = row
    H.write_json(os.path.join(OUT, "targets_200.json"), targets, indent=1)

    doc = {"config": H.CONFIG, "box_mass": cfg["box"]["mass"], "max_steps": cfg["env"]["max_steps"], "threshold": th,
           "frozen": H.FROZEN, "picks": {p: POLS[p] for p in picks}, "names": names, "sets": SET200, "eval_cache": f"{H.RUN}/{EVALS200}",
           "reproduction_of_141_start_results": repro, "summary": S, "paired_vs_frozen": pair, "wall_min_this_run": (time.time() - t0) / 60}
    H.write_json(os.path.join(OUT, "results_200.json"), doc, indent=1)
    keep = ("id", "reason", "steps", "contact_share_a", "push_share_a", "fell", "contact_impulse", "push_impulse")
    H.write_json(os.path.join(OUT, "episodes_200.json"),
                 {key: {p: {m: [{f: e.get(f) for f in keep} for e in v] for m, v in d.items()} for p, d in dd.items()} for key, dd in E.items()},
                 separators=(",", ":"))

    L = ["# h1 heavy-box fine-tune: results on the 200-start heavy sets", "",
         "Written by `scripts/rl/h1_fill_eval.py`. Same evaluation as `results.md` (deterministic, one episode per start, box "
         f"{cfg['box']['mass']} kg, {cfg['env']['max_steps']}-step limit, reward {cfg['reward']['version']}), on "
         "`experiments/test_sets/stage1_heavy_<set>_200.json`: the 141 (noisy: 142) starts of the earlier heavy sets, unchanged, plus new starts "
         f"to reach 200. Cooperative success = task success and each duck at least {round(100 * th)}% of the pushing; 95% Wilson intervals. "
         "The 141-start tables in `results.md` stay as the first report (superseded by these for any README or decision).", "",
         "## Old starts reproduce", "",
         f"The old starts inside each 200-start set were compared with `episodes.json` ({', '.join(repro['fields'])}) for every policy and mode: "
         f"{repro['checked']} episodes checked, {len(repro['different'])} different.", "", "## Results", ""]
    for k in KEYS:
        key = SKEY[k]
        L += H.table(f"Test set: {k}, heavy box, 200 starts (`{SET200[k]}`)", {names[p]: S[key][p]["both"] for p in POLS},
                     {names[p]: {m: S[key][p][m] for m in ("A_idle", "B_idle")} for p in POLS})
        pr = pair[key]
        L += [f"h1 (the {len(picks)} seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success {H.pp(pr['task'])}. "
              f"Cooperative success (contact impulse) {H.pp(pr['cooperative'])}. Cooperative success (along the line) {H.pp(pr['cooperative_push'])}.", ""]
    L += ["## Where the box starts (distance to the target)", "",
          f"Two ducks at their open-loop speed ({H.SPEED_TWO} m/s) cover {reach2:.3f} m in {T:.0f} s, one duck ({H.SPEED_ONE} m/s) {reach1:.3f} m. "
          "Margin = two-duck reach divided by the 90th percentile distance, minus 1. Distances in metres, all 200 starts of each set.", "",
          "| set | distance | min | p10 | p50 | p90 | max | two-duck margin over p90 | one duck could reach |", "|---|---|---|---|---|---|---|---|---|"]
    for k in KEYS:
        t = targets["sets"][SET200[k]]
        for nm, kk, mg, one in (("to target centre", "centre_m", "two_duck_margin_on_p90_centre", "one_duck_could_reach_by_centre"),
                                ("to enter the target", "entry_m", "two_duck_margin_on_p90_entry", "one_duck_could_reach_by_entry")):
            q = t[kk]
            L.append(f"| {k} | {nm} | {q['min']:.3f} | {q['p10']:.3f} | {q['p50']:.3f} | {q['p90']:.3f} | {q['max']:.3f} | "
                     f"{100 * t[mg]:+.0f}% | {t[one]} of {t['n']} |")
    L += ["", "Box start to target centre for the h1 picks, both ducks (m; mean and 90th percentile, number of starts):", "",
          "| policy | set | successes | timeouts |", "|---|---|---|---|"]
    f = lambda q: "none" if not q["n"] else f"mean {q['mean']:.3f}, p90 {q['p90']:.3f} (n={q['n']})"   # noqa: E731
    for p in picks:
        for k in KEYS + ["all_four_sets"]:
            r = targets["h1_success_vs_timeout_centre_m"][p][k]
            L.append(f"| {names[p]} | {k.replace('_', ' ')} | {f(r['success'])} | {f(r['timeout'])} |")
    open(rp(os.path.join(OUT, "results_200.md")), "w").write("\n".join(L) + "\n")
    H.log(f"results_200 written to {OUT}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("sets", "eval", "all"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    rc = cmd_sets(a) if a.cmd in ("sets", "all") else 0
    return rc or (cmd_eval(a) if a.cmd in ("eval", "all") else 0)


if __name__ == "__main__":
    sys.exit(main())
