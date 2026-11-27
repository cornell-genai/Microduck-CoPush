#!/usr/bin/env python3
"""Episode review: watch sampled evaluation episodes in the browser and label them, blind to the metric.

    scripts/rl.sh scripts/review/serve.py --run r6-dock-payout --seed-policy s1 --n 30 --reviewer ashwin
    scripts/rl.sh scripts/review/serve.py --run d2-steering-night5 --seed-policy l2_s2 --reviewer ashwin \
        --results runs/d2-steering/night5/results/eval_L2/comparison.json \
        --policy runs/d2-steering-night5/l2-s2/model.zip@partner@standstill

Reads the per-episode results an evaluation wrote (rendezvous_eval.py results.json for full-pipeline runs,
compare_policies.py comparison.json for push-only runs), samples episodes evenly from three groups (successes,
failures, suspicious successes), replays each one with the evaluation's start and seed to a GIF (cached under
runs/review-cache/, git-ignored) and serves one page (review.html) where the reviewer labels the episode BEFORE the
metric's verdict is shown. Labels go to experiments/<run>/reviews/<reviewer>_<date>.json after every label; starting
the same session again resumes it. scripts/review/summarize.py reports the agreement with the metric.

--run            the run's name: the folder under runs/ (also runs/*-<run>) or experiments/ that holds its results
--seed-policy    which policy of the run: s1, s2 (rendezvous seeds) or the policy's name in comparison.json (l2_s2)
--results        the per-episode results file, when it is not found from --run
--policy         push-only runs: the policy as compare_policies.py took it (model.zip@partner@standstill); a
                 rendezvous results file names its own policy and push policy
--n, --group, --seed   sample size (30), only one group (success, failure, suspicious), sampling seed (0)
--coop-min       cooperative threshold (default: metrics.cooperative_share of configs/copush.yaml, 0.25). The
                 cooperative result is read from the results file's contact impulses (contact_impulse) through
                 copush/cooperation.py; only an old file without those fields falls back to its push share. The
                 source is printed at start, saved in the session file and in each label, and shown in the summary.
--out-dir        where the label file goes (default experiments/<run>/reviews)
--render-only    render the sampled clips, print whether each replay matched, and exit
--port, --no-open      the local port (8765); do not open the browser
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import subprocess
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts", "rl"), HERE]

import reviewlib as rl  # noqa: E402

FPS = 10                      # GIF frames per second of simulated time: 1x in the page is real time
SIZE = (480, 270)
CACHE = "runs/review-cache"   # under the git-ignored runs/
RENDER_VERSION = 2            # bump when the rendering or the replay check changes, so cached GIFs are redone


# ── rendering (in one worker process that keeps the env and the policies loaded) ─────────────────────────────

# what a replay must reproduce: the fields rendezvous_eval.py wrote (the shares and impulses to the precision it stored)
REPLAY_FIELDS = ("id", "arrived", "rv_steps", "fell_rv", "assign", "pos_err_cm", "yaw_err_deg", "hit_box", "hit_ducks",
                 "push_reason", "push_steps", "push_success", "push_share_a", "contact_share_a", "contact_impulse",
                 "push_impulse", "cooperative")


def replay_match(replayed: dict, recorded: dict, fields=REPLAY_FIELDS) -> dict:
    """Compare a replayed episode with the recorded one on every field both have. -> {"reproduced", "checked",
    "mismatch": {field: [recorded, replayed]}}. Stored values are rounded (4 places for shares and impulses, 2 for
    errors), and the replay is rounded the same way before it gets here, so equality is exact."""
    checked = [k for k in fields if k in recorded]
    bad = {k: [recorded[k], replayed.get(k)] for k in checked if replayed.get(k) != recorded[k]}
    return {"reproduced": not bad, "checked": checked, "mismatch": bad}


def _setup_rendezvous(spec: dict):
    import rendezvous_eval as rve
    rve._W.clear()
    rve._init(spec["set"], spec["policy_file"], spec["push"] or rve.PUSH, spec["no_push"], spec["episode_steps"])
    env, rv = rve._W["env"], rve._W["rv"]

    def run(job: dict, hook, phase: list) -> dict:
        begin = env.begin_push_phase

        def begin_push(*a, **k):
            phase[0] = "push"
            return begin(*a, **k)
        phase[0] = "rendezvous"
        rv.frame_hook = env.frame_hook = hook
        env.begin_push_phase = begin_push
        try:
            out = rve.episode(job["i"])
        finally:
            rv.frame_hook = env.frame_hook = None
            del env.begin_push_phase
        return replay_match(out, job["raw"])
    return env, run


def _setup_push(spec: dict):
    from copush.env import CoPushEnv
    from copush.experiments import load_stage, load_test_set
    from test_set import make_act_factory
    _, cfg = load_stage(spec["config"])          # the same settings as scripts/rl/compare_policies.py _run
    pol = spec["policy_spec"]
    if spec.get("max_steps"):
        cfg["env"]["max_steps"] = int(spec["max_steps"])
    if isinstance(pol, dict) and pol.get("standstill"):
        cfg["env"]["stand_still"] = {**cfg["env"]["stand_still"], "enabled": True}
    ch = pol["decentral"].get("chirp") if isinstance(pol, dict) and pol.get("decentral") else None
    if ch:
        cfg["chirp"] = {**cfg["chirp"], "enabled": True, **ch}
    starts = load_test_set(spec["set"])["starts"]
    make_act = make_act_factory(spec["policy"], pol)
    env = CoPushEnv(cfg, split="eval")
    seed0 = cfg["env"]["heldout_seeds"][0]

    def run(job: dict, hook, phase: list) -> dict:
        j = next((k for k, s in enumerate(starts) if s.get("id") == job["start_id"]), job["i"])
        seed = seed0 + j
        phase[0] = "push"
        act = make_act(env, seed)
        env.frame_hook = hook
        try:
            obs, _ = env.reset(seed=seed, options={"box": starts[j]})
            while True:
                obs, _, te, tr, info = env.step(act(obs))
                if te or tr:
                    break
        finally:
            env.frame_hook = None
        es, raw = info["episode_stats"], job["raw"]
        got = {"reason": es["reason"], "steps": int(es["steps"])}
        for f, k in (("push_share_a", "push_share"), ("contact_share_a", "contact_share")):
            v = es[k]["duck_a"]
            got[f] = None if v != v else float(v)
        for f in ("push_share_a", "contact_share_a"):          # compare at the precision the file stored
            if isinstance(raw.get(f), float) and got[f] is not None:
                got[f] = round(got[f], 4) if round(raw[f], 4) == raw[f] else got[f]
        return {**replay_match(got, raw, ("reason", "steps", "push_share_a", "contact_share_a")), "seed": seed}
    return env, run


def _record(env, run, job: dict) -> dict:
    """One episode -> <base>.gif, <base>.frames/NNN.jpg and <base>.json. The overlay shows the time and the phase
    only: nothing that tells the metric's verdict."""
    from PIL import Image, ImageSequence
    from copush.sim import CONTROL_DT
    from copush.video import VideoRecorder
    base = job["base"]
    os.makedirs(os.path.dirname(base), exist_ok=True)
    mp4 = base + ".tmp.mp4"
    rec = VideoRecorder(env.sim.m, mp4, fps=FPS, width=SIZE[0], height=SIZE[1])
    every = max(1, round(1 / (FPS * CONTROL_DT)))
    count, phase = [0], [""]

    def hook(st, _):
        if count[0] % every == 0:
            rec.frame(env.sim.d, st, [f"t {count[0] * CONTROL_DT:5.1f} s   {phase[0]}"])
        count[0] += 1
    try:
        info = run(job, hook, phase)
    finally:
        rec.close()
    # the palette GIF recipe of scripts/rl/side_by_side_policies.py, one clip, every frame kept
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-filter_complex",
                    f"fps={FPS},split[x][y];[x]palettegen=max_colors=48:stats_mode=diff[pl];"
                    "[y][pl]paletteuse=dither=none:diff_mode=rectangle", "-loop", "0", base + ".gif"], check=True)
    os.remove(mp4)
    fdir = base + ".frames"
    os.makedirs(fdir, exist_ok=True)
    n = 0
    with Image.open(base + ".gif") as im:
        for n, fr in enumerate(ImageSequence.Iterator(im), 1):
            fr.convert("RGB").save(os.path.join(fdir, f"{n - 1:04d}.jpg"), quality=82)
    meta = {"frames": n, "fps": FPS, "version": RENDER_VERSION, **info}
    with open(base + ".json", "w") as f:
        json.dump(meta, f)
    return meta


