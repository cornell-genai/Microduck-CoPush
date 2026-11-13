#!/usr/bin/env python3
"""Distill the centralized stage 1 policy into decentralized per-duck policies (copush.decentral).

    scripts/rl.sh scripts/rl/distill.py --config experiments/decentralized-control/distill/config.yaml

1. collect   the teacher (centralized PPO) drives episodes from random box starts (train seeds, the
             stage 1 range); in noise_frac of them its action gets Gaussian noise (noise_std) so the
             data covers recoveries. Every step records, per duck, its local view (D1 and D2) and the
             teacher's noise-free command for that duck, plus the discounted team return.
2. fit       for each variant, a PPO MlpPolicy (the hyperparameters fine-tuning uses) is fit by
             supervised learning: the actor mean to the teacher's command (MSE) and the critic to the
             recorded return. log_std starts at the teacher's.
3. dagger    dagger_rounds times: the student drives (both ducks, its own views), the teacher labels
             every visited state, the data is added and the student refit.
4. report    copy quality on held-out episodes (val seeds; R2 and mean absolute error per command), then
             success from copying alone: the fixed start (rl.eval_seed) and the stage 1 test set.
Writes <out>/{d1,d2}.zip (the distilled policies; `out` is git-ignored) and <results>/distill.{md,json}.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copush.experiments import load_stage, load_test_set, repo_path, test_set_episodes  # noqa: E402

VARIANTS = {"d1": False, "d2": True}                     # name -> include_partner


def _collect(job):
    """One worker: episodes on `seeds`. driver: None (teacher) or (variant, student zip path)."""
    cfg_path, teacher_path, seeds, noise_seeds, noise_std, driver, gamma = job
    from stable_baselines3 import PPO
    from copush.decentral import decentral_action, local_obs
    from copush.env import CoPushEnv
    _, cfg = load_stage(cfg_path)
    teacher = PPO.load(repo_path(teacher_path), device="cpu")
    student = PPO.load(driver[1], device="cpu") if driver else None
    env = CoPushEnv(cfg, split="train")
    rng = np.random.default_rng(seeds[0])
    rows = {"d1": [], "d2": [], "y": [], "ret": [], "ep": []}
    for seed in seeds:
        obs, _ = env.reset(seed=seed)
        rews, n0 = [], len(rows["y"])
        while True:
            st = env.state
            a_t = np.clip(teacher.predict(obs, deterministic=True)[0], -1, 1)
            for k, d in enumerate(("duck_a", "duck_b")):
                rows["d1"].append(local_obs(st, d, False))
                rows["d2"].append(local_obs(st, d, True))
                rows["y"].append(a_t[2 * k:2 * k + 2])
                rows["ep"].append(seed)
            if student is not None:
                a = decentral_action(student, st, VARIANTS[driver[0]])
            else:
                a = a_t + (rng.normal(0, noise_std, 4) if seed in noise_seeds else 0.0)
            obs, r, te, tr, _ = env.step(np.clip(a, -1, 1).astype(np.float32))
            rews.append(r)
            if te or tr:
                break
        g, ret = 0.0, []
        for r in reversed(rews):
            g = r + gamma * g
            ret.append(g)
        for g in reversed(ret):
            rows["ret"] += [g, g]                        # both ducks share the team return
        assert len(rows["ret"]) == len(rows["y"]), (n0, len(rows["y"]))
    return {k: np.asarray(v, dtype=np.float32) for k, v in rows.items()}


def collect(cfg_path, teacher, seeds, noise_frac, noise_std, gamma, driver=None, workers=8, rng_seed=0):
    rng = np.random.default_rng(rng_seed)
    noisy = set(int(s) for s in rng.choice(seeds, int(noise_frac * len(seeds)), replace=False)) if driver is None else set()
    chunks = [[int(x) for x in c] for c in np.array_split(seeds, workers) if len(c)]
    with Pool(len(chunks)) as pool:
        parts = pool.map(_collect, [(cfg_path, teacher, c, noisy, noise_std, driver, gamma) for c in chunks])
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def new_model(cfg, include_partner):
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv
    from copush.decentral import DuckPairEnv, DuckVecEnv
    pc = cfg["ppo"]
    vec = DuckVecEnv(DummyVecEnv([lambda: DuckPairEnv(cfg, include_partner)]))
    return PPO("MlpPolicy", vec, n_steps=pc["n_steps"], batch_size=pc["batch_size"], n_epochs=pc["n_epochs"],
               learning_rate=pc["learning_rate"], gamma=pc["gamma"], gae_lambda=pc["gae_lambda"],
               clip_range=pc["clip_range"], ent_coef=pc["ent_coef"], seed=pc["seed"], device="cpu", verbose=0)


def fit(model, x, y, ret, epochs, lr, batch, seed):
    import torch as th
    pol = model.policy
    opt = th.optim.Adam([p for n, p in pol.named_parameters() if n != "log_std"], lr=lr)
    X, Y, R = th.as_tensor(x), th.as_tensor(y), th.as_tensor(ret)
    g = th.Generator().manual_seed(seed)
    pol.set_training_mode(True)
    for _ in range(epochs):
        perm = th.randperm(len(X), generator=g)
        for i in range(0, len(X), batch):
            j = perm[i:i + batch]
            mean = pol.get_distribution(X[j]).distribution.mean
            v = pol.predict_values(X[j]).squeeze(-1)
            loss = ((mean - Y[j]) ** 2).mean() + 0.01 * ((v - R[j]) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    pol.set_training_mode(False)


def copy_quality(model, x, y) -> dict:
    """On held-out data: R2 and mean absolute error per command, in physical units."""
    pred = np.clip(model.predict(x, deterministic=True)[0], -1, 1)
    out = {}
    for k, (name, scale, unit) in enumerate((("vx", 0.15, "m/s"), ("vyaw", 1.5, "rad/s"))):
        err = pred[:, k] - y[:, k]
        out[name] = {"r2": float(1 - (err ** 2).sum() / ((y[:, k] - y[:, k].mean()) ** 2).sum()),
                     "mae": float(np.abs(err).mean() * scale), "unit": unit}
    return out


def _test_one(job):
    cfg_path, ts_path, name, path, ip = job
    from test_set import make_act_factory
    _, cfg = load_stage(cfg_path)
    spec = path if ip is None else {"path": path, "decentral": {"include_partner": ip}}
    make_act = make_act_factory(name, spec)
    stats = test_set_episodes(cfg, load_test_set(ts_path)["starts"], make_act)
    from copush.env import CoPushEnv
    from copush.rl_callbacks import run_episode
    fixed_cfg = json.loads(json.dumps(cfg))
    fixed_cfg["env"]["box_start"]["enabled"] = False
    env = CoPushEnv(fixed_cfg, split="eval")
    fixed = run_episode(env, make_act(env, cfg["rl"]["eval_seed"]), cfg["rl"]["eval_seed"])
    return name, stats, fixed


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    args = p.parse_args()
    with open(repo_path(args.config)) as f:
        dc = yaml.safe_load(f)
    stage, cfg = load_stage(dc["env_config"])
    out, res_dir = repo_path(dc["out"]), repo_path(dc["results"])
    os.makedirs(out, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)
    t0 = time.perf_counter()
    gamma = cfg["ppo"]["gamma"]
    s0, n_tr, n_val = dc["train_seed0"], dc["train_episodes"], dc["val_episodes"]
    tr_seeds, val_seeds = np.arange(s0, s0 + n_tr), np.arange(s0 + n_tr, s0 + n_tr + n_val)
    data = collect(dc["env_config"], dc["teacher"], tr_seeds, dc["noise_frac"], dc["noise_std"], gamma, rng_seed=s0)
    val = collect(dc["env_config"], dc["teacher"], val_seeds, 0.0, 0.0, gamma, rng_seed=s0 + 1)
    print(f"collected {len(data['y']) // 2} teacher steps ({n_tr} episodes) + {len(val['y']) // 2} val steps "
          f"in {time.perf_counter() - t0:.0f} s", flush=True)

    from stable_baselines3 import PPO
    teacher = PPO.load(repo_path(dc["teacher"]), device="cpu")
    log_std = teacher.policy.log_std.detach().numpy()
    report = {"teacher": dc["teacher"], "env_config": dc["env_config"], "n_train_steps": int(len(data["y"]) // 2),
              "n_val_steps": int(len(val["y"]) // 2), "variants": {}}
    for name, ip in VARIANTS.items():
        d = {k: v for k, v in data.items()}
        model = new_model(cfg, ip)
        import torch as th
        with th.no_grad():
            model.policy.log_std.copy_(th.as_tensor(0.5 * (log_std[:2] + log_std[2:])))
        rounds = []
        for r in range(dc["dagger_rounds"] + 1):
            if r > 0:                                    # student drives, teacher labels
                tmp = os.path.join(out, f"{name}_round{r - 1}.zip")
                model.save(tmp)
                seeds = np.arange(s0 + 100000 * r, s0 + 100000 * r + dc["dagger_episodes"])
                new = collect(dc["env_config"], dc["teacher"], seeds, 0.0, 0.0, gamma, driver=(name, tmp), rng_seed=s0 + r)
                d = {k: np.concatenate([d[k], new[k]]) for k in d}
            fit(model, d[name], d["y"], d["ret"], dc["epochs"], dc["lr"], dc["batch"], seed=r)
            q = copy_quality(model, val[name], val["y"])
            rounds.append({"round": r, "samples": int(len(d["y"])), "val": q})
            print(f"{name} round {r}: {len(d['y'])} samples, val R2 vx {q['vx']['r2']:.3f} vyaw {q['vyaw']['r2']:.3f}, "
                  f"MAE vx {q['vx']['mae']:.3f} m/s vyaw {q['vyaw']['mae']:.3f} rad/s", flush=True)
            if r == 0:
                model.save(os.path.join(out, f"{name}_bc.zip"))
        model.save(os.path.join(out, f"{name}.zip"))
        report["variants"][name] = {"include_partner": ip, "rounds": rounds}

    jobs = [(dc["env_config"], stage["test_set"], "stage1 (teacher)", dc["teacher"], None)]
    for name, ip in VARIANTS.items():
        jobs += [(dc["env_config"], stage["test_set"], f"{name} BC only", os.path.join(out, f"{name}_bc.zip"), ip),
                 (dc["env_config"], stage["test_set"], f"{name} after DAgger", os.path.join(out, f"{name}.zip"), ip)]
    with Pool(len(jobs)) as pool:
        tests = pool.map(_test_one, jobs)
    report["test"] = {}
    for name, stats, fixed in tests:
        side = lambda s: 0 if s["start"]["dyaw"] < -15 else (2 if s["start"]["dyaw"] > 15 else 1)   # noqa: E731
        by = [[0, 0], [0, 0], [0, 0]]
        for s in stats:
            by[side(s)][0] += s["reason"] == "success"
            by[side(s)][1] += 1
        sh = [s["push_share"]["duck_a"] for s in stats if s["push_share"]["duck_a"] == s["push_share"]["duck_a"]]
        report["test"][name] = {"success": sum(s["reason"] == "success" for s in stats), "n": len(stats), "by_side": by,
                                "falls": sum(any(s["fell"].values()) for s in stats),
                                "push_share_a": float(np.mean(sh)) if sh else None,
                                "fixed_start": {"reason": fixed["reason"], "steps": fixed["steps"]}}
    report["wall_s"] = time.perf_counter() - t0
    with open(os.path.join(res_dir, "distill.json"), "w") as f:
        json.dump(report, f, indent=1)

    md = ["# Distillation: centralized stage 1 policy -> per-duck policies", "",
          f"Teacher `{dc['teacher']}` on {n_tr} training episodes (random box starts, stage 1 range; {dc['noise_frac']:.0%} "
          f"with action noise sd {dc['noise_std']}), {report['n_train_steps']} sim steps = {2 * report['n_train_steps']} "
          f"per-duck samples, then {dc['dagger_rounds']} DAgger round(s) of {dc['dagger_episodes']} episodes. Copy quality "
          f"on {n_val} held-out episodes ({report['n_val_steps']} steps, teacher driving).", "",
          "## How closely each copies the teacher (held-out episodes)", "",
          "| variant | round | samples | R2 forward speed | R2 turn rate | mean abs error speed (m/s) | mean abs error turn (rad/s) |",
          "|---|---|---|---|---|---|---|"]
    for name, v in report["variants"].items():
        for r in v["rounds"]:
            q = r["val"]
            label = "BC" if r["round"] == 0 else f"DAgger {r['round']}"
            md.append(f"| {name} | {label} | "
                      f"{r['samples']} | {q['vx']['r2']:.3f} | {q['vyaw']['r2']:.3f} | {q['vx']['mae']:.3f} | {q['vyaw']['mae']:.3f} |")
    md += ["", "R2 = 1 means a perfect copy, 0 means no better than always giving the average command. Speed is in [0, 0.3] m/s "
           "and turn rate in [-1.5, 1.5] rad/s.", "", "## Success from copying alone (no PPO)", "",
           "| policy | fixed start | test set | < -15 deg | -15 to +15 deg | > +15 deg | falls | push share A |",
           "|---|---|---|---|---|---|---|---|"]
    for name, t in report["test"].items():
        sh = "-" if t["push_share_a"] is None else f"{100 * t['push_share_a']:.0f}%"
        md.append(f"| {name} | {t['fixed_start']['reason']} ({t['fixed_start']['steps']} steps) | "
                  f"{100 * t['success'] / t['n']:.0f}% ({t['success']}/{t['n']}) | "
                  + " | ".join(f"{w}/{k}" for w, k in t["by_side"]) + f" | {t['falls']}/{t['n']} | {sh} |")
    md += ["", f"Wall time {report['wall_s'] / 60:.1f} min."]
    with open(os.path.join(res_dir, "distill.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
