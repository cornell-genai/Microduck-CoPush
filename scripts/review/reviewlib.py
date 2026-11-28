"""Shared logic of the episode review tool (scripts/review/serve.py, scripts/review/summarize.py).

Standard library only, so the tests and the summary run without the simulator.

    find_results     a run name (+ policy name) -> the per-episode results file an evaluation wrote
    load_episodes    that file -> one normalized record per episode (missing fields become None)
    group_of         success / failure / suspicious, with the reasons an episode is suspicious
    sample           an even, seeded sample over the three groups
    Session          the label file: experiments/<run>/reviews/<reviewer>_<date>.json, saved after every label
    summarize        agreement of the labels with the metric (Wilson 95% intervals), reasons, disagreements

Two results formats are read:
    rendezvous   scripts/rl/rendezvous_eval.py results.json: {"rendezvous": policy, "set": ..., "episodes": [..]}
    push         scripts/rl/compare_policies.py comparison.json: {"test_set", "config", "episodes": {policy: [..]}}
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import math
import os
import random
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VERDICTS = ("real_success", "fake_success", "real_failure", "unclear")
REASONS = ("one_duck_idle", "box_lost", "duck_fell", "overshoot", "wrong_side", "collision", "hovering", "stuck", "other")
GROUPS = ("success", "failure", "suspicious")
COOP_MIN = 0.25            # cooperative success: each duck has at least this share of the push (as the box-mass sweep)
LATE_FRAC = 0.10           # "late": success within the last 10% of the time limit
DOCK_TOL = {"pos_cm": 3.0, "yaw_deg": 15.0}   # the handoff tolerance (scripts/rl/rendezvous_eval.py)
DOCK_EDGE = 0.90           # "docking just inside tolerance": an error at or above 90% of its tolerance
MAX_STEPS = 100            # env.max_steps, the push time limit, when the results file does not carry it
SEED0 = 10000              # env.heldout_seeds[0], the first evaluation seed, when the results file does not carry it
RESULT_NAMES = ("results.json", "comparison.json", "test_set.json")
Z = 1.96


def repo_path(p: str, root: str = ROOT) -> str:
    return p if os.path.isabs(p) else os.path.join(root, p)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def sha256_file(path: str):
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def wilson(k: int, n: int):
    """95% Wilson interval for k of n (the same formula as scripts/rl/ci_report.py)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


# ── finding and reading a run's per-episode results ──────────────────────────

def run_dirs(run: str, root: str = ROOT) -> list:
    """Folders that can belong to a run name: runs/<run>, runs/*-<run>, and experiments/**/<run>."""
    out = []
    for base in ("runs", "experiments"):
        b = os.path.join(root, base)
        direct = os.path.join(b, run)
        if os.path.isdir(direct):
            out.append(direct)
        if "/" in run:
            continue
        for depth in ("*", "*/*", "*/*/*"):
            for d in sorted(glob.glob(os.path.join(b, depth))):
                name = os.path.basename(d)
                if os.path.isdir(d) and d not in out and (name == run or name.endswith("-" + run)):
                    out.append(d)
    return out


def experiment_dir(run: str, root: str = ROOT) -> str:
    """Where a run's reviews go: the existing experiments/**/<run> folder, else experiments/<run>."""
    for d in run_dirs(run, root):
        if os.path.relpath(d, root).split(os.sep)[0] == "experiments":
            return d
    return os.path.join(root, "experiments", run)


def _policy_in(doc: dict, path: str, policy: str):
    """The name under which `policy` appears in a results file, or None."""
    eps = doc.get("episodes") if isinstance(doc, dict) else None
    if isinstance(eps, dict):
        for name in eps:
            if not policy or norm(name) == norm(policy):
                return name
        return None
    if isinstance(eps, list):
        if not policy:
            return ""
        where = [os.path.basename(os.path.dirname(path))] + str(doc.get("rendezvous") or doc.get("policy") or "").split("/")
        return policy if any(norm(w) in (norm(policy), norm("eval_" + policy)) for w in where) else None
    return None


