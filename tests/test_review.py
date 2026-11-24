"""The episode review tool (scripts/review): sampling, saving and resuming, and the summary math. No simulator."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "review"))

import reviewlib as rl  # noqa: E402


def rv_episode(i, success=True, share=0.5, steps=40, arrived=True, pos=1.0, yaw=2.0, **extra):
    """A record as scripts/rl/rendezvous_eval.py writes it."""
    return {"i": i, "id": i, "kind": "uniform", "arrived": arrived, "rv_steps": 20, "fell_rv": False,
            "pos_err_cm": {"duck_a": pos, "duck_b": 0.5}, "yaw_err_deg": {"duck_a": yaw, "duck_b": 1.0},
            "hit_box": {"duck_a": 1, "duck_b": 0}, "hit_ducks": 2, "push_reason": "success" if success else "timeout",
            "push_success": success, "push_steps": steps, "push_share_a": share, **extra}


def write_run(tmp_path, eps, name="results.json"):
    d = tmp_path / "runs" / "d2-rendezvous-r9-test" / "eval_s1"
    d.mkdir(parents=True)
    (d / name).write_text(json.dumps({"rendezvous": "runs/d2-rendezvous-r9-test/s1/best.zip", "push": "runs/push/model.zip",
                                      "set": "experiments/test_sets/rendezvous_large.json", "episodes": eps}))
    return str(d / name)


@pytest.fixture
def episodes(tmp_path):
    eps = ([rv_episode(i) for i in range(0, 20)]                                  # clean successes
           + [rv_episode(i, success=False, share=None, steps=100) for i in range(20, 30)]   # failures
           + [rv_episode(i, share=0.0) for i in range(30, 40)]                    # one duck pushes alone
           + [rv_episode(40, steps=95), rv_episode(41, pos=2.9), rv_episode(42, yaw=-14.0),
              rv_episode(43, arrived=False)])                                     # late, edge docking (x2), no docking
    return rl.load_episodes(write_run(tmp_path, eps), "s1")["episodes"]


# ── reading results ──────────────────────────────────────────────────────────

def test_find_results_and_normalized_fields(tmp_path, episodes):
    assert rl.find_results("r9-test", "s1", root=str(tmp_path)).endswith("eval_s1/results.json")
    with pytest.raises(SystemExit):
        rl.find_results("r9-test", "s7", root=str(tmp_path))
    e = episodes[0]
    assert (e["start_id"], e["episode_seed"], e["task_success"], e["coop_success"]) == (0, 10000, True, True)
    assert (e["falls"], e["collisions"], e["start_type"], e["steps"]) == (0, 3, "uniform", 40)
    assert episodes[30]["coop_success"] is False and episodes[25]["coop_success"] is False


def test_push_only_format_and_missing_fields(tmp_path):
    p = tmp_path / "comparison.json"
    p.write_text(json.dumps({"test_set": "s.json", "config": "c.yaml", "episodes": {"l2_s2": [
        {"id": 0, "side": "> +15", "reason": "success", "fell": False, "push_share_a": 1.0, "steps": 35},
        {"id": 1, "reason": "timeout"},
        {"id": 2}]}}))
    d = rl.load_episodes(str(p), "L2-s2")                       # the policy name matches without case or punctuation
    assert d["format"] == "push" and d["policy"] == "l2_s2"
    a, b, c = d["episodes"]
    assert (a["task_success"], a["coop_success"], a["start_type"]) == (True, False, "> +15")
    assert (b["task_success"], b["coop_success"], b["push_share_a"], b["falls"]) == (False, False, None, 0)
    assert (c["task_success"], c["coop_success"], c["falls"], c["collisions"], c["dock"]) == (None, None, None, None, None)
    assert [rl.group_of(e) for e in d["episodes"]] == ["suspicious", "failure", "failure"]
    assert len(rl.sample(d["episodes"], 30)) == 3               # nothing crashes on the missing fields


def test_parse_policy():
    assert rl.parse_policy("runs/a/model.zip") == ("runs/a/model.zip", "runs/a/model.zip")
    path, spec = rl.parse_policy("runs/a/model.zip@partner@standstill")
    assert path == "runs/a/model.zip" and spec == {"path": path, "decentral": {"include_partner": True}, "standstill": True}
    assert rl.parse_policy("m.zip@partner@chirp:2:30")[1]["decentral"]["chirp"]["interval_s"] == 2.0


# ── groups and sampling ──────────────────────────────────────────────────────

def test_groups_are_correct(episodes):
    g = rl.groups(episodes)
    assert [e["i"] for e in g["success"]] == list(range(0, 20))
    assert [e["i"] for e in g["failure"]] == list(range(20, 30))
    assert [e["i"] for e in g["suspicious"]] == list(range(30, 44))
    why = {e["i"]: rl.suspicious_reasons(e) for e in episodes}
    assert why[30] == ["task success but not cooperative"]
    assert why[40] == ["success in the last 10% of the time limit"]
    assert why[41] == why[42] == ["docking just inside tolerance"]
    assert why[43] == ["push success without docking"]
    assert why[0] == [] and why[20] == []
    assert rl.suspicious_reasons({**episodes[0], "steps": 89}) == [] and rl.suspicious_reasons({**episodes[0], "steps": 90})


def test_sample_is_even_and_repeatable(episodes):
    a = rl.sample(episodes, 30, seed=7)
    assert [e["i"] for e in a] == [e["i"] for e in rl.sample(episodes, 30, seed=7)]
    assert [e["i"] for e in a] != [e["i"] for e in rl.sample(episodes, 30, seed=8)]
    assert {g: sum(rl.group_of(e) == g for e in a) for g in rl.GROUPS} == {"success": 10, "failure": 10, "suspicious": 10}
    assert len({e["i"] for e in a}) == 30
    # the input order does not matter, only the episodes
    assert [e["i"] for e in rl.sample(list(reversed(episodes)), 30, seed=7)] == [e["i"] for e in a]
    six = rl.sample(episodes, 6, seed=0)
    assert sorted(rl.group_of(e) for e in six) == ["failure"] * 2 + ["success"] * 2 + ["suspicious"] * 2


def test_sample_small_groups_one_group_and_small_runs(episodes):
    a = rl.sample(episodes, 36, seed=1)                 # only 10 failures: the others take the rest
    n = {g: sum(rl.group_of(e) == g for e in a) for g in rl.GROUPS}
    assert n["failure"] == 10 and sum(n.values()) == 36 and abs(n["success"] - n["suspicious"]) <= 1
    only = rl.sample(episodes, 5, group="suspicious", seed=1)
    assert len(only) == 5 and all(rl.group_of(e) == "suspicious" for e in only)
    assert sorted(e["i"] for e in rl.sample(episodes, 500)) == list(range(44))       # few episodes: all of them
    assert sorted(e["i"] for e in rl.sample(episodes[:8], 30)) == list(range(8))
    assert rl.sample([], 30) == []


# ── saving and resuming ──────────────────────────────────────────────────────

def meta(reviewer="ashwin", seed=0):
    return {"run": "r9-test", "policy": "s1", "policy_file": "runs/x/best.zip", "policy_sha256": "ab" * 32,
            "results_file": "runs/x/results.json", "reviewer": reviewer,
            "sampling": {"n": 6, "group": None, "seed": seed, "coop_min": 0.25, "group_sizes": {}}}


def test_save_after_every_label_and_resume(tmp_path, episodes):
    rd = str(tmp_path / "experiments" / "r9-test" / "reviews")
    picked = rl.sample(episodes, 6, seed=0)
    s, resumed = rl.Session.open(rd, meta(), picked, date="2026-11-24")
    assert not resumed and os.path.basename(s.path) == "ashwin_2026-11-24.json"
    keys = [x["key"] for x in s.doc["sample"]]
    assert keys[0] == f"r9-test|{'ab' * 32}|{picked[0]['start_id']}|{picked[0]['episode_seed']}"
    lab = s.label(keys[0], picked[0], "fake_success", ["one_duck_idle", "other"], " B never touched the box ")
    on_disk = json.load(open(s.path))                    # written by the label itself, nothing else to call
    assert on_disk["labels"][keys[0]]["verdict"] == "fake_success" and lab["note"] == "B never touched the box"
    assert on_disk["labels"][keys[0]]["reasons"] == ["one_duck_idle", "other"]
    assert not os.path.exists(s.path + ".tmp")
    with pytest.raises(ValueError):
        s.label(keys[1], picked[1], "great")
    with pytest.raises(ValueError):
        s.label(keys[1], picked[1], "unclear", ["bored"])

    # the page closes; the same command another day resumes the unfinished file with its sample and labels
    s2, resumed = rl.Session.open(rd, meta(), rl.sample(episodes, 6, seed=0), date="2026-11-25")
    assert resumed and s2.path == s.path and [x["key"] for x in s2.doc["sample"]] == keys
    assert list(s2.doc["labels"]) == [keys[0]]
    for k, e in zip(keys[1:], picked[1:]):
        s2.label(k, e, "real_success")
    # finished: the same day reopens it, a later day starts a new file; other settings or reviewers never share a file
    assert rl.Session.open(rd, meta(), picked, date="2026-11-24")[0].path == s.path
    s3, resumed = rl.Session.open(rd, meta(), picked, date="2026-11-26")
    assert not resumed and os.path.basename(s3.path) == "ashwin_2026-11-26.json"
    s4, resumed = rl.Session.open(rd, meta(seed=5), picked, date="2026-11-24")
    assert not resumed and os.path.basename(s4.path) == "ashwin_2026-11-24-2.json"
    assert os.path.basename(rl.Session.open(rd, meta("winston"), picked, date="2026-11-24")[0].path) == "winston_2026-11-24.json"


def test_blind_verdict_is_kept_when_a_label_changes(tmp_path, episodes):
    picked = rl.sample(episodes, 6, seed=0)
    s, _ = rl.Session.open(str(tmp_path / "reviews"), meta(), picked, date="2026-11-24")
    k = s.doc["sample"][0]["key"]
    assert s.label(k, picked[0], "real_success")["changed_after_reveal"] is False
    lab = s.label(k, picked[0], "fake_success")
    assert (lab["verdict"], lab["blind_verdict"], lab["changed_after_reveal"]) == ("fake_success", "real_success", True)
    assert s.label(k, picked[0], "real_success")["changed_after_reveal"] is True      # it stays marked


# ── the summary ──────────────────────────────────────────────────────────────

def test_wilson_and_agreement():
    lo, hi = rl.wilson(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-3) and hi == pytest.approx(0.9433, abs=1e-3)
    assert rl.wilson(0, 10)[0] == 0.0 and rl.wilson(10, 10)[1] == 1.0
    assert all(x != x for x in rl.wilson(0, 0))
    assert rl.agreement("real_success", True) is True and rl.agreement("real_success", False) is False
    assert rl.agreement("fake_success", True) is False and rl.agreement("fake_success", False) is True
    assert rl.agreement("real_failure", False) is True and rl.agreement("real_failure", True) is False
    assert rl.agreement("unclear", True) is None and rl.agreement("real_success", None) is None


def label_all(tmp_path, episodes, reviewer, verdicts, date="2026-11-24"):
    """Label episodes by index: verdicts = {i: verdict or (verdict, reasons)}."""
    by_i = {e["i"]: e for e in episodes}
    picked = [by_i[i] for i in verdicts]
    s, _ = rl.Session.open(str(tmp_path / "experiments" / "d2-rendezvous" / "r9-test" / "reviews"), meta(reviewer), picked, date=date)
    for x, e in zip(s.doc["sample"], picked):
        v = verdicts[e["i"]]
        s.label(x["key"], e, *(v if isinstance(v, tuple) else (v,)))
    return s


def test_summary_math(tmp_path, episodes):
    # 0, 1: clean successes; 20: failure; 30, 31: task success, not cooperative; 40: late success
    label_all(tmp_path, episodes, "ashwin", {
        0: "real_success", 1: "unclear", 20: "real_failure",
        30: ("fake_success", ["one_duck_idle"]), 31: ("real_success", ["one_duck_idle", "hovering"]), 40: "fake_success"})
    rows = rl.load_reviews("r9-test", root=str(tmp_path))       # found under experiments/d2-rendezvous/r9-test/reviews
    s = rl.summarize(rows)
    assert (s["labels"], s["episodes"], s["reviewers"]) == (6, 6, ["ashwin"])
    c = s["combined"]
    assert c["verdicts"] == {"real_success": 2, "fake_success": 2, "real_failure": 1, "unclear": 1}
    # task: 0 agree, 20 agree, 30 disagree, 31 agree, 40 disagree; the unclear one is left out
    assert (c["task"]["agree"], c["task"]["n"]) == (3, 5) and c["task"]["rate"] == pytest.approx(0.6)
    assert c["task"]["ci"] == pytest.approx(list(rl.wilson(3, 5)))
    # cooperative (30 and 31 are not cooperative): 0 agree, 20 agree, 30 agree, 31 disagree, 40 disagree
    assert (c["coop"]["agree"], c["coop"]["n"]) == (3, 5)
    assert c["by_group"]["suspicious"]["reviewed"] == 3 and c["by_group"]["suspicious"]["task"]["agree"] == 1
    assert s["reasons"]["one_duck_idle"] == 2 and s["reasons"]["hovering"] == 1 and s["reasons"]["stuck"] == 0
    dis = {d["start_id"]: d["disagrees_with"] for d in s["disagreements"]}
    assert dis == {30: ["task"], 31: ["cooperative"], 40: ["task", "cooperative"]}
    out = rl.report("r9-test", s)
    assert "task success         60% (3/5; 95% interval" in out and "start 40" in out and "not ground truth" in out


def test_summary_combines_reviewers_and_shows_splits(tmp_path, episodes):
    label_all(tmp_path, episodes, "ashwin", {0: "real_success", 30: "fake_success", 20: "real_failure"})
    label_all(tmp_path, episodes, "winston", {0: "real_success", 30: "real_success", 31: "fake_success"})
    s = rl.summarize(rl.load_reviews("r9-test", root=str(tmp_path)))
    assert (s["labels"], s["episodes"], s["reviewers"]) == (6, 4, ["ashwin", "winston"])
    b = s["between_reviewers"]
    assert (b["episodes_with_two_or_more"], b["same"], b["split"]) == (2, 1, 1)
    assert b["splits"][0]["start_id"] == 30 and b["splits"][0]["verdicts"] == {"ashwin": "fake_success", "winston": "real_success"}
    # combined: each episode once, the split one (30) left out -> 0, 20, 31
    assert s["combined"]["reviewed"] == 3 and s["combined"]["task"]["n"] == 3
    assert s["per_reviewer"]["winston"]["task"] == {"agree": 2, "n": 3, "rate": pytest.approx(2 / 3), "ci": pytest.approx(list(rl.wilson(2, 3)))}
    out = rl.report("r9-test", s)
    assert "Between reviewers: 2 episodes labeled by two or more; same verdict on 1, different on 1" in out
    assert "ashwin fake success, winston real success" in out


def test_newest_label_wins_and_empty_run(tmp_path, episodes):
    label_all(tmp_path, episodes, "ashwin", {30: "real_success"}, date="2026-11-24")
    s = label_all(tmp_path, episodes, "ashwin", {30: "fake_success"}, date="2026-11-25")
    doc = json.load(open(s.path))
    for lab in doc["labels"].values():
        lab["saved_at"] = "2099-01-01T00:00:00"
    json.dump(doc, open(s.path, "w"))
    rows = rl.load_reviews("r9-test", root=str(tmp_path))
    assert len(rows) == 1 and rows[0]["verdict"] == "fake_success"
    empty = rl.summarize([])
    assert empty["labels"] == 0 and empty["combined"]["task"]["rate"] is None
    assert "No labels found" in rl.report("nope", empty)
