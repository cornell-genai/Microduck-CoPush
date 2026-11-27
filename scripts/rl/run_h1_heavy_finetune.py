#!/usr/bin/env python3
"""D2 heavy box, h1: fine-tune the night 5 L2-s2 push policy on a 0.60 kg box (experiments/d2-heavybox/h1-heavy-finetune.yaml).

    caffeinate -is scripts/rl.sh scripts/rl/run_h1_heavy_finetune.py          # the whole run
    scripts/rl.sh scripts/rl/run_h1_heavy_finetune.py --dry-run               # tiny end-to-end test (runs/d2-heavybox-h1-dry/)
    scripts/rl.sh scripts/rl/run_h1_heavy_finetune.py sets                    # write the heavy-box test and check sets (once)
    scripts/rl.sh scripts/rl/run_h1_heavy_finetune.py startcheck              # start-check rejections, light vs heavy box

Steps of the run, in order (experiments/d2-heavybox/h1-heavy-finetune/PLAN.md has the decision rule):
  baseline   frozen L2-s2 on the heavy check set: both ducks, duck A idle, duck B idle
  train      per seed (h1.seeds): scripts/rl/stage.py to 400k duck steps, then the check set; 0 task successes there stops
             the seed. Otherwise on to 2M. Every checkpoint (200k apart) is kept and evaluated on the check set, and the
             pick is the checkpoint with the most cooperative successes (contact impulse; ties: more task successes, then
             the earlier checkpoint)
  solo       each pick on the check set with duck A idle and with duck B idle
  test       frozen L2-s2 and each pick on the four heavy test sets (clean, noisy, L1, L2), three modes each
  forget     frozen L2-s2 and each pick on the LIGHT box (clean set, 100 steps, the original config)
  pipeline   r6 rendezvous then the push policy on rendezvous_large.json with the heavy box: frozen L2-s2 and the best pick
  gifs       the best pick on the heavy L2 test set: two cooperative successes, one failure, one solo test (duck A idle)
Writes <results>/results.json and results.md. Restart-safe: every evaluation is cached in <run dir>/evals/, training
resumes from its last checkpoint.

Idle = that duck's speed command is forced to the lowest value every step, which the stand-still action turns into
standing still. Evaluation: deterministic, one episode per start, episode seed = the set's episode_seed0 (10000 for the
test sets, 20000 for the check set) + the start's id.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from multiprocessing import Pool

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts", "rl")]
os.chdir(ROOT)

from copush import cooperation as C  # noqa: E402
from copush.experiments import copy_box_task, load_stage, load_test_set, make_test_set, target_entry_m  # noqa: E402

CONFIG = "experiments/d2-heavybox/h1-heavy-finetune.yaml"
E = "experiments/d2-heavybox/h1-heavy-finetune"
RUN = "runs/d2-heavybox-h1"
FROZEN = "runs/d2-steering-night5/l2-s2/model.zip"
FROZEN_SHA = "ab82e344b275ce617123cf89b70d998f2dbf9003e7fd8feec437607503dd3366"
R6 = "runs/d2-rendezvous-r6-dock-payout/s1/model.zip"
RV_SET = "experiments/test_sets/rendezvous_large.json"
LIGHT = {"clean": ("experiments/test_sets/stage1_large.json", "experiments/stage1-random-box-pose/config.yaml"),
         "noisy": ("experiments/test_sets/stage1_noisy_large.json", "experiments/d2-steering/noisy-sets/config.yaml"),
         "L1": ("experiments/test_sets/stage1_L1_large.json", "experiments/d2-steering/night5/sets/L1/config.yaml"),
         "L2": ("experiments/test_sets/stage1_L2_large.json", "experiments/d2-steering/night5/sets/L2/config.yaml")}
HEAVY = {k: f"experiments/test_sets/stage1_heavy_{k}_large.json" for k in LIGHT}
CHECK = "experiments/test_sets/stage1_heavy_checks.json"
# set key -> (starts file, env config, heavy box?)
SETS = {**{f"heavy_{k}": (HEAVY[k], LIGHT[k][1], True) for k in LIGHT},
        "check": (CHECK, LIGHT["L2"][1], True),
        "light_clean": (LIGHT["clean"][0], LIGHT["clean"][1], False)}
MODES = ("both", "A_idle", "B_idle")
MODE_LABEL = {"both": "both ducks", "A_idle": "duck B alone (A idle)", "B_idle": "duck A alone (B idle)"}
BUCKETS = ((0.0, 0.10), (0.10, 0.25), (0.25, 0.40), (0.40, 0.5000001))
SPEED_ONE, SPEED_TWO = 0.0195, 0.0357          # open-loop box speed at 0.60 kg (h0 physics.json: 0.195 m and 0.357 m in 10 s)
_W: dict = {}


def rp(p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def read_json(path, default=None):
    try:
        return json.load(open(rp(path)))
    except (OSError, ValueError):
        return default


def write_json(path, obj, **kw):
    os.makedirs(os.path.dirname(rp(path)), exist_ok=True)
    tmp = rp(path) + ".tmp"
    json.dump(obj, open(tmp, "w"), **kw)
    os.replace(tmp, rp(path))


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    os.makedirs(rp(RUN), exist_ok=True)
    open(rp(os.path.join(RUN, "progress.log")), "a").write(line + "\n")


def sha256(path: str) -> str:
    return hashlib.sha256(open(rp(path), "rb").read()).hexdigest()


def set_cfg(key: str, config: str = CONFIG) -> dict:
    """The env config a set is evaluated with: the set's own config (its duck start noise) with the stand-still action
    on, and for the heavy sets the h1 box task (mass, step limit, reward version) copied in."""
    _, cfg_path, heavy = SETS[key]
    _, cfg = load_stage(cfg_path)
    cfg["env"]["stand_still"] = {**cfg["env"]["stand_still"], "enabled": True}
    if heavy:
        copy_box_task(cfg, load_stage(config)[1])
    return cfg


# ── heavy-box sets ───────────────────────────────────────────────────────────

def target_stats(starts, target, size):
    def q(xs, p):
        xs = sorted(xs)
        k = (len(xs) - 1) * p
        f = int(k)
        c = min(f + 1, len(xs) - 1)
        return xs[f] + (xs[c] - xs[f]) * (k - f)
    out = {}
    for name, xs in (("centre_m", [math.hypot(s["x"] - target["x"], s["y"] - target["y"]) for s in starts]),
                     ("entry_m", [target_entry_m(s, target, size) for s in starts])):
        out[name] = {"min": min(xs), "p10": q(xs, .1), "p50": q(xs, .5), "p90": q(xs, .9), "max": max(xs)}
    return out


def cmd_sets(a) -> int:
    stage, cfg = load_stage(CONFIG)
    h = stage["h1"]
    reach, size = h["solo_reach_m"], cfg["target"]["size"]
    T = cfg["env"]["max_steps"] * cfg["env"]["step_s"]
    report = {"time_limit_s": T, "speed_one_m_s": SPEED_ONE, "speed_two_m_s": SPEED_TWO, "solo_reach_m": reach,
              "two_duck_reach_m": SPEED_TWO * T, "sets": {}}
    for k, (path, _) in LIGHT.items():
        doc = load_test_set(path)
        tg = doc["target"]
        keep = [s for s in doc["starts"] if target_entry_m(s, tg, size) > reach]
        st = target_stats(doc["starts"], tg, size)
        report["sets"][path] = {"n": len(doc["starts"]), **st,
                                "solo_reachable_by_entry": sum(target_entry_m(s, tg, size) <= SPEED_ONE * T for s in doc["starts"]),
                                "solo_reachable_by_centre": sum(math.hypot(s["x"] - tg["x"], s["y"] - tg["y"]) <= SPEED_ONE * T for s in doc["starts"]),
                                "kept": len(keep), "two_duck_margin_on_p90_entry": SPEED_TWO * T / st["entry_m"]["p90"] - 1}
        out = dict(doc, stage=f"{doc['stage']}-heavy", n=len(keep), mass=cfg["box"]["mass"], max_steps=cfg["env"]["max_steps"],
                   base_set=path, config=CONFIG, removed=len(doc["starts"]) - len(keep), solo_reach_m=reach,
                   episode_seed0=10000,
                   note=(f"{path} for the heavy box ({cfg['box']['mass']} kg, {cfg['env']['max_steps']}-step limit): the same starts "
                         f"with the shortest targets removed (box centre less than {reach} m from entering the target, which one "
                         "duck could cover alone at its open-loop speed). Ids are the original ones; episode seed 10000 + id, "
                         "so each start keeps its duck start noise. Never used in training."),
                   starts=keep)
        if os.path.exists(rp(HEAVY[k])) and not a.force:
            print(f"{HEAVY[k]} exists; --force to rebuild")
        else:
            write_json(HEAVY[k], out, indent=1)
            print(f"wrote {HEAVY[k]}: {len(keep)} of {len(doc['starts'])} starts")
    ck = h["check"]
    _, l2cfg = load_stage(LIGHT["L2"][1])
    tg = load_test_set(LIGHT["L2"][0])["target"]
    drawn = make_test_set(l2cfg, ck["draw"], ck["rng_seed"])
    keep = [s for s in drawn if target_entry_m(s, tg, size) > reach][:ck["n"]]
    if len(keep) < ck["n"]:
        raise SystemExit(f"only {len(keep)} check starts left of {ck['draw']} drawn; raise h1.check.draw")
    keep = [dict(s, id=i, drawn_id=s["id"]) for i, s in enumerate(keep)]
    key = lambda s: (round(s["x"], 3), round(s["y"], 3), round(s["yaw"], 1))          # noqa: E731
    shared = {key(s) for s in keep} & {key(s) for p in list(LIGHT.values()) for s in load_test_set(p[0])["starts"]}
    if shared:
        raise SystemExit(f"check set repeats test box poses {sorted(shared)}; pick another rng_seed")
    report["sets"][CHECK] = {"n": len(keep), "drawn": ck["draw"], **target_stats(keep, tg, size)}
    report["sets"][CHECK + " (as drawn)"] = {"n": len(drawn), **target_stats(drawn, tg, size)}
    for old in ("experiments/test_sets/stage1_checks.json", "experiments/test_sets/stage1_noisy_checks.json"):
        d = load_test_set(old)
        report["sets"][old] = {"n": d["n"], **target_stats(d["starts"], d["target"], size),
                               "solo_reachable_by_entry": sum(target_entry_m(s, d["target"], size) <= SPEED_ONE * T for s in d["starts"]),
                               "solo_reachable_by_centre": sum(math.hypot(s["x"] - d["target"]["x"], s["y"] - d["target"]["y"]) <= SPEED_ONE * T for s in d["starts"])}
    doc = {"stage": "stage1-heavy-checks", "created": time.strftime("%Y-%m-%d"), "config": CONFIG, "n": len(keep),
           "rng_seed": ck["rng_seed"], "drawn": ck["draw"], "episode_seed0": ck["episode_seed0"],
           "range": l2cfg["env"]["box_start"], "target": tg, "layout": l2cfg["env"]["layout"], "mass": cfg["box"]["mass"],
           "max_steps": cfg["env"]["max_steps"], "solo_reach_m": reach, "shared_with_test_sets": 0,
           "note": ("checkpoint selection and the h1 decision rule only; never report final results on it. Box poses: a Latin "
                    f"hypercube of {ck['draw']} over stage 1's full range (rng seed {ck['rng_seed']}), the starts whose box centre "
                    f"is less than {reach} m from entering the target removed, the first {ck['n']} of the rest kept. L2 duck "
                    f"start noise from the episode seed ({ck['episode_seed0']} + id). No box pose repeats a test-set one."),
           "starts": keep}
    if os.path.exists(rp(CHECK)) and not a.force:
        print(f"{CHECK} exists; --force to rebuild")
    else:
        write_json(CHECK, doc, indent=1)
        print(f"wrote {CHECK}: {len(keep)} starts")
    write_json(os.path.join(E, "results", "targets.json"), report, indent=1)
    for p, s in report["sets"].items():
        print(p, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items() if not isinstance(v, dict)},
              {m: {k: round(v, 3) for k, v in s[m].items()} for m in ("centre_m", "entry_m")})
    return 0


def cmd_startcheck(a) -> int:
    """How many L2-noise starts the start check (copush.env._start_ok: the box moved > 1 cm or turned > 2 deg while the
    ducks settled) rejects on the light box and on the heavy one. Training seeds 0..resets-1, the config's box starts."""
    from copush.env import CoPushEnv
    _, heavy = load_stage(CONFIG)
    light = copy.deepcopy(heavy)
    light["box"]["mass"] = 0.15
    out = {}
    for name, cfg in (("light 0.15 kg", light), ("heavy 0.60 kg", heavy)):
        env = CoPushEnv(cfg, split="train")
        for seed in range(a.resets):
            env.reset(seed=seed)
        out[name] = {"resets": a.resets, "draws": env.start_draws, "rejected": env.start_resamples,
                     "rejected_rate": env.start_resamples / env.start_draws}
        print(name, out[name], flush=True)
    write_json(os.path.join(E, "results", "start_check.json"), out, indent=1)
    return 0


