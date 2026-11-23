#!/usr/bin/env python3
"""Behavioral cloning of the scripted rendezvous coordinator (copush.rendezvous.ScriptedRendezvous) into the same
shared per-duck PPO network that train_rendezvous.py trains, as a warm start for PPO (rendezvous night 5).

    scripts/rl.sh scripts/rl/bc_rendezvous.py collect --config experiments/d2-rendezvous/night5.yaml \
        --out runs/d2-rendezvous-night5/bc/demos.npz
    scripts/rl.sh scripts/rl/bc_rendezvous.py train --config experiments/d2-rendezvous/night5.yaml \
        --data runs/d2-rendezvous-night5/bc/demos.npz --out runs/d2-rendezvous-night5/bc

collect  runs the scripted coordinator in RendezvousPairEnv (training split, the config's reward, curriculum off) on
         randomized training starts (sample_start, never the eval set) at the stage's bc.dist_m distances, and records
         every step's per-duck observation (exactly what the RL policy sees), the scripted per-duck action (in the
         policy's [-1, 1] action space), the reward, and each duck's discounted return-to-go (ppo gamma) from that step.
         Episodes end as in training: both docked (arrived), a fall, or max_steps.
train    fits a fresh MlpPolicy (configs/copush.yaml's PPO architecture, as nights 1-4) by supervised learning: MSE
         between the policy's mean action and the scripted action (the action head), plus MSE between its value
         estimate and the return-to-go (the value head, so PPO does not start with a random critic). 80/20 split by
         episode (never by step, so near-identical steps of one episode do not land on both sides). Adam, minibatches,
         until the validation action loss has not improved for bc.patience epochs (or bc.max_epochs); the best epoch's
         weights are kept. The action log-std is set to bc.init_log_std (PPO's own initial value, 0, means a standard
         deviation of 1 on a [-1, 1] action, which would bury the cloned behavior in noise). Writes <out>/bc.zip (a
         PPO zip: rendezvous_eval.py and train_rendezvous.py --init load it), <out>/loss.jsonl (one row per epoch),
         <out>/bc.json (summary).
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

BC_DEFAULTS = {"episodes": 6000, "seed": 777, "dist_m": [0.15, 0.80], "workers": 8, "val_frac": 0.2, "lr": 1e-3,
               "batch_size": 4096, "max_epochs": 300, "patience": 15, "value_coef": 0.05, "init_log_std": -1.0}


def bc_settings(stage: dict) -> dict:
    return {**BC_DEFAULTS, **(stage.get("bc") or {})}


def demo_config(cfg: dict, dist_m) -> dict:
    """The training config with the curriculum off and starts drawn at dist_m. (RendezvousPairEnv's reward normalizer
    comes from start.dist_m[1]; _collect_chunk resets it to the training config's value, so rewards and the value
    targets are exactly the training reward.)"""
    import copy
    c = copy.deepcopy(cfg)
    rv = c.setdefault("rendezvous", {})
    rv.setdefault("curriculum", {})["enabled"] = False
    rv.setdefault("start", {})["dist_m"] = list(dist_m)
    return c


def _collect_chunk(args):
    cfg, seeds, gamma, max_start_dist = args
    from copush.rendezvous import RendezvousPairEnv, ScriptedRendezvous
    env = RendezvousPairEnv(cfg, split="train")
    env.max_start_dist = max_start_dist                 # the reward normalizer of the training config
    obs_l, act_l, ret_l, ep_l, info_l = [], [], [], [], []
    for seed in seeds:
        obs, _ = env.reset(seed=int(seed))
        act = ScriptedRendezvous(env.rv)
        ep_obs, ep_act, ep_rew = [], [], []
        reason = None
        while True:
            a = np.asarray(act(None), dtype=np.float32).reshape(2, 2)
            ep_obs.append(obs)
            ep_act.append(a)
            obs, r, te, tr, info = env.step(a)
            ep_rew.append(np.asarray(r, dtype=np.float32))
            if te or tr:
                reason = info["reason"]
                break
        rew = np.stack(ep_rew)                          # (T, 2)
        ret = np.zeros_like(rew)
        g = np.zeros(2, dtype=np.float32)
        for t in range(len(rew) - 1, -1, -1):
            g = rew[t] + gamma * g
            ret[t] = g
        obs_l.append(np.stack(ep_obs).reshape(-1, np.stack(ep_obs).shape[-1]))   # (T*2, 14): duck_a, duck_b per step
        act_l.append(np.stack(ep_act).reshape(-1, 2))
        ret_l.append(ret.reshape(-1))
        ep_l.append(np.full(2 * len(rew), int(seed), dtype=np.int64))
        info_l.append({"seed": int(seed), "steps": len(rew), "reason": reason})
    env.close()
    return obs_l, act_l, ret_l, ep_l, info_l


def collect(a) -> int:
    from copush.experiments import load_stage
    from copush.rendezvous import settings
    stage, cfg = load_stage(a.config)
    bc = bc_settings(stage)
    n = int(a.episodes or bc["episodes"])
    workers = int(a.workers or bc["workers"])
    gamma = float(cfg["ppo"]["gamma"])
    max_start_dist = settings(cfg)["start"]["dist_m"][1]
    dcfg = demo_config(cfg, bc["dist_m"])
    seeds = bc["seed"] * 100000 + np.arange(n)
    chunks = [(dcfg, list(c), gamma, max_start_dist) for c in np.array_split(seeds, max(1, workers * 4)) if len(c)]
    t0 = time.perf_counter()
    with mp.get_context("spawn").Pool(workers) as pool:
        parts = pool.map(_collect_chunk, chunks)
    obs = np.concatenate([x for p in parts for x in p[0]])
    act = np.concatenate([x for p in parts for x in p[1]])
    ret = np.concatenate([x for p in parts for x in p[2]])
    ep = np.concatenate([x for p in parts for x in p[3]])
    infos = [x for p in parts for x in p[4]]
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez_compressed(out, obs=obs, act=act, ret=ret, episode=ep)
    reasons = {}
    for i in infos:
        reasons[i["reason"]] = reasons.get(i["reason"], 0) + 1
    summary = {"episodes": len(infos), "pairs": int(len(obs)), "outcomes": reasons,
               "docking_rate": reasons.get("arrived", 0) / max(len(infos), 1),
               "mean_steps": float(np.mean([i["steps"] for i in infos])), "dist_m": bc["dist_m"], "seed": bc["seed"],
               "wall_s": round(time.perf_counter() - t0, 1)}
    with open(os.path.splitext(out)[0] + ".json", "w") as f:
        json.dump(summary, f, indent=1)
    print(f"collected {summary['episodes']} episodes, {summary['pairs']} (obs, action) pairs; scripted docked "
          f"{100 * summary['docking_rate']:.1f}% of them; outcomes {reasons}; {summary['wall_s'] / 60:.1f} min", flush=True)
    return 0


class _Spaces:
    """A stand-in env with the per-duck spaces of RendezvousVecEnv (DuckVecEnv), so the saved PPO zip matches them."""

    @staticmethod
    def make():
        import gymnasium as gym
        from gymnasium import spaces

        from copush.rendezvous import OBS_NAMES

        class E(gym.Env):
            observation_space = spaces.Box(-np.inf, np.inf, shape=(len(OBS_NAMES),), dtype=np.float32)
            action_space = spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)

            def reset(self, *, seed=None, options=None):
                return np.zeros(len(OBS_NAMES), dtype=np.float32), {}

            def step(self, action):
                return np.zeros(len(OBS_NAMES), dtype=np.float32), 0.0, True, False, {}
        return E()


def train(a) -> int:
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from copush.experiments import load_stage
    stage, cfg = load_stage(a.config)
    bc = bc_settings(stage)
    if a.max_epochs:
        bc["max_epochs"] = a.max_epochs
    pc = cfg["ppo"]
    torch.manual_seed(bc["seed"])
    rng = np.random.default_rng(bc["seed"])
    d = np.load(a.data if os.path.isabs(a.data) else os.path.join(ROOT, a.data))
    obs, act, ret, ep = d["obs"], d["act"], d["ret"], d["episode"]
    eps = np.unique(ep)
    val_eps = set(rng.choice(eps, size=max(1, int(round(bc["val_frac"] * len(eps)))), replace=False).tolist())
    is_val = np.array([e in val_eps for e in ep])
    tr_idx, va_idx = np.where(~is_val)[0], np.where(is_val)[0]
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)

    model = PPO("MlpPolicy", DummyVecEnv([_Spaces.make]), n_steps=pc["n_steps"], batch_size=pc["batch_size"],
                n_epochs=pc["n_epochs"], learning_rate=pc["learning_rate"], gamma=pc["gamma"], gae_lambda=pc["gae_lambda"],
                clip_range=pc["clip_range"], ent_coef=pc["ent_coef"], seed=bc["seed"], device="cpu", verbose=0)
    pol = model.policy
    with torch.no_grad():
        pol.log_std.fill_(float(bc["init_log_std"]))
    params = [p for n, p in pol.named_parameters() if n != "log_std"]
    opt = torch.optim.Adam(params, lr=float(bc["lr"]))
    O, A, R = (torch.as_tensor(x, dtype=torch.float32) for x in (obs, act, ret))

    def heads(o):
        f = pol.extract_features(o)
        lpi, lvf = pol.mlp_extractor(f)
        return pol.action_net(lpi), pol.value_net(lvf).squeeze(-1)

    def losses(idx):
        with torch.no_grad():
            la = lv = 0.0
            for s in range(0, len(idx), 65536):
                j = torch.as_tensor(idx[s:s + 65536])
                mu, v = heads(O[j])
                la += float(((mu - A[j]) ** 2).mean(-1).sum())
                lv += float(((v - R[j]) ** 2).sum())
            return la / len(idx), lv / len(idx)

    best, best_state, since, rows = float("inf"), None, 0, []
    log = open(os.path.join(out, "loss.jsonl"), "w")
    t0 = time.perf_counter()
    for epoch in range(1, int(bc["max_epochs"]) + 1):
        perm = rng.permutation(tr_idx)
        for s in range(0, len(perm), int(bc["batch_size"])):
            j = torch.as_tensor(perm[s:s + int(bc["batch_size"])])
            mu, v = heads(O[j])
            loss = ((mu - A[j]) ** 2).mean() + float(bc["value_coef"]) * ((v - R[j]) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
        tr_a, tr_v = losses(tr_idx)
        va_a, va_v = losses(va_idx)
        row = {"epoch": epoch, "train_action_mse": round(tr_a, 6), "val_action_mse": round(va_a, 6),
               "train_value_mse": round(tr_v, 4), "val_value_mse": round(va_v, 4), "wall_s": round(time.perf_counter() - t0, 1)}
        rows.append(row)
        log.write(json.dumps(row) + "\n")
        log.flush()
        if va_a < best - 1e-6:
            best, since = va_a, 0
            best_state = {k: v.detach().clone() for k, v in pol.state_dict().items()}
        else:
            since += 1
        if epoch == 1 or epoch % 10 == 0:
            print(f"epoch {epoch}: action MSE train {tr_a:.5f} val {va_a:.5f}; value MSE train {tr_v:.3f} val {va_v:.3f}",
                  flush=True)
        if since >= int(bc["patience"]):
            break
    log.close()
    pol.load_state_dict(best_state)
    model.save(os.path.join(out, "bc.zip"))
    best_row = min(rows, key=lambda r: r["val_action_mse"])
    summary = {"pairs_train": int(len(tr_idx)), "pairs_val": int(len(va_idx)), "episodes_val": len(val_eps),
               "epochs_run": rows[-1]["epoch"], "best_epoch": best_row["epoch"], "best": best_row,
               "stopped": "plateau" if since >= int(bc["patience"]) else "max_epochs",
               "action_var": float(A.var(0).mean()), "settings": bc}
    with open(os.path.join(out, "bc.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(f"BC done: best epoch {best_row['epoch']} of {rows[-1]['epoch']} ({summary['stopped']}), val action MSE "
          f"{best_row['val_action_mse']:.5f} (action variance {summary['action_var']:.4f}); saved {os.path.join(out, 'bc.zip')}",
          flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--config", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--episodes", type=int, default=0, help="override bc.episodes (dry runs)")
    c.add_argument("--workers", type=int, default=0)
    t = sub.add_parser("train")
    t.add_argument("--config", required=True)
    t.add_argument("--data", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--max-epochs", type=int, default=0, help="override bc.max_epochs (dry runs)")
    a = ap.parse_args()
    return collect(a) if a.cmd == "collect" else train(a)


if __name__ == "__main__":
    sys.exit(main())