def render_worker(conn, spec: dict) -> None:
    os.chdir(ROOT)
    try:
        import torch
        torch.set_num_threads(2)
        env, run = (_setup_rendezvous if spec["format"] == "rendezvous" else _setup_push)(spec)
        fatal = None
    except Exception as e:                                   # answer every job with why nothing can be rendered
        fatal = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    while True:
        job = conn.recv()
        if job is None:
            return
        if fatal:
            conn.send((job["idx"], None, fatal))
            continue
        try:
            conn.send((job["idx"], _record(env, run, job), None))
        except Exception as e:
            traceback.print_exc()
            conn.send((job["idx"], None, f"{type(e).__name__}: {e}"))


def cached(base: str):
    try:
        meta = json.load(open(base + ".json"))
    except (OSError, ValueError):
        return None
    ok = meta.get("version") == RENDER_VERSION and os.path.exists(base + ".gif") and \
        os.path.exists(os.path.join(base + ".frames", f"{meta['frames'] - 1:04d}.jpg"))
    return meta if ok else None


# ── the session the page talks to ────────────────────────────────────────────

class Review:
    def __init__(self, a):
        results = rl.repo_path(a.results) if a.results else rl.find_results(a.run, a.seed_policy)
        data = rl.load_episodes(results, a.seed_policy, coop_min=a.coop_min, max_steps=a.max_steps)
        self.coop_min = data["coop_min"]
        self.data, self.run = data, a.run
        doc = json.load(open(results))
        if data["format"] == "rendezvous":
            pfile, pspec = data["policy_file"], None
            if pfile == "scripted":
                pfile = None
        else:
            spec = a.policy or self._guess_policy(a.run, data["policy"])
            if not spec:
                raise SystemExit("a push-only results file does not name its policy file: pass it as compare_policies.py "
                                 "took it, for example --policy runs/d2-steering-night5/l2-s2/model.zip@partner@standstill")
            pfile, pspec = rl.parse_policy(spec)
        sha = rl.sha256_file(rl.repo_path(pfile)) if pfile else None
        if pfile and not sha:
            print(f"warning: policy file {pfile} not found; labels are keyed with policy 'unknown' and nothing can be rendered")
        by_i = {e["i"]: e for e in data["episodes"]}
        picked = rl.sample(data["episodes"], a.n, a.group, a.seed)
        g = rl.groups(data["episodes"])
        meta = {"run": a.run, "policy": data["policy"], "policy_file": pfile, "policy_sha256": sha,
                "results_file": os.path.relpath(results, ROOT), "reviewer": a.reviewer,
                "coop_source": data["coop_source"],
                "sampling": {"n": a.n, "group": a.group, "seed": a.seed, "coop_min": self.coop_min,
                             "group_sizes": {k: len(v) for k, v in g.items()}}}
        self.session, self.resumed = rl.Session.open(
            rl.repo_path(a.out_dir) if a.out_dir else os.path.join(rl.experiment_dir(a.run), "reviews"), meta, picked)
        self.items = []
        tag = (sha or "unknown")[:8]
        for idx, s in enumerate(self.session.doc["sample"]):
            e = by_i[s["i"]]
            base = os.path.join(ROOT, CACHE, a.run, rl.norm(data["policy"]) or "policy",
                                f"start{s['start_id']}_seed{s['episode_seed']}_{tag}")
            self.items.append({"idx": idx, "key": s["key"], "episode": e, "base": base, "state": "queued",
                               "error": None, "meta": None})
        self.spec = {"format": data["format"], "set": data["set"], "config": data["config"], "policy": data["policy"],
                     "policy_file": data["policy_file"], "policy_spec": pspec, "push": data.get("push_policy_file"),
                     "no_push": bool(doc.get("no_push")), "episode_steps": doc.get("episode_steps"),
                     "max_steps": a.max_steps}
        self.lock = threading.Condition()
        self.want = None                 # the episode the page is waiting for: rendered first

    @staticmethod
    def _guess_policy(run: str, policy: str):
        """runs/<run>/<policy>/model.zip exists and the run's config says how it runs: nothing to guess from, so only a
        sidecar a results folder may carry (policies.json: {name: spec}) is used."""
        for d in rl.run_dirs(run):
            p = os.path.join(d, "policies.json")
            if os.path.exists(p):
                spec = {rl.norm(k): v for k, v in json.load(open(p)).items()}.get(rl.norm(policy))
                if spec:
                    return spec
        return None

    # rendering, on a thread that feeds the worker process one episode at a time
    def render_loop(self) -> None:
        for it in self.items:
            it["meta"] = cached(it["base"])
            if it["meta"]:
                it["state"] = "ready"
        if all(it["state"] == "ready" for it in self.items):
            return
        ctx = mp.get_context("spawn")
        here, there = ctx.Pipe()
        proc = ctx.Process(target=render_worker, args=(there, self.spec), daemon=True)
        proc.start()
        while True:
            with self.lock:
                todo = [it for it in self.items if it["state"] == "queued"]
                if not todo:
                    break
                it = next((t for t in todo if t["idx"] == self.want), todo[0])
                it["state"] = "rendering"
            e = it["episode"]
            try:
                here.send({"idx": it["idx"], "i": e["i"], "start_id": e["start_id"], "raw": e["raw"], "base": it["base"]})
                _, meta, err = here.recv()
            except (EOFError, OSError) as x:
                meta, err = None, f"the render process stopped ({x})"
            with self.lock:
                it["meta"], it["error"], it["state"] = meta, err, "ready" if meta else "error"
            if err and "render process stopped" in err:
                with self.lock:
                    for t in self.items:
                        if t["state"] == "queued":
                            t["state"], t["error"] = "error", err
                return
        try:
            here.send(None)
        except OSError:
            pass

    # what the page may see
    def reveal(self, it: dict) -> dict:
        e = it["episode"]
        return {"start_id": e["start_id"], "episode_seed": e["episode_seed"], "group": rl.group_of(e),
                "suspicious_because": rl.suspicious_reasons(e), **{f: e.get(f) for f in rl.METRIC_FIELDS}}

    def public(self, it: dict, full: bool = True) -> dict:
        lab = self.session.doc["labels"].get(it["key"])
        out = {"idx": it["idx"], "labeled": lab is not None,
               "agree": None if lab is None else [lab["agree_task"], lab["agree_coop"]]}
        if not full:
            return out
        m = it["meta"] or {}
        out.update(state=it["state"], error=it["error"], frames=m.get("frames"), fps=m.get("fps"),
                   replay_differs=(m.get("reproduced") is False))
        if lab is not None:                       # the metric is only sent once the episode has a label
            out.update(label=lab, reveal=self.reveal(it))
        return out

    def info(self) -> dict:
        d = self.session.doc
        return {"run": d["run"], "policy": d["policy"], "reviewer": d["reviewer"], "resumed": self.resumed,
                "file": os.path.relpath(self.session.path, ROOT), "format": self.data["format"],
                "verdicts": rl.VERDICTS, "reasons": rl.REASONS, "items": [self.public(it, False) for it in self.items]}

    def save_label(self, body: dict) -> dict:
        it = self.items[int(body["idx"])]
        with self.lock:
            self.session.label(it["key"], it["episode"], body["verdict"], body.get("reasons") or [], body.get("note") or "")
        return self.public(it)