def find_results(run: str, policy: str, root: str = ROOT) -> str:
    """The per-episode results file of `run` for `policy` (for example r6-dock-payout, s1)."""
    hits = []
    for d in run_dirs(run, root):
        for depth in ("", "*", "*/*", "*/*/*"):
            for name in RESULT_NAMES:
                for p in sorted(glob.glob(os.path.join(d, depth, name))):
                    try:
                        doc = json.load(open(p))
                    except (OSError, ValueError):
                        continue
                    if _policy_in(doc, p, policy) is not None and p not in hits:
                        hits.append(p)
    if not hits:
        raise SystemExit(f"no per-episode results found for run '{run}', policy '{policy}' under runs/ or experiments/; "
                         "pass the file with --results")
    # an eval of the whole test set beats smaller ones (checkpoint selection, reselects): prefer the shallowest path
    best = min(len(os.path.relpath(p, root).split(os.sep)) for p in hits)
    top = [p for p in hits if len(os.path.relpath(p, root).split(os.sep)) == best]
    if len(top) > 1:
        raise SystemExit("several results files match; pick one with --results:\n  "
                         + "\n  ".join(os.path.relpath(p, root) for p in top))
    return top[0]


def _num(x):
    return None if x is None or (isinstance(x, float) and x != x) else x


def _total(x):
    """A count that may be a number, a bool, or a per-duck dict."""
    if x is None:
        return None
    if isinstance(x, dict):
        return sum(int(v) for v in x.values() if v is not None)
    return int(x)


def _coop(share, coop_min: float):
    return None if share is None else bool(coop_min <= share <= 1 - coop_min)


def load_episodes(path: str, policy: str = "", coop_min: float = COOP_MIN, max_steps=None, seed0=None) -> dict:
    """-> {"format", "policy", "policy_file", "set", "config", "seed0", "max_steps", "episodes": [..]}.

    Every episode: i (position in the set), start_id, episode_seed, task_success, coop_success, push_share_a, steps,
    reason, falls, collisions, start_type, arrived, dock (worst position and heading error at handoff) and raw (the
    record as written). A field the results file lacks is None; nothing here assumes a field exists.
    """
    doc = json.load(open(path))
    name = _policy_in(doc, path, policy)
    if name is None:
        have = list(doc["episodes"]) if isinstance(doc.get("episodes"), dict) else "(one policy, not named like that)"
        raise SystemExit(f"{path} has no episodes for policy '{policy}'; it has {have}")
    eps = doc["episodes"]
    rendezvous = isinstance(eps, list)
    rows = eps if rendezvous else eps[name]
    # the episode seed is seed0 + position in the set; both evaluations start at the first held-out seed (10000)
    seed0 = doc.get("episode_seed0") or seed0 or SEED0
    limit = max_steps or doc.get("max_steps") or MAX_STEPS
    out = []
    for k, r in enumerate(rows):
        i = r.get("i", k)
        share = _num(r.get("push_share_a"))
        if "push_success" in r:
            task = bool(r["push_success"])
        elif "reason" in r or "push_reason" in r:
            task = (r.get("reason") or r.get("push_reason")) == "success"
        elif "success" in r:
            task = bool(r["success"])
        elif "arrived" in r:                       # a rendezvous-only evaluation: arriving is the task
            task = bool(r["arrived"])
        else:
            task = None
        coop = next((bool(r[f]) for f in ("coop_success", "cooperative_success", "coop") if r.get(f) is not None), None)
        if coop is None and task is not None:
            coop = False if not task else _coop(share, coop_min)
        fell = [r[f] for f in ("fell", "fell_rv") if f in r]
        reason = r.get("reason") or r.get("push_reason")
        falls = None if not fell and reason is None else int(any(_total(f) for f in fell) or reason == "fall")
        hits = [_total(r[f]) for f in ("hit_box", "hit_ducks", "collisions") if r.get(f) is not None]
        pe, ye = r.get("pos_err_cm"), r.get("yaw_err_deg")
        out.append({
            "i": i, "start_id": r.get("id", i), "episode_seed": seed0 + i,
            "task_success": task, "coop_success": coop, "push_share_a": share,
            "steps": r.get("push_steps", r.get("steps")), "max_steps": limit, "reason": reason,
            "falls": falls, "collisions": sum(hits) if hits else None,
            "start_type": r.get("kind", r.get("side")), "arrived": r.get("arrived"),
            "dock": None if not isinstance(pe, dict) or not isinstance(ye, dict) else
                    {"pos_cm": max(pe.values()), "yaw_deg": max(abs(v) for v in ye.values())},
            "overshoot": r.get("overshoot"), "box_lost": r.get("box_lost"), "raw": r})
    return {"format": "rendezvous" if rendezvous else "push", "policy": name or policy,
            "policy_file": (doc.get("rendezvous") if rendezvous else None), "push_policy_file": doc.get("push"),
            "set": doc.get("set") or doc.get("test_set"), "config": doc.get("config"), "seed0": seed0,
            "max_steps": limit, "episodes": out}