# ── evaluation ───────────────────────────────────────────────────────────────

def _init(config):
    import torch
    torch.set_num_threads(1)
    _W.update(config=config, env={}, act={}, starts={}, seed0={})


def _episode(job):
    policy, key, mode, k = job
    from copush.env import CoPushEnv
    if key not in _W["env"]:
        doc = load_test_set(SETS[key][0])
        _W["env"][key] = CoPushEnv(set_cfg(key, _W["config"]), split="eval")
        _W["starts"][key], _W["seed0"][key] = doc["starts"], doc.get("episode_seed0", 10000)
    if policy not in _W["act"]:
        from test_set import make_act_factory
        _W["act"][policy] = make_act_factory("p", {"path": policy, "decentral": {"include_partner": True}, "standstill": True})
    env, start = _W["env"][key], _W["starts"][key][k]
    seed = _W["seed0"][key] + start["id"]
    act = _W["act"][policy](env, seed)
    obs, _ = env.reset(seed=seed, options={"box": start})
    while True:
        action = act(obs)
        if mode == "A_idle":
            action[0], action[1] = -1.0, 0.0
        elif mode == "B_idle":
            action[2], action[3] = -1.0, 0.0
        obs, _, te, tr, info = env.step(action)
        if te or tr:
            break
    es = info["episode_stats"]
    nn = lambda x: None if x != x else round(float(x), 4)                             # noqa: E731
    return {"k": k, "id": start["id"], "reason": es["reason"], "success": es["reason"] == "success", "steps": int(es["steps"]),
            "contact_share_a": nn(es["contact_share"]["duck_a"]), "push_share_a": nn(es["push_share"]["duck_a"]),
            "contact_impulse": [round(es["contact_impulse"][d], 3) for d in ("duck_a", "duck_b")],
            "push_impulse": [round(es["push_impulse"][d], 3) for d in ("duck_a", "duck_b")],
            "fell": any(es["fell"].values()), "final_dist": round(es["final_dist"], 4), "min_dist": round(es["min_dist"], 4),
            "mass": float(env.sim.m.body_mass[env.sim.box_body]), "max_steps": int(env.ecfg["max_steps"])}


