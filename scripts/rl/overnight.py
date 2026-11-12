#!/usr/bin/env python3
"""Overnight queue: PPO experiments from a YAML list, one after another, restartable.

    nohup scripts/rl/overnight.sh --config configs/overnight.yaml >> runs/overnight-<date>/queue.log 2>&1 &
    scripts/rl.sh scripts/rl/overnight.py --config configs/overnight.yaml --summary     # rewrite SUMMARY.md only

The YAML (configs/overnight.yaml) has a `reference` block of overrides on configs/copush.yaml and a
list of `runs`, each with its own `overrides` on top of the reference (ONE change per run).

Queue (this process): detaches into its own session, keeps the Mac awake (caffeinate -w), then for
each run in order
    done                      skip
    crashed max_attempts x    skip
    otherwise                 train it in a child process (resumes from its last checkpoint)
A child that exits non-zero is logged to <out>/crashes.log and the queue goes on. With a `deadline`
each run gets an equal share of the time left (minus deadline_reserve_s) and stops training when
its share is used up, so the queue ends on time even if the machine is slower than measured. After every run
<out>/SUMMARY.md is rewritten. `kill $(cat <out>/queue.pid)` stops the queue and the running child;
starting the queue again continues where it stopped.

One run (child, --run-one NAME) writes <out>/runs/<NAME>/: config.yaml, train.log, status.json,
state.json + checkpoints/ckpt_<step>.zip (every checkpoint_every steps, newest only), tb/, videos/
(VideoEvalCallback, capped at max_videos), model.zip, results.json.
    eval           one deterministic episode on rl.eval_seed every rl.eval_every steps, always on
                   the run's layout (the curriculum run trains on its levels but is evaluated on
                   the final one, so the eval curves are comparable)
    early stop     the eval returns of the last early_stop.flat_steps steps span less than
                   early_stop.flat_range
    final numbers  the last eval (fixed start), and eval_episodes deterministic episodes with the
                   box randomized (env.random, eval seeds) for success rate / falls / box lost
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

from copush.config import _merge, dump_config, load_config  # noqa: E402


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def load_queue(path: str) -> dict:
    with open(path) as f:
        q = yaml.safe_load(f)
    q["_path"] = os.path.abspath(path)
    q["_out"] = os.path.join(ROOT, q["out"])
    names = [r["name"] for r in q["runs"]]
    if len(set(names)) != len(names):
        raise ValueError("run names must be unique")
    return q


def run_dir(q: dict, name: str) -> str:
    return os.path.join(q["_out"], "runs", name)


def run_cfg(q: dict, run: dict) -> dict:
    return load_config(overrides=_merge(q.get("reference") or {}, run.get("overrides") or {}))


def read_json(path: str, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


# ── one run (child process) ──────────────────────────────────────────────────

def _prune_after(videos_dir: str, step: int) -> None:
    """Drop evals / videos recorded after the checkpoint being resumed (they will be redone)."""
    jl = os.path.join(videos_dir, "evals.jsonl")
    if os.path.exists(jl):
        keep = [ln for ln in open(jl) if ln.strip() and json.loads(ln)["step"] <= step]
        with open(jl, "w") as f:
            f.writelines(keep)
    idx = os.path.join(videos_dir, "index.md")
    if os.path.exists(idx):
        out = []
        for ln in open(idx):
            if ln.startswith("| [step_"):
                if int(ln.split("step_")[1].split("_")[0]) > step:
                    continue
            out.append(ln)
        with open(idx, "w") as f:
            f.writelines(out)
    for name in os.listdir(videos_dir) if os.path.isdir(videos_dir) else []:
        if name.startswith("step_") and name.endswith(".mp4") and int(name.split("_")[1]) > step:
            os.remove(os.path.join(videos_dir, name))


def train_one(q: dict, run: dict, until: float = 0.0) -> int:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CallbackList
    from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor

    from copush.env import CoPushEnv, make_env
    from copush.rl_callbacks import CurriculumCallback, VideoEvalCallback, behaviors, decide, run_episode
    from copush.rl_eval import run_episodes, summarize

    name = run["name"]
    rd = run_dir(q, name)
    os.makedirs(os.path.join(rd, "checkpoints"), exist_ok=True)
    cfg = run_cfg(q, run)
    dump_config(cfg, os.path.join(rd, "config.yaml"))
    pc = cfg["ppo"]
    total = int(run.get("steps", q["steps_per_run"]))
    state_path = os.path.join(rd, "state.json")
    state = read_json(state_path, {}) or {}
    ckpt = state.get("checkpoint") and os.path.join(rd, state["checkpoint"])
    if not (ckpt and os.path.exists(ckpt)):
        state, ckpt = {}, None
    parent = os.getppid()

    vec = VecMonitor(SubprocVecEnv([make_env(cfg) for _ in range(pc["n_envs"])]))
    tb = os.path.join(rd, "tb")
    if ckpt:
        model = PPO.load(ckpt, env=vec, device="cpu", tensorboard_log=tb)
        vec.seed(pc["seed"] + model.num_timesteps)
        _prune_after(os.path.join(rd, "videos"), model.num_timesteps)
        log(f"{name}: resuming from step {model.num_timesteps} of {total} ({state['checkpoint']})")
    else:
        _prune_after(os.path.join(rd, "videos"), -1)          # a restart from scratch: no stale evals
        vec.seed(pc["seed"])
        model = PPO("MlpPolicy", vec, n_steps=pc["n_steps"], batch_size=pc["batch_size"], n_epochs=pc["n_epochs"],
                    learning_rate=pc["learning_rate"], gamma=pc["gamma"], gae_lambda=pc["gae_lambda"],
                    clip_range=pc["clip_range"], ent_coef=pc["ent_coef"], seed=pc["seed"], device="cpu",
                    tensorboard_log=tb, verbose=0)
        log(f"{name}: starting, {total} steps, layout {cfg['env']['layout']} target {cfg['layouts'][cfg['env']['layout']]['target']}, "
            f"reward {cfg['reward']['version']}, seed {pc['seed']}")

    eval_cfg = copy.deepcopy(cfg)
    eval_cfg["env"]["curriculum"]["enabled"] = False            # always evaluate on the run's layout
    es = q["early_stop"]

    class QueueCallback(VideoEvalCallback):
        def __init__(self):
            super().__init__(eval_cfg, rd, verbose=1)
            self.best = state.get("best") if state.get("best") is not None else -math.inf
            self.seen = set(state.get("seen", []))
            self.n_evals = state.get("n_evals", 0)
            self.last_eval = state.get("last_eval", 0)
            self.videos = [tuple(v) for v in state.get("videos", [])]
            self.history = [tuple(h) for h in state.get("history", [])]      # (step, eval return)
            self.last_ckpt = state.get("step", 0)
            self.wall0, self.t0 = state.get("wall_s", 0.0), time.perf_counter()
            self.early_stopped = self.time_capped = False
            self.cur = None

        def wall(self) -> float:
            return self.wall0 + time.perf_counter() - self.t0

        def evaluate(self, final: bool = False):
            stats = run_episode(self.env, self._act, self.seed)
            reason = "final" if final else decide(stats, self.best, self.seen, self.margin, self.n_evals == 0)
            if reason not in (None, "final") and len(self.videos) >= q["max_videos"] - 1:
                reason = None                                    # cap; one slot is kept for the final video
            if reason is not None:
                self.vlog.record(self.env, self._act, self.num_timesteps, reason, seed=self.seed)
                self.videos.append((self.num_timesteps, reason))
            self.n_evals += 1
            self.best = max(self.best, stats["return"])
            self.seen |= behaviors(stats)
            self.history.append((self.num_timesteps, stats["return"]))
            share = stats["push_share"]
            self.logger.record("eval/return", stats["return"])
            self.logger.record("eval/success", float(stats["reason"] == "success"))
            self.logger.record("eval/final_dist", stats["final_dist"])
            self.logger.record("eval/push_share_a", 0.0 if math.isnan(share["duck_a"]) else share["duck_a"])
            with open(self.jsonl, "a") as f:
                f.write(json.dumps({"step": self.num_timesteps, "video": reason, **stats}) + "\n")
            log(f"{name}: eval @ {self.num_timesteps}: return {stats['return']:+.2f} ({stats['reason']}), "
                f"video: {reason}, wall {self.wall() / 60:.1f} min")
            return stats, reason

        def flat(self) -> bool:
            now = self.num_timesteps
            window = [r for s, r in self.history if s > now - es["flat_steps"]]
            covered = self.history and self.history[0][0] <= now - es["flat_steps"] + self.every
            return bool(covered and len(window) >= 3 and max(window) - min(window) < es["flat_range"])

        def checkpoint(self) -> None:
            step = self.num_timesteps
            rel = os.path.join("checkpoints", f"ckpt_{step}.zip")
            self.model.save(os.path.join(rd, rel))
            write_json(state_path, {
                "step": step, "checkpoint": rel, "best": None if self.best == -math.inf else self.best,
                "seen": sorted(self.seen), "n_evals": self.n_evals, "last_eval": self.last_eval,
                "videos": self.videos, "history": self.history, "wall_s": self.wall(),
                "curriculum_level": self.cur.level if self.cur else 0,
                "curriculum_history": self.cur.history if self.cur else []})
            for f in os.listdir(os.path.join(rd, "checkpoints")):
                if f != os.path.basename(rel):
                    os.remove(os.path.join(rd, "checkpoints", f))
            self.last_ckpt = step
            log(f"{name}: checkpoint at {step}")

        def _on_step(self) -> bool:
            if run.get("crash_at_step") and self.num_timesteps >= run["crash_at_step"]:
                raise RuntimeError(f"forced crash at step {self.num_timesteps} (crash_at_step, queue test)")
            if os.getppid() != parent:
                raise SystemExit(f"{name}: the queue process is gone, stopping (resume by restarting the queue)")
            if self.num_timesteps - self.last_eval >= self.every:
                self.last_eval = self.num_timesteps
                self.evaluate()
                if self.flat():
                    self.early_stopped = True
                    log(f"{name}: early stop at {self.num_timesteps}: eval return flat (range < {es['flat_range']}) "
                        f"for {es['flat_steps']} steps")
                    return False
            if self.num_timesteps - self.last_ckpt >= q["checkpoint_every"]:
                self.checkpoint()
            if until and time.time() > until:
                self.time_capped = True
                log(f"{name}: time cap reached at {self.num_timesteps} of {total} steps (queue deadline), stopping")
                return False
            return True

    cb = QueueCallback()
    cbs = [cb]
    if cfg["env"]["curriculum"]["enabled"]:
        cur = CurriculumCallback(cfg, verbose=1)
        cur.level = state.get("curriculum_level", 0)
        cur.history = list(state.get("curriculum_history", []))
        vec.env_method("set_curriculum_level", cur.level)
        cb.cur = cur
        cbs.append(cur)
    remaining = total - model.num_timesteps
    if remaining > 0:
        model.learn(total_timesteps=remaining, callback=CallbackList(cbs), tb_log_name="ppo",
                    reset_num_timesteps=ckpt is None)
    else:                                                        # killed between the last step and results.json
        cb.init_callback(model)
        cb.evaluate(final=True)
    cb.checkpoint()
    vec.close()
    model.save(os.path.join(rd, "model.zip"))

    act = lambda obs: model.predict(obs, deterministic=True)[0]          # noqa: E731
    rand_cfg = copy.deepcopy(eval_cfg)
    rand_cfg["env"]["randomize"] = True
    summ = summarize(run_episodes(CoPushEnv(rand_cfg, split="eval"), lambda s: act, q["eval_episodes"],
                                  seed0=cfg["rl"]["eval_seed"]))
    vdir = os.path.join(rd, "videos")
    evals = [json.loads(ln) for ln in open(os.path.join(vdir, "evals.jsonl")) if ln.strip()]
    vids = sorted(f for f in os.listdir(vdir) if f.endswith(".mp4"))
    with_video = [e for e in evals if e["video"]]
    best_v = max(with_video, key=lambda e: e["return"], default=None)
    best = max(evals, key=lambda e: e["return"])
    final = evals[-1]
    pick = lambda e: e and next((f for f in vids if f.startswith(f"step_{e['step']}_")), None)   # noqa: E731
    brief = lambda e: {"step": e["step"], "return": e["return"], "reason": e["reason"],          # noqa: E731
                       "final_dist": e["final_dist"], "final_yaw_deg": e["final_yaw_deg"]}
    write_json(os.path.join(rd, "results.json"), {
        "name": name, "change": run.get("change", ""), "steps": int(model.num_timesteps), "steps_planned": total,
        "wall_s": cb.wall(), "early_stopped": cb.early_stopped, "time_capped": cb.time_capped,
        "layout_target": cfg["layouts"][cfg["env"]["layout"]]["target"], "reward_version": cfg["reward"]["version"],
        "seed": pc["seed"], "final_eval": brief(final), "best_eval": brief(best),
        "best_video": pick(best_v), "best_video_eval": best_v and brief(best_v), "final_video": pick(final),
        "randomized": summ, "eval_flags": sorted(k[5:] for k in cb.seen if k.startswith("flag:")),
        "eval_endings": sorted(k[4:] for k in cb.seen if k.startswith("end:")),
        "eval_curve": [(e["step"], e["return"], e["reason"]) for e in evals],
        "curriculum": {"level": cb.cur.level, "history": cb.cur.history} if cb.cur else None, "videos": vids})
    log(f"{name}: done, {model.num_timesteps} steps in {cb.wall() / 60:.1f} min, final eval {final['return']:+.2f} "
        f"({final['reason']}), best {best['return']:+.2f}, randomized success {100 * summ['success_rate']:.0f}%")
    return 0


# ── SUMMARY.md ───────────────────────────────────────────────────────────────

def write_summary(q: dict) -> str:
    out = q["_out"]
    now = dt.datetime.now()
    md = [f"# Overnight queue summary ({os.path.basename(out)})", "",
          f"Rewritten after every run; last update {now:%Y-%m-%d %H:%M:%S}. Config: `{os.path.relpath(q['_path'], ROOT)}`.",
          ""]
    ref = (q.get("reference") or {})
    try:
        cfg = run_cfg(q, {})
        tg = cfg["layouts"][cfg["env"]["layout"]]["target"]
        md += [f"Reference: reward {cfg['reward']['version']}, layout `{cfg['env']['layout']}` (in-contact start, target "
               f"{tg['x'] - cfg['box']['x']:.2f} m ahead, {abs(tg['y'] - cfg['box']['y']):.2f} m to the "
               f"{'right' if tg['y'] < cfg['box']['y'] else 'left'}), seed {cfg['ppo']['seed']}, "
               f"{q['steps_per_run']} steps per run. Each run differs from it by one thing.", ""]
    except Exception as e:                                       # the summary must never stop the queue
        md += [f"(reference config could not be loaded: {e})", ""]
    del ref
    md += ["| # | run | change | status | steps | final eval return (ending) | best eval return (step) | "
           f"success, {q['eval_episodes']} randomized | falls | box lost | push share A / B | monitor flags | "
           "wall time | early stop | videos |", "|" + "---|" * 15]
    notes = []
    for i, run in enumerate(q["runs"], 1):
        name = run["name"]
        rd = run_dir(q, name)
        st = read_json(os.path.join(rd, "status.json"), {}) or {}
        res = read_json(os.path.join(rd, "results.json")) if st.get("status") == "done" else None
        change = run.get("change", "")
        if res:
            s = res["randomized"]
            n = s["n"]
            sh = s["push_share_a_mean"]
            share = "-" if sh is None or (isinstance(sh, float) and math.isnan(sh)) else f"{100 * sh:.0f} / {100 - 100 * sh:.0f}%"
            flags = sorted(set(res["eval_flags"]) | set(s["flag_episodes"]))
            rel = f"runs/{name}/videos"
            vids = " · ".join(f"[{label}]({rel}/{f})" for label, f in (("best", res["best_video"]), ("final", res["final_video"])) if f)
            vids += f" · [all]({rel}/index.md)"
            md.append(f"| {i} | {name} | {change} | done | {res['steps']} | {res['final_eval']['return']:+.2f} "
                      f"({res['final_eval']['reason']}) | {res['best_eval']['return']:+.2f} ({res['best_eval']['step']}) | "
                      f"{100 * s['success_rate']:.0f}% | {s['episodes_with_fall']}/{n} | {s['box_lost']}/{n} | {share} | "
                      f"{', '.join(flags) or 'none'} | {res['wall_s'] / 60:.0f} min | "
                      f"{'YES (flat eval)' if res['early_stopped'] else 'time cap' if res.get('time_capped') else 'no'} | {vids} |")
            if res.get("curriculum"):
                notes.append(f"- `{name}`: curriculum ended at level {res['curriculum']['level']} "
                             f"(0-based, {len(run_cfg(q, run)['env']['curriculum']['distances'])} levels).")
        else:
            status = st.get("status", "pending")
            extra = ""
            if status == "crashed":
                extra = f" x{st.get('crashes', 1)} (exit {st.get('returncode')}; see crashes.log, runs/{name}/train.log)"
            if status == "running":
                p = read_json(os.path.join(rd, "state.json"), {}) or {}
                extra = f" (last checkpoint: step {p.get('step', 0)})"
            md.append(f"| {i} | {name} | {change} | {status}{extra} |" + " - |" * 11)
    md += ["", "Columns: *final / best eval return* are the single deterministic evaluation episode on the eval seed with "
           "the fixed start (the eval curve in `runs/<run>/videos/evals.jsonl`, best = highest over training). *success, "
           "falls, box lost, push share* are the final policy on episodes with the box randomized (position, yaw, mass; "
           "eval seeds), the same protocol as the reachability sweep. *monitor flags* are RewardMonitor flag kinds seen in "
           "any evaluation. *best* video = the saved video with the highest return (videos are only saved on a change).", ""]
    if notes:
        md += notes + [""]
    heat = os.path.join(out, "reachability", "heatmap.png")
    if os.path.exists(heat):
        md += ["## Reachability (scripted baselines)", "", "![reachability heatmap](reachability/heatmap.png)", "",
               "[table](reachability/table.md) · [DECISIONS.md](DECISIONS.md)", ""]
    crashes = os.path.join(out, "crashes.log")
    if os.path.exists(crashes):
        md += ["Crashes: [crashes.log](crashes.log)", ""]
    path = os.path.join(out, "SUMMARY.md")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(md))
    os.replace(tmp, path)
    return path


# ── queue ────────────────────────────────────────────────────────────────────

def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    try:
        cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
    except OSError:
        return True
    return "overnight.py" in cmd


def run_queue(q: dict) -> int:
    out = q["_out"]
    os.makedirs(os.path.join(out, "runs"), exist_ok=True)
    pid_path = os.path.join(out, "queue.pid")
    old = read_json(pid_path)
    if isinstance(old, int) and old != os.getpid() and pid_alive(old):
        log(f"a queue is already running (pid {old}); not starting another")
        return 2
    try:
        os.setsid()                                              # survive the launching shell / session
    except OSError:
        pass
    write_json(pid_path, os.getpid())
    try:
        subprocess.Popen(["caffeinate", "-ims", "-w", str(os.getpid())], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        log(f"caffeinate not started: {e}")
    child = {"p": None}

    def stop(signum, _frame):
        log(f"signal {signum}: stopping the queue")
        p = child["p"]
        if p is not None and p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)
                p.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except OSError:
                    pass
        try:
            write_summary(q)
        finally:
            os._exit(143)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log(f"queue start (pid {os.getpid()}): {len(q['runs'])} runs, {q['steps_per_run']} steps each, out {q['out']}, "
        f"deadline {q.get('deadline') or 'none'}")
    deadline = dt.datetime.strptime(str(q["deadline"]), "%Y-%m-%d %H:%M").timestamp() if q.get("deadline") else 0.0

    def is_open(r) -> bool:
        s_ = read_json(os.path.join(run_dir(q, r["name"]), "status.json"), {}) or {}
        return not (s_.get("status") == "done" or
                    (s_.get("status") == "crashed" and s_.get("crashes", 0) >= q.get("max_attempts", 2)))

    write_summary(q)
    for run in q["runs"]:
        name = run["name"]
        rd = run_dir(q, name)
        os.makedirs(rd, exist_ok=True)
        st_path = os.path.join(rd, "status.json")
        st = read_json(st_path, {}) or {}
        if st.get("status") == "done" and os.path.exists(os.path.join(rd, "results.json")):
            log(f"{name}: already done, skipping")
            continue
        if st.get("status") == "crashed" and st.get("crashes", 0) >= q.get("max_attempts", 2):
            log(f"{name}: crashed {st['crashes']} times, skipping")
            continue
        st.update({"status": "running", "started": st.get("started") or f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"})
        write_json(st_path, st)
        write_summary(q)                  # shows this run as running
        until = 0.0                       # this run's share of the time left before the deadline
        if deadline:
            left = deadline - q.get("deadline_reserve_s", 600) - time.time()
            n_open = sum(is_open(r) for r in q["runs"])
            if left > 0:
                until = time.time() + left / max(1, n_open)
                log(f"{name}: time budget {left / max(1, n_open) / 60:.0f} min ({n_open} runs left before the deadline)")
            else:
                log(f"{name}: the deadline has passed, running without a time cap")
        with open(os.path.join(rd, "train.log"), "a") as lf:
            p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--config", q["_path"], "--run-one", name,
                                  "--until", str(until)],
                                 stdout=lf, stderr=subprocess.STDOUT, start_new_session=True, cwd=ROOT)
            child["p"] = p
            log(f"{name}: started (pid {p.pid}), log runs/{name}/train.log")
            rc = p.wait()
            child["p"] = None
        if rc == 0 and os.path.exists(os.path.join(rd, "results.json")):
            st.update({"status": "done", "finished": f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}", "returncode": 0})
            log(f"{name}: finished")
        else:
            st.update({"status": "crashed", "crashes": st.get("crashes", 0) + 1, "returncode": rc,
                       "finished": f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"})
            try:
                tail = "".join(open(os.path.join(rd, "train.log")).readlines()[-25:])
            except OSError:
                tail = ""
            with open(os.path.join(out, "crashes.log"), "a") as f:
                f.write(f"\n===== {dt.datetime.now():%Y-%m-%d %H:%M:%S}  {name}  exit code {rc}  (crash {st['crashes']}) =====\n{tail}")
            log(f"{name}: CRASHED (exit {rc}), see crashes.log; continuing with the next run")
        write_json(st_path, st)
        try:
            write_summary(q)
        except Exception as e:                                   # never let the summary stop the queue
            log(f"summary failed: {e!r}")
    log("queue finished")
    try:
        os.remove(pid_path)
    except OSError:
        pass
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=os.path.join(ROOT, "configs", "overnight.yaml"))
    p.add_argument("--run-one", metavar="NAME", help="train one run of the queue in this process (the queue uses this)")
    p.add_argument("--until", type=float, default=0.0, help="with --run-one: stop training at this epoch time")
    p.add_argument("--summary", action="store_true", help="only rewrite SUMMARY.md")
    args = p.parse_args()
    q = load_queue(args.config)
    if args.summary:
        print(write_summary(q))
        return 0
    if args.run_one:
        run = next(r for r in q["runs"] if r["name"] == args.run_one)
        return train_one(q, run, until=args.until)
    return run_queue(q)


if __name__ == "__main__":
    sys.exit(main())