def parse_policy(spec: str):
    """A push policy as scripts/rl/compare_policies.py takes it: path[@own|@partner][@chirp:<s>:<deg>[:<noise>]]
    [@trueheading|@heldheading][@standstill][@sample:K] -> (path, what make_act_factory takes)."""
    path, dc = spec, None
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
    if chirp and dc:
        dc["chirp"] = {"interval_s": float(chirp[1]), "direction_noise_deg": float(chirp[2]), "heading": heading,
                       "distance": chirp[3] is not None, **({"distance_noise": float(chirp[3])} if chirp[3] else {})}
    if not (dc or stand or smp):
        return path, path
    return path, {"path": path, **({"decentral": dc} if dc else {}), **({"standstill": True} if stand else {}),
                  **({"sample": int(smp[1])} if smp else {})}


# ── groups and sampling ──────────────────────────────────────────────────────

def suspicious_reasons(e: dict) -> list:
    """Why a metric success deserves a second look (empty for failures and for clean successes)."""
    if not e.get("task_success"):
        return []
    why = []
    if e.get("coop_success") is False:
        why.append("task success but not cooperative")
    if e.get("steps") is not None and e.get("max_steps") and e["steps"] >= (1 - LATE_FRAC) * e["max_steps"]:
        why.append("success in the last 10% of the time limit")
    d = e.get("dock")
    if d and e.get("arrived") and (d["pos_cm"] >= DOCK_EDGE * DOCK_TOL["pos_cm"] or d["yaw_deg"] >= DOCK_EDGE * DOCK_TOL["yaw_deg"]):
        why.append("docking just inside tolerance")
    if e.get("arrived") is False and e.get("raw", {}).get("push_success"):
        why.append("push success without docking")
    return why


def group_of(e: dict) -> str:
    if not e.get("task_success"):
        return "failure"
    return "suspicious" if suspicious_reasons(e) else "success"


def groups(episodes: list) -> dict:
    g = {k: [] for k in GROUPS}
    for e in episodes:
        g[group_of(e)].append(e)
    return g