class Evaluator:
    subdir = "evals"                                   # the cache folder under the run dir (h1_fill_eval.py uses evals200)
    init_fn = staticmethod(_init)                      # the worker initializer (h1_fill_eval.py adds its own sets)

    def __init__(self, run, config, workers, limit=None):
        self.run, self.config, self.workers, self.limit = run, config, workers, limit

    def __call__(self, label: str, policy: str, key: str, mode: str = "both") -> list:
        path = os.path.join(self.run, self.subdir, f"{label}__{key}__{mode}.json")
        got = read_json(path)
        if got:
            return got["episodes"]
        n = len(load_test_set(SETS[key][0])["starts"])
        n = min(n, self.limit) if self.limit else n
        t0 = time.time()
        with Pool(self.workers, initializer=self.init_fn, initargs=(self.config,)) as p:
            eps = sorted(p.map(_episode, [(policy, key, mode, k) for k in range(n)], chunksize=2), key=lambda e: e["k"])
        write_json(path, {"label": label, "policy": policy, "set": SETS[key][0], "mode": mode, "episodes": eps},
                   separators=(",", ":"))
        s = summarize(eps)
        log(f"eval {label} on {key} ({mode}): task {s['task']['k']}/{s['n']}, cooperative {s['cooperative']['contact']['k']}/{s['n']}, "
            f"{time.time() - t0:.0f} s")
        return eps