class Handler(BaseHTTPRequestHandler):
    review: Review = None

    def log_message(self, *a):
        pass

    def _send(self, code: int, body: bytes, ctype: str, cache: bool = False) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _item(self, s: str):
        k = int(s)
        if not 0 <= k < len(self.review.items):
            raise IndexError(k)
        return self.review.items[k]

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        parts = [p for p in u.path.split("/") if p]
        r = self.review
        try:
            if not parts:
                return self._send(200, open(os.path.join(HERE, "review.html"), "rb").read(), "text/html; charset=utf-8")
            if u.path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if u.path == "/api/session":
                return self._json(r.info())
            if u.path == "/api/episode":
                it = self._item(q["idx"][0])
                with r.lock:
                    r.want = it["idx"]
                return self._json(r.public(it))
            if parts[0] == "frame" and len(parts) == 3:
                it = self._item(parts[1])
                p = os.path.join(it["base"] + ".frames", f"{int(parts[2].split('.')[0]):04d}.jpg")
                return self._send(200, open(p, "rb").read(), "image/jpeg", cache=True)
            if parts[0] == "gif" and len(parts) == 2:
                return self._send(200, open(self._item(parts[1])["base"] + ".gif", "rb").read(), "image/gif")
        except (KeyError, ValueError, IndexError, OSError) as e:
            return self._json({"error": f"{type(e).__name__}: {e}"}, 404)
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/label":
            return self._json({"error": "not found"}, 404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            self._json(self.review.save_label(body))
        except (KeyError, ValueError, IndexError, StopIteration) as e:
            self._json({"error": f"{type(e).__name__}: {e}"}, 400)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--seed-policy", default="", help="s1, s2, or the policy's name in comparison.json")
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--group", choices=rl.GROUPS, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--results", default=None)
    ap.add_argument("--policy", default=None, help="push-only runs: model.zip@partner@standstill, as compare_policies.py")
    ap.add_argument("--coop-min", type=float, default=None,
                    help="cooperative success: each duck's share is at least this (default: metrics.cooperative_share "
                         "of configs/copush.yaml, 0.25)")
    ap.add_argument("--out-dir", default=None,
                    help="where the label file goes (default experiments/<run>/reviews); use a folder under runs/ for a test")
    ap.add_argument("--render-only", action="store_true",
                    help="render the sampled clips, print whether each replay matched the recorded episode, and exit "
                         "(no server)")
    ap.add_argument("--max-steps", type=int, default=None, help="the push time limit in steps, when it is not 100")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    if not a.reviewer.replace("-", "").isalnum():
        ap.error("--reviewer: letters, digits and - only (it is part of the file name)")
    os.chdir(ROOT)
    r = Review(a)
    Handler.review = r
    sizes = r.session.doc["sampling"]["group_sizes"]
    done = len(r.session.doc["labels"])
    print(f"{a.run} / {r.data['policy']}: {len(r.data['episodes'])} episodes ("
          + ", ".join(f"{k} {v}" for k, v in sizes.items()) + f"); reviewing {len(r.items)}")
    print(("resuming " if r.resumed else "new session ") + os.path.relpath(r.session.path, ROOT)
          + (f" ({done} of {len(r.items)} labeled)" if r.resumed else ""))
    print("cooperative success read from: " + ", ".join(f"{rl.COOP_SOURCE_TEXT[k]} for {v} episodes"
                                                         for k, v in r.data["coop_source"].items())
          + f" (threshold {r.coop_min})")
    if a.render_only:
        r.render_loop()
        bad = 0
        for it in r.items:
            e, m = it["episode"], it["meta"] or {}
            ok = m.get("reproduced")
            bad += ok is not True
            print(f"  clip {it['idx']}: start {e['start_id']} seed {e['episode_seed']} group {rl.group_of(e)}: "
                  + (f"ERROR {it['error']}" if it["error"] else
                     ("replay MATCHES the recorded episode" if ok else f"replay DIFFERS: {m.get('mismatch')}")
                     + f" ({len(m.get('checked', []))} fields checked: {', '.join(m.get('checked', []))}; {m.get('frames')} frames)"))
        print(f"{len(r.items) - bad} of {len(r.items)} replays match")
        return 0 if not bad else 1
    threading.Thread(target=r.render_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"open {url}   (Ctrl-C to stop; labels are saved after every one)")
    if not a.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\nstopped; {len(r.session.doc['labels'])} of {len(r.items)} labeled in {os.path.relpath(r.session.path, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