def sample(episodes: list, n: int = 30, group=None, seed: int = 0) -> list:
    """Episodes to review, in the order they are shown.

    Evenly over the three groups (n // 3 each, the remainder to the first groups that still have episodes; a group
    that runs out gives its share to the others), random within a group, then shuffled so the order does not tell
    the group. The same (episodes, n, group, seed) always gives the same list. With `group`, only that group. When
    the run has no more than n episodes (in the chosen groups), all of them.
    """
    g = groups(episodes)
    names = [group] if group else list(GROUPS)
    rng = random.Random(seed)
    pools = {}
    for k in names:
        pools[k] = sorted(g[k], key=lambda e: e["i"])
        rng.shuffle(pools[k])
    total = sum(len(p) for p in pools.values())
    want = {k: 0 for k in names}
    left = min(n, total)
    while left:
        open_ = [k for k in names if want[k] < len(pools[k])]
        share = max(1, left // len(open_))
        for k in open_:
            if not left:
                break
            take = min(share, len(pools[k]) - want[k], left)
            want[k] += take
            left -= take
    picked = [e for k in names for e in pools[k][:want[k]]]
    rng.shuffle(picked)
    return picked


# ── the label file ───────────────────────────────────────────────────────────

def label_key(run: str, policy_sha256, start_id, episode_seed) -> str:
    """Labels are keyed by run, policy file hash, start id and episode seed, so they survive reruns."""
    return f"{run}|{policy_sha256 or 'unknown'}|{start_id}|{episode_seed}"


def human_success(verdict: str):
    """What a verdict says about the episode: True (a real success), False (not one), None (unclear)."""
    return {"real_success": True, "fake_success": False, "real_failure": False}.get(verdict)


def agreement(verdict: str, metric_value):
    """True / False when the label and the metric can be compared, else None."""
    h = human_success(verdict)
    return None if h is None or metric_value is None else bool(h == bool(metric_value))


METRIC_FIELDS = ("task_success", "coop_success", "push_share_a", "start_type", "falls", "collisions", "steps",
                 "max_steps", "reason", "arrived", "dock", "overshoot", "box_lost")


class Session:
    """One reviewer's session on one run and policy: the sample and the labels, saved after every label."""

    def __init__(self, path: str, doc: dict):
        self.path, self.doc = path, doc

    @classmethod
    def open(cls, reviews_dir: str, meta: dict, picked: list, date=None):
        """Resume the reviewer's unfinished session with the same run, policy, results and sampling, else the finished
        one from today, else start a new file <reviewer>_<date>.json (-2, -3 ... when that name is taken)."""
        date = date or dt.date.today().isoformat()
        same = ("run", "policy", "policy_sha256", "reviewer", "sampling")
        match = []
        for p in sorted(glob.glob(os.path.join(reviews_dir, f"{meta['reviewer']}_*.json"))):
            try:
                d = json.load(open(p))
            except (OSError, ValueError):
                continue
            if all(d.get(k) == meta[k] for k in same):
                match.append((p, d))
        unfinished = [m for m in match if len(m[1].get("labels", {})) < len(m[1].get("sample", []))]
        today = [m for m in match if m[1].get("date") == date]
        if unfinished or today:
            p, d = (unfinished or today)[-1]
            return cls(p, d), True
        k, path = 1, os.path.join(reviews_dir, f"{meta['reviewer']}_{date}.json")
        while os.path.exists(path):
            k += 1
            path = os.path.join(reviews_dir, f"{meta['reviewer']}_{date}-{k}.json")
        doc = {"version": 1, **meta, "date": date,
               "sample": [{"key": label_key(meta["run"], meta["policy_sha256"], e["start_id"], e["episode_seed"]),
                           "i": e["i"], "start_id": e["start_id"], "episode_seed": e["episode_seed"],
                           "group": group_of(e)} for e in picked],
               "labels": {}}
        return cls(path, doc), False

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.doc, f, indent=1)
        os.replace(tmp, self.path)

    def label(self, key: str, episode: dict, verdict: str, reasons=(), note: str = "") -> dict:
        """Record a label and write the file. The first verdict for an episode is the blind one: it is kept as
        blind_verdict, and a later change is marked changed_after_reveal."""
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}")
        bad = [r for r in reasons if r not in REASONS]
        if bad:
            raise ValueError(f"unknown reasons {bad}")
        item = next(s for s in self.doc["sample"] if s["key"] == key)
        old = self.doc["labels"].get(key)
        metric = {f: episode.get(f) for f in METRIC_FIELDS}
        rec = {"start_id": item["start_id"], "episode_seed": item["episode_seed"], "group": item["group"],
               "verdict": verdict, "reasons": [r for r in REASONS if r in reasons], "note": note.strip(),
               "blind_verdict": old["blind_verdict"] if old else verdict,
               "changed_after_reveal": bool(old and (old["changed_after_reveal"] or old["blind_verdict"] != verdict)),
               "saved_at": dt.datetime.now().isoformat(timespec="seconds"), "metric": metric,
               "suspicious_because": suspicious_reasons(episode),
               "agree_task": agreement(verdict, metric["task_success"]),
               "agree_coop": agreement(verdict, metric["coop_success"])}
        self.doc["labels"][key] = rec
        self.save()
        return rec