def summarize(eps: list, threshold: float = None) -> dict:
    th = C.threshold_of(load_stage(CONFIG)[1]) if threshold is None else threshold
    s = C.summarize([dict(e, i=e["id"]) for e in eps], th)
    n, ok = len(eps), [e for e in eps if e["success"]]
    cell = lambda k, of=n: {"k": k, "n": of, "rate": k / of if of else float("nan"), "ci": list(C.wilson(k, of))}   # noqa: E731
    weak = [C.weaker_share(e["contact_share_a"]) for e in ok]
    s["weaker_share_buckets"] = {f"{round(100 * lo)}-{round(100 * min(hi, .5))}%":
                                 cell(sum(1 for w in weak if (w or 0.0) >= lo and (w or 0.0) < hi), len(ok)) for lo, hi in BUCKETS}
    s["falls"], s["tip_overs"] = cell(sum(e["fell"] for e in eps)), cell(sum(e["reason"] == "box_tipped" for e in eps))
    s["timeouts"] = cell(sum(e["reason"] == "timeout" for e in eps))
    s["steps_success_mean"] = sum(e["steps"] for e in ok) / len(ok) if ok else None
    s["steps_success_max"] = max((e["steps"] for e in ok), default=None)
    s["reasons"] = {r: sum(e["reason"] == r for e in eps) for r in sorted({e["reason"] for e in eps})}
    return s


# ── training ─────────────────────────────────────────────────────────────────

def ckpt_steps(out: str) -> list:
    d = rp(os.path.join(out, "checkpoints"))
    return sorted(int(f[5:-4]) for f in os.listdir(d) if f.startswith("ckpt_") and f.endswith(".zip")) if os.path.isdir(d) else []


def stage_py(config, seed, out, steps) -> None:
    logf = rp(os.path.join(out, "train.log"))
    os.makedirs(os.path.dirname(logf), exist_ok=True)
    with open(logf, "a") as f:
        r = subprocess.run([sys.executable, "scripts/rl/stage.py", "--config", config, "--seed", str(seed), "--out", out,
                            "--steps", str(steps)], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        raise SystemExit(f"stage.py failed for seed {seed} (see {logf})")


def train_seed(ev, config, run, seed, steps, early_at, can_stop=True) -> dict:
    out = os.path.join(run, f"s{seed}")
    done = read_json(os.path.join(out, "h1.json"))
    if done:
        return done
    res = {"seed": seed, "out": out, "early_stopped": False}
    if not any(s >= early_at for s in ckpt_steps(out)):
        log(f"seed {seed}: training to {early_at} duck steps")
        stage_py(config, seed, out, early_at)
    first = min(s for s in ckpt_steps(out) if s >= early_at)
    e = ev(f"s{seed}@{first}", os.path.join(out, "checkpoints", f"ckpt_{first}.zip"), "check")
    res["early_check"] = {"step": first, "task_successes": sum(x["success"] for x in e), "n": len(e)}
    if res["early_check"]["task_successes"] == 0 and can_stop:
        res["early_stopped"] = True
        log(f"seed {seed}: 0 task successes on the check set at {first} steps; this seed stops here")
    else:
        if not (read_json(os.path.join(out, "results.json"), {}) or {}).get("steps", 0) >= steps:
            log(f"seed {seed}: {res['early_check']['task_successes']} check-set successes at {first}; training on to {steps}")
            stage_py(config, seed, out, steps)
        curve = []
        for st in ckpt_steps(out):
            s = summarize(ev(f"s{seed}@{st}", os.path.join(out, "checkpoints", f"ckpt_{st}.zip"), "check"))
            curve.append({"step": st, "task": s["task"]["k"], "cooperative": s["cooperative"]["contact"]["k"],
                          "cooperative_push": s["cooperative"]["push"]["k"], "n": s["n"], "falls": s["falls"]["k"],
                          "tip_overs": s["tip_overs"]["k"], "timeouts": s["timeouts"]["k"]})
        best = max(curve, key=lambda c: (c["cooperative"], c["task"], -c["step"]))
        shutil.copyfile(rp(os.path.join(out, "checkpoints", f"ckpt_{best['step']}.zip")), rp(os.path.join(out, "best.zip")))
        res.update(curve=curve, pick=best, pick_path=os.path.join(out, "best.zip"), pick_sha256=sha256(os.path.join(out, "best.zip")),
                   wall_s=(read_json(os.path.join(out, "results.json"), {}) or {}).get("wall_s"))
        log(f"seed {seed}: pick step {best['step']} (cooperative {best['cooperative']}/{best['n']}, task {best['task']}/{best['n']})")
    write_json(os.path.join(out, "h1.json"), res, indent=1)
    return res


# ── pipeline and clips ───────────────────────────────────────────────────────

def pipeline(run, config, label, push, workers, limit) -> dict:
    out = os.path.join(run, f"pipeline_{label}")
    if not os.path.exists(rp(os.path.join(out, "results.json"))):
        cmd = [sys.executable, "scripts/rl/rendezvous_eval.py", "eval", "--rendezvous", R6, "--push", push, "--out", out,
               "--box-task-from", config, "--workers", str(workers)] + (["--starts", str(limit)] if limit else [])
        with open(rp(out + ".log"), "w") as f:
            if subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode:
                raise SystemExit(f"pipeline eval failed (see {out}.log)")
        log(f"pipeline {label}: done")
    return read_json(os.path.join(out, "results.json"))


def record(config, policy, key, k, mode, label, base) -> dict:
    """One episode as <base>.mp4 and .gif (2x speed)."""
    from copush.sim import CONTROL_DT
    from copush.video import VideoRecorder
    _W.clear()
    _init(config)
    _episode((policy, key, mode, k))                      # builds the env and the policy; the episode is then replayed
    env = _W["env"][key]
    rec = VideoRecorder(env.sim.m, base + ".mp4", fps=25, width=480, height=270)
    every, count = max(1, round(2 / (25 * CONTROL_DT))), [0]

    def hook(st, _):
        if count[0] % every == 0:
            rec.frame(env.sim.d, st, [label, f"box {_W['mass']:.2f} kg, step {env.steps + 1} of {env.ecfg['max_steps']}"])
        count[0] += 1
    _W["mass"] = float(env.sim.m.body_mass[env.sim.box_body])
    env.frame_hook = hook
    try:
        e = _episode((policy, key, mode, k))
    finally:
        env.frame_hook = None
        rec.close()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", base + ".mp4", "-filter_complex",
                    "fps=5,scale=360:-2,split[x][y];[x]palettegen=max_colors=32:stats_mode=diff[p];[y][p]paletteuse=dither=none:diff_mode=rectangle",
                    "-loop", "0", base + ".gif"], check=True)
    return e


def make_gifs(ev, run, config, label, policy) -> list:
    done = read_json(os.path.join(run, "gifs", "gifs.json"))
    if done:
        return done
    key = "heavy_L2"
    eps = ev(label, policy, key)
    solo = ev(label, policy, key, "A_idle")
    good = []
    for floor in (0.40, 0.25):                            # the most evenly shared successes first
        good += sorted((e for e in eps if e["success"] and e not in good
                        and (C.weaker_share(e["contact_share_a"]) or 0) >= floor), key=lambda e: e["k"])
    bad = [e for e in eps if not e["success"]]
    plan = [(e, "both", "cooperative_success") for e in good[:2]] + [(e, "both", "failure") for e in bad[:1]]
    if good:
        plan.append((solo[good[0]["k"]], "A_idle", "solo_test_duck_a_idle"))
    out, gdir = [], rp(os.path.join(run, "gifs"))
    os.makedirs(gdir, exist_ok=True)
    for e, mode, kind in plan:
        name = f"{kind}_start{e['id']:03d}"
        text = {"cooperative_success": "h1: both ducks push", "failure": "h1: failure",
                "solo_test_duck_a_idle": "h1 solo test: duck A idle"}[kind]
        r = record(config, policy, key, e["k"], mode, text, os.path.join(gdir, name))
        if (r["reason"], r["steps"]) != (e["reason"], e["steps"]):
            log(f"gif {name}: the replay ended {r['reason']} at {r['steps']}, the evaluation {e['reason']} at {e['steps']}")
        out.append({"file": name + ".gif", "kind": kind, "mode": mode, "id": e["id"], "reason": r["reason"], "steps": r["steps"],
                    "contact_share_a": r["contact_share_a"]})
        log(f"gif {name}: {r['reason']} in {r['steps']} steps, duck A contact share {r['contact_share_a']}")
    write_json(os.path.join(run, "gifs", "gifs.json"), out, indent=1)
    return out