# ── the summary ──────────────────────────────────────────────────────────────

def load_reviews(run: str, root: str = ROOT) -> list:
    """Every label of a run, one row per (reviewer, episode); a reviewer's newest label of an episode wins."""
    files = []
    for d in run_dirs(run, root) + [os.path.join(root, "experiments", run)]:
        files += glob.glob(os.path.join(d, "reviews", "*.json"))
    latest = {}
    for p in sorted(set(files)):
        try:
            doc = json.load(open(p))
        except (OSError, ValueError):
            continue
        for key, lab in doc.get("labels", {}).items():
            row = {**lab, "key": key, "reviewer": doc.get("reviewer"), "policy": doc.get("policy"),
                   "file": os.path.relpath(p, root)}
            old = latest.get((row["reviewer"], key))
            if old is None or row.get("saved_at", "") >= old.get("saved_at", ""):
                latest[(row["reviewer"], key)] = row
    return sorted(latest.values(), key=lambda r: (str(r["policy"]), str(r["start_id"]).zfill(8), str(r["reviewer"])))


def _rate(rows: list, which: str) -> dict:
    """Agreement of the blind verdicts with one metric; unclear labels and unknown metric values are left out."""
    vals = [agreement(r["blind_verdict"], r["metric"].get(which)) for r in rows]
    vals = [v for v in vals if v is not None]
    k, n = sum(vals), len(vals)
    lo, hi = wilson(k, n)
    return {"agree": k, "n": n, "rate": (k / n) if n else None, "ci": [lo, hi]}


def summarize(rows: list) -> dict:
    """Counts and agreement rates over label rows (load_reviews). Rates use the blind verdict."""
    by_rev = {}
    for r in rows:
        by_rev.setdefault(r["reviewer"], []).append(r)
    by_ep = {}
    for r in rows:
        by_ep.setdefault(r["key"], []).append(r)
    # one row per episode for the combined rates: episodes whose reviewers gave different verdicts are left out
    split = {k: v for k, v in by_ep.items() if len({r["blind_verdict"] for r in v}) > 1}
    shared = {k: v for k, v in by_ep.items() if len(v) > 1}
    unique = [v[0] for k, v in by_ep.items() if k not in split]

    def block(rs):
        return {"reviewed": len(rs), "verdicts": {v: sum(r["blind_verdict"] == v for r in rs) for v in VERDICTS},
                "task": _rate(rs, "task_success"), "coop": _rate(rs, "coop_success"),
                "by_group": {g: {"reviewed": sum(r["group"] == g for r in rs),
                                 "task": _rate([r for r in rs if r["group"] == g], "task_success"),
                                 "coop": _rate([r for r in rs if r["group"] == g], "coop_success")} for g in GROUPS}}

    dis = []
    for r in rows:
        at = agreement(r["blind_verdict"], r["metric"].get("task_success"))
        ac = agreement(r["blind_verdict"], r["metric"].get("coop_success"))
        if at is False or ac is False:
            dis.append({"start_id": r["start_id"], "episode_seed": r["episode_seed"], "policy": r["policy"],
                        "reviewer": r["reviewer"], "verdict": r["blind_verdict"], "reasons": r["reasons"],
                        "note": r["note"], "task_success": r["metric"].get("task_success"),
                        "coop_success": r["metric"].get("coop_success"), "push_share_a": r["metric"].get("push_share_a"),
                        "disagrees_with": [n for n, a in (("task", at), ("cooperative", ac)) if a is False]})
    return {"labels": len(rows), "episodes": len(by_ep), "reviewers": sorted(by_rev, key=str),
            "combined": block(unique), "per_reviewer": {k: block(v) for k, v in sorted(by_rev.items(), key=lambda kv: str(kv[0]))},
            "reasons": {x: sum(x in r["reasons"] for r in rows) for x in REASONS},
            "changed_after_reveal": sum(bool(r.get("changed_after_reveal")) for r in rows),
            "disagreements": dis,
            "between_reviewers": {"episodes_with_two_or_more": len(shared), "split": len(split),
                                  "same": len(shared) - len(split),
                                  "splits": [{"start_id": v[0]["start_id"], "episode_seed": v[0]["episode_seed"],
                                              "policy": v[0]["policy"],
                                              "verdicts": {str(r["reviewer"]): r["blind_verdict"] for r in v}}
                                             for v in split.values()]}}