# ── report ───────────────────────────────────────────────────────────────────

def pc(c: dict) -> str:
    return "n/a" if not c["n"] else f"{100 * c['rate']:.1f}% ({100 * c['ci'][0]:.1f} to {100 * c['ci'][1]:.1f})"


def kn(c: dict) -> str:
    return f"{c['k']}/{c['n']}"


def pp(p: dict) -> str:
    return (f"{100 * p['diff']:+.1f} ({100 * p['ci'][0]:+.1f} to {100 * p['ci'][1]:+.1f}); seeds "
            + ", ".join(f"{100 * s['diff']:+.1f}" for s in p["per_seed"])
            + ("; **measurable**" if p["measurable"] else "; no measurable difference"))


def paired_all(eps: dict, a: tuple, b: str, th: float) -> dict:
    from cooperation_report import paired
    val = {"task": lambda e: float(e["success"]),
           "cooperative": lambda e: float(C.is_cooperative(e["success"], e["contact_share_a"], th)),
           "cooperative_push": lambda e: float(C.is_cooperative(e["success"], e["push_share_a"], th))}
    return {k: paired(eps, a, (b,), v) for k, v in val.items()}


def table(title, rows: dict, solo: dict) -> list:
    """rows: {name: summary (both ducks)}; solo: {name: {mode: summary}}."""
    L = [f"### {title}", "",
         "| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | "
         "duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | "
         "steps to success, mean (max) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, s in rows.items():
        so = solo.get(n, {})
        L.append(f"| {n} | {s['n']} | {pc(s['task'])} | **{pc(s['cooperative']['contact'])}** | {pc(s['cooperative']['push'])} | "
                 + " | ".join(pc(so[m]["task"]) if m in so else "not run" for m in ("A_idle", "B_idle"))
                 + f" | {kn(s['falls'])} | {kn(s['tip_overs'])} | {kn(s['timeouts'])} | "
                 + (f"{s['steps_success_mean']:.0f} ({s['steps_success_max']})" if s["task"]["k"] else "none") + " |")
    L += ["", "Share of the pushing done by the duck doing less (contact impulse), of the task successes:", "",
          "| policy | successes | " + " | ".join(next(iter(rows.values()))["weaker_share_buckets"]) + " |",
          "|---|---|" + "---|" * len(BUCKETS)]
    for n, s in rows.items():
        L.append(f"| {n} | {s['task']['k']} | " + " | ".join(
            f"{c['k']} ({100 * c['rate']:.0f}%)" if c["n"] else "0" for c in s["weaker_share_buckets"].values()) + " |")
    return L + [""]


def run(a) -> int:
    global RUN
    dry = a.dry_run
    run_dir = RUN + ("-dry" if dry else "")
    stage, cfg = load_stage(CONFIG)
    h, config = stage["h1"], CONFIG
    steps, early, seeds, limit = stage["steps"], h["early_stop_at"], list(h["seeds"]), None
    results = os.path.join(E, "results")
    if dry:                                               # a tiny copy of the config: 2 seeds, 8k steps, 6 starts per eval
        steps, early, seeds, limit = 8192, 4096, seeds[:2], 6
        d = yaml.safe_load(open(rp(CONFIG)))
        d.update(steps=steps, checkpoint_every=4096, max_videos=2)
        d["overrides"]["rl"] = {"eval_every": 4096}
        os.makedirs(rp(run_dir), exist_ok=True)
        config = os.path.join(run_dir, "config.yaml")
        yaml.safe_dump(d, open(rp(config), "w"))
        results = os.path.join(run_dir, "results")
    RUN = run_dir
    if sha256(FROZEN) != FROZEN_SHA:
        raise SystemExit(f"{FROZEN} is not the official L2-s2 (sha256 {sha256(FROZEN)})")
    th = C.threshold_of(cfg)
    ev = Evaluator(run_dir, config, a.workers, limit)
    log(f"h1 start: box {cfg['box']['mass']} kg, {cfg['env']['max_steps']} steps, reward {cfg['reward']['version']}, "
        f"seeds {seeds}, {steps} duck steps" + (" (DRY RUN)" if dry else ""))

    for m in MODES:                                        # baseline: frozen L2-s2 on the heavy check set
        ev("frozen", FROZEN, "check", m)
    seeds_res = {f"s{s}": train_seed(ev, config, run_dir, s, steps, early, can_stop=not dry) for s in seeds}
    picks = {k: r["pick_path"] for k, r in seeds_res.items() if not r["early_stopped"]}
    pols = {"frozen": FROZEN, **picks}
    names = {"frozen": "frozen L2-s2", **{k: f"h1 seed {k[1:]} (pick, step {seeds_res[k]['pick']['step']})" for k in picks}}
    for k in picks:                                        # solo tests on the check set
        for m in ("A_idle", "B_idle"):
            ev(k, picks[k], "check", m)

    E_ = {}                                                # episodes[set key][policy key][mode]
    for key in ["check"] + [f"heavy_{k}" for k in LIGHT]:
        E_[key] = {p: {m: ev(p if p == "frozen" or key != "check" or m != "both" else f"{p}@{seeds_res[p]['pick']['step']}",
                             pols[p], key, m) for m in MODES} for p in pols}
    E_["light_clean"] = {p: {"both": ev(p, pols[p], "light_clean")} for p in pols}
    S = {key: {p: {m: summarize(e, th) for m, e in v.items()} for p, v in d.items()} for key, d in E_.items()}
    pair = {key: paired_all({p: E_[key][p]["both"] for p in pols}, tuple(picks), "frozen", th) for key in E_} if picks else {}

    # decision rule (PLAN.md), on the check set
    dec = {"threshold": th}
    if picks:
        c = pair["check"]["cooperative"]
        solo = {p: {m: S["check"][p][m]["task"]["rate"] for m in ("A_idle", "B_idle")} for p in picks}
        buck = {p: S["check"][p]["both"] for p in picks}
        under = {p: (sum(v["k"] for b, v in s["weaker_share_buckets"].items() if b in ("0-10%", "10-25%")), s["task"]["k"]) for p, s in buck.items()}
        dec.update(cooperative_vs_frozen=c, cooperative_measurably_above=bool(c["measurable"] and c["diff"] > 0),
                   solo_task_success=solo, solo_under_10pct=all(v < 0.10 for s in solo.values() for v in s.values()),
                   successes_with_one_duck_under_25pct={p: {"k": k, "of": n, "share": k / n if n else None} for p, (k, n) in under.items()})
        dec["h1_works"] = bool(dec["cooperative_measurably_above"] and dec["solo_under_10pct"])
        dec["add_balanced_push_bonus"] = bool(dec["solo_under_10pct"] and any(n and k / n > 1 / 3 for k, n in under.values()))

    # full pipeline with the heavy box
    pipe = {}
    if picks:
        best = max(picks, key=lambda p: (seeds_res[p]["pick"]["cooperative"], seeds_res[p]["pick"]["task"]))
        docs = {"frozen": pipeline(run_dir, config, "frozen", FROZEN, a.workers, limit),
                best: pipeline(run_dir, config, best, picks[best], a.workers, limit)}
        pe = {k: [dict(e, success=e["push_success"]) for e in d["episodes"]] for k, d in docs.items()}
        pipe = {"best": best, "summary": {k: {"cooperation": C.summarize(v, th), "arrived": sum(e["arrived"] for e in v),
                                              "push_reasons": docs[k]["summary"]["all"]["push_reasons"]} for k, v in pe.items()},
                "paired_best_minus_frozen": paired_all(pe, (best,), "frozen", th)}
        gifs = make_gifs(ev, run_dir, config, best, picks[best])
        gdir = rp(os.path.join(E, "gifs")) if not dry else rp(os.path.join(run_dir, "gifs_out"))
        os.makedirs(gdir, exist_ok=True)
        for g in gifs:
            shutil.copyfile(rp(os.path.join(run_dir, "gifs", g["file"])), os.path.join(gdir, g["file"]))
    else:
        gifs, best = [], None

    doc = {"config": config, "dry_run": dry, "box_mass": cfg["box"]["mass"], "max_steps": cfg["env"]["max_steps"],
           "reward_version": cfg["reward"]["version"], "steps": steps, "threshold": th, "frozen": FROZEN, "seeds": seeds_res,
           "names": names, "summary": S, "paired_vs_frozen": pair, "decision": dec, "pipeline": pipe, "gifs": gifs,
           "sets": {k: v[0] for k, v in SETS.items()}}
    write_json(os.path.join(results, "results.json"), doc, indent=1)
    write_json(os.path.join(results, "episodes.json"),
               {key: {p: {m: [{k: e[k] for k in ("id", "reason", "steps", "contact_share_a", "push_share_a", "fell")} for e in v]
                          for m, v in d.items()} for p, d in dd.items()} for key, dd in E_.items()}, separators=(",", ":"))

    L = ["# h1 heavy-box fine-tune: results", "",
         f"Written by `scripts/rl/run_h1_heavy_finetune.py`" + (" (DRY RUN)" if dry else "") + f". Box {cfg['box']['mass']} kg, "
         f"{cfg['env']['max_steps']}-step limit, reward {cfg['reward']['version']}. Deterministic, one episode per start. "
         f"Cooperative success = task success and each duck at least {round(100 * th)}% of the pushing; 95% Wilson intervals.", "",
         "## Training", "", "| seed | early check (400k) | pick (step) | check set at the pick: cooperative / task | wall time |",
         "|---|---|---|---|---|"]
    for k, r in seeds_res.items():
        ec = r["early_check"]
        L.append(f"| {r['seed']} | {ec['task_successes']}/{ec['n']} task successes at {ec['step']} | "
                 + ("stopped early (0 successes)" if r["early_stopped"] else
                    f"{r['pick']['step']} | {r['pick']['cooperative']}/{r['pick']['n']} / {r['pick']['task']}/{r['pick']['n']} | "
                    f"{(r['wall_s'] or 0) / 60:.0f} min") + " |")
    L += ["", "Check set, every kept checkpoint (cooperative successes / task successes of the starts):", ""]
    for k, r in seeds_res.items():
        if not r["early_stopped"]:
            L.append(f"- seed {r['seed']}: " + ", ".join(f"{c['step'] // 1000}k {c['cooperative']}/{c['task']}" for c in r["curve"]))
    title = {"check": "Check set (heavy box, L2 start noise; used for picking and for the decision rule)",
             **{f"heavy_{k}": f"Test set: {k}, heavy box (`{HEAVY[k]}`)" for k in LIGHT},
             "light_clean": "Forgetting check: LIGHT box (0.15 kg, 100 steps), clean test set"}
    L += ["", "## Results", ""]
    for key in S:
        L += table(title[key], {names[p]: S[key][p]["both"] for p in pols},
                   {names[p]: {m: S[key][p][m] for m in ("A_idle", "B_idle") if m in S[key][p]} for p in pols})
        if picks:
            pr = pair[key]
            L += [f"h1 (the {len(picks)} seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success "
                  f"{pp(pr['task'])}. Cooperative success (contact impulse) {pp(pr['cooperative'])}. Cooperative success (along the "
                  f"line) {pp(pr['cooperative_push'])}.", ""]
    if picks:
        L += ["## Decision rule (check set)", "",
              f"- Cooperative success measurably above frozen L2-s2: **{'yes' if dec['cooperative_measurably_above'] else 'no'}** "
              f"({pp(dec['cooperative_vs_frozen'])}).",
              "- Both solo tests under 10% task success: **" + ("yes" if dec["solo_under_10pct"] else "no") + "** ("
              + "; ".join(f"{names[p]}: duck B alone {100 * v['A_idle']:.1f}%, duck A alone {100 * v['B_idle']:.1f}%" for p, v in dec["solo_task_success"].items()) + ").",
              f"- **h1 works: {'yes' if dec['h1_works'] else 'no'}.**",
              "- Successes where one duck does under 25%: " + "; ".join(
                  f"{names[p]}: {v['k']} of {v['of']}" + (f" ({100 * v['share']:.0f}%)" if v["of"] else "") for p, v in dec["successes_with_one_duck_under_25pct"].items())
              + f". Add the balanced-push bonus next (solo rule met and more than a third in any seed): **{'yes' if dec['add_balanced_push_bonus'] else 'no'}**.", "",
              "## Full pipeline (r6 rendezvous, then the push policy; heavy box; `experiments/test_sets/rendezvous_large.json`)", "",
              "| push policy | n | docked | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | push endings |",
              "|---|---|---|---|---|---|---|"]
        for k, s in pipe["summary"].items():
            c = s["cooperation"]
            L.append(f"| {names[k]} | {c['n']} | {s['arrived']}/{c['n']} | {pc(c['task'])} | **{pc(c['cooperative']['contact'])}** | "
                     f"{pc(c['cooperative']['push'])} | {', '.join(f'{r} {v}' for r, v in s['push_reasons'].items())} |")
        pb = pipe["paired_best_minus_frozen"]
        L += ["", f"{names[pipe['best']]} minus frozen L2-s2, same starts (one seed, so no seed rule): task success {pp(pb['task'])}. "
                  f"Cooperative success {pp(pb['cooperative'])}.", "", "## Clips", ""]
        L += [f"- `{g['file']}`: {g['kind'].replace('_', ' ')}, start {g['id']}, ended {g['reason']} in {g['steps']} steps" for g in gifs]
    open(rp(os.path.join(results, "results.md")), "w").write("\n".join(L) + "\n")
    log(f"h1 done: results in {results}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="run", choices=("run", "sets", "startcheck"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true", help="sets: overwrite existing set files")
    ap.add_argument("--resets", type=int, default=500, help="startcheck: resets per box")
    a = ap.parse_args()
    return {"run": run, "sets": cmd_sets, "startcheck": cmd_startcheck}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