def _pct(r: dict) -> str:
    if not r["n"]:
        return "n/a (0 comparable)"
    return f"{100 * r['rate']:.0f}% ({r['agree']}/{r['n']}; 95% interval {100 * r['ci'][0]:.0f}% to {100 * r['ci'][1]:.0f}%)"


def report(run: str, s: dict) -> str:
    if not s["labels"]:
        return f"No labels found for run '{run}' (looked for experiments/**/{run}/reviews/*.json).\n"
    c = s["combined"]
    L = [f"Episode review summary: {run}", "",
         f"Reviewed: {s['episodes']} episodes, {s['labels']} labels, reviewers: {', '.join(map(str, s['reviewers']))}",
         "Verdicts (blind): " + ", ".join(f"{v.replace('_', ' ')} {c['verdicts'][v]}" for v in VERDICTS)
         + (f" (episodes where reviewers split are left out: {s['between_reviewers']['split']})" if s["between_reviewers"]["split"] else ""),
         "", "Agreement with the metric (a label agrees when 'real success' meets a metric success, or 'fake success' /",
         "'real failure' meets a metric failure; 'unclear' is left out):",
         f"  task success         {_pct(c['task'])}",
         f"  cooperative success  {_pct(c['coop'])}", "", "By sampling group:"]
    for g in GROUPS:
        b = c["by_group"][g]
        if b["reviewed"]:
            L.append(f"  {g:<11} reviewed {b['reviewed']:>3}   task {_pct(b['task'])}   cooperative {_pct(b['coop'])}")
    L += ["", "The sample takes the three groups evenly, so these rates describe the reviewed episodes, not the whole run.",
          "Labels are for catching metric bugs; they are not ground truth."]
    if len(s["reviewers"]) > 1:
        L += ["", "Per reviewer:"]
        for name, b in s["per_reviewer"].items():
            L.append(f"  {str(name):<12} reviewed {b['reviewed']:>3}   task {_pct(b['task'])}   cooperative {_pct(b['coop'])}")
    L += ["", "Reasons ticked: " + (", ".join(f"{k.replace('_', ' ')} {v}" for k, v in s["reasons"].items() if v) or "none")]
    if s["changed_after_reveal"]:
        L.append(f"Labels changed after the reveal: {s['changed_after_reveal']} (the rates use the blind label)")
    L += ["", f"Disagreements with the metric: {len(s['disagreements'])}"]
    for d in s["disagreements"]:
        sh = "n/a" if d["push_share_a"] is None else f"{100 * d['push_share_a']:.0f}%"
        L.append(f"  start {d['start_id']} (seed {d['episode_seed']}, {d['policy']}, {d['reviewer']}): {d['verdict'].replace('_', ' ')}; "
                 f"metric task {_yn(d['task_success'])}, cooperative {_yn(d['coop_success'])}, push share A {sh}; "
                 f"disagrees with {' and '.join(d['disagrees_with'])}"
                 + (f"; reasons: {', '.join(x.replace('_', ' ') for x in d['reasons'])}" if d["reasons"] else "")
                 + (f"; note: {d['note']}" if d["note"] else ""))
    b = s["between_reviewers"]
    if len(s["reviewers"]) > 1:
        L += ["", f"Between reviewers: {b['episodes_with_two_or_more']} episodes labeled by two or more; "
                  f"same verdict on {b['same']}, different on {b['split']}"]
        for x in b["splits"]:
            L.append(f"  start {x['start_id']} (seed {x['episode_seed']}, {x['policy']}): "
                     + ", ".join(f"{k} {v.replace('_', ' ')}" for k, v in x["verdicts"].items()))
    return "\n".join(L) + "\n"


def _yn(x) -> str:
    return "n/a" if x is None else ("yes" if x else "no")
