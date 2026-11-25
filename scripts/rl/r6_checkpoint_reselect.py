#!/usr/bin/env python3
"""r6-dock-payout: re-pick each seed's checkpoint on the check set instead of the test set, and redo the comparisons.

    scripts/rl.sh scripts/rl/r6_checkpoint_reselect.py

r6's best.zip was picked by most dockings on the test set (experiments/test_sets/rendezvous_large.json), the starts its
results are reported on. train_rendezvous.py kept only the newest checkpoint, so the candidates per seed are what is
still on disk: the final checkpoint (model.zip, step 2002944) and best.zip (the test-set pick). Each candidate is
evaluated on the check set (experiments/test_sets/rendezvous_check.json; rendezvous alone, 50 steps, the training
ending, as the training evals). Only the final checkpoint was saved independently of the test set, so it is the
official pick; best.zip's check-set score is shown for information only. Reads the evals under
runs/d2-rendezvous-r6-dock-payout/reselect/ (made by reselect/run.sh) and the run's own evals, and writes
experiments/d2-rendezvous/r6-dock-payout/results/reselect/{reselect.md, reselect.json}.

The evals it reads (R = runs/d2-rendezvous-r6-dock-payout, CHECK = experiments/test_sets/rendezvous_check.json):

    rendezvous_eval.py eval --rendezvous R/sN/model.zip --set CHECK --no-push --episode-steps 50 --out R/reselect/check_sN_final
    rendezvous_eval.py eval --rendezvous R/s2/best.zip  --set CHECK --no-push --episode-steps 50 --out R/reselect/check_s2_best2000000
    rendezvous_eval.py eval --rendezvous R/sN/model.zip --out R/reselect/test_sN_final        # test set, full pipeline
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts", "rl")]

from ci_report import mean_ci, wilson  # noqa: E402

R = os.path.join(ROOT, "runs/d2-rendezvous-r6-dock-payout")
R5 = os.path.join(ROOT, "runs/d2-rendezvous-r5-bc-warmstart")
OUT = os.path.join(ROOT, "experiments/d2-rendezvous/r6-dock-payout/results/reselect")
SEEDS = ("s1", "s2")
FINAL = 2002944


def load(path):
    return json.load(open(path))


def eps(path):
    return load(path)["episodes"]


def rate(k, n):
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% ({100 * lo:.1f}% to {100 * hi:.1f}%)"


def paired(a, b):
    d = [x - y for x, y in zip(a, b)]
    m, h = mean_ci(d)
    return m, m - h, m + h


def err(e, key):
    return sum(e[key].values()) / 2


def row(label, e):
    n = len(e)
    a = sum(x["arrived"] for x in e)
    s = sum(x["push_success"] for x in e)
    pe = sum(err(x, "pos_err_cm") for x in e) / n
    ye = sum(err(x, "yaw_err_deg") for x in e) / n
    pm, plo, phi = paired([err(x, "pos_err_cm") for x in e], [0.0] * n)
    ym, ylo, yhi = paired([err(x, "yaw_err_deg") for x in e], [0.0] * n)
    return (f"| {label} | {rate(a, n)} | {rate(s, n)} | {pe:.1f} cm ({plo:.1f} to {phi:.1f}) | "
            f"{ye:.1f} deg ({ylo:.1f} to {yhi:.1f}) |")


def main() -> int:
    sel = os.path.join(R, "reselect")
    best = {s: load(os.path.join(R, s, "best.json")) for s in SEEDS}
    check = {s: {"final": load(os.path.join(sel, f"check_{s}_final", "results.json"))["summary"]["all"]} for s in SEEDS}
    for s in SEEDS:
        p = os.path.join(sel, f"check_{s}_best{best[s]['step']}", "results.json")
        if best[s]["step"] != FINAL and os.path.exists(p):
            check[s]["best"] = load(p)["summary"]["all"]
    test_final = {s: eps(os.path.join(sel, f"test_{s}_final", "results.json")) for s in SEEDS}
    test_old = {s: eps(os.path.join(R, f"eval_{s}", "results.json")) for s in SEEDS}
    scripted = eps(os.path.join(R, "eval_scripted", "results.json"))
    r5 = [eps(os.path.join(R5, f"eval_{s}", "results.json")) for s in SEEDS]
    n = len(scripted)
    for e in (*test_final.values(), *test_old.values(), *r5):
        assert len(e) == n and all(x["id"] == y["id"] for x, y in zip(e, scripted))

    L = ["## Checkpoint selection (official r6 numbers)", "",
         "r6 first picked each seed's best.zip by most dockings on the test set (`experiments/test_sets/rendezvous_large.json`), "
         "the same 200 starts the results are reported on. That is selection on the test set (AGENTS.md: checkpoints are "
         "picked on a separate check set). The numbers in this section replace the test-set pick and are the official r6 numbers.", "",
         "- **Check set:** `experiments/test_sets/rendezvous_check.json`, 200 new starts from the same distribution as the "
         "test set (same box range as a Latin hypercube, same 0.2-0.8 m duck distances and any bearing and heading, the same "
         "160 uniform / 20 near-symmetric / 20 wrong-side split), with their own seeds (box poses 20261124, ducks 20261125, "
         "episode seeds 20000 + i). No start and no box pose repeats a test-set one (checked when the set is made, and by a test).",
         "- **Candidates:** training kept only the newest checkpoint, so the every-200k checkpoints are gone. What is left per "
         f"seed is the final checkpoint (step {FINAL}) and best.zip (the old test-set pick). The final checkpoint is the only "
         "one not chosen with the test set, so it is the official pick (as the re-selection plan says when intermediate "
         "checkpoints were not saved). best.zip's check-set score is shown for information.", ""]
    L += ["**Check set, rendezvous alone** (50 steps, the training ending, as the training evals)", "",
          "| seed | checkpoint | docked | position / heading error (mean) | used |", "|---|---|---|---|---|"]
    picks = {}
    for s in SEEDS:
        same = best[s]["step"] == FINAL
        c = check[s]["final"]
        L.append(f"| {s} | final, step {FINAL}" + (" (also the old best.zip)" if same else "") + f" | {rate(c['arrived'], c['n'])} | "
                 f"{c['pos_err_cm_mean']:.1f} cm / {c['yaw_err_deg_mean']:.1f} deg | **yes** |")
        if "best" in check[s]:
            c = check[s]["best"]
            L.append(f"| {s} | old best.zip, step {best[s]['step']} (picked on the test set) | {rate(c['arrived'], c['n'])} | "
                     f"{c['pos_err_cm_mean']:.1f} cm / {c['yaw_err_deg_mean']:.1f} deg | no |")
        picks[s] = {"step": FINAL, "old_step": best[s]["step"], "changed": not same}
    L += ["", "- " + "; ".join(f"**{s}:** step {FINAL}, " + ("unchanged (the old pick was already the final checkpoint)"
                                                              if not picks[s]["changed"] else f"changed from step {picks[s]['old_step']}")
                               for s in SEEDS) + ".", ""]
    L += ["**Test set, full pipeline** (200 starts; rendezvous up to 50 steps, then the frozen push policy; 95% intervals)", "",
          "| controller | docked in 50 steps | end-to-end push success | position error at handoff | heading error at handoff |",
          "|---|---|---|---|---|"]
    for s in SEEDS:
        L.append(row(f"**dock payout {s}, check-set pick = final (official)**", test_final[s]))
    for s in SEEDS:
        if picks[s]["changed"]:
            L.append(row(f"dock payout {s}, old test-set pick (step {picks[s]['old_step']}, superseded)", test_old[s]))
        else:
            same = all(x == y for x, y in zip(test_final[s], test_old[s]))
            L.append(f"| dock payout {s}, old test-set pick | same checkpoint as the final one; " +
                     ("re-run gives identical episodes" if same else "**re-run differs from the old eval**") + " | | | |")
    L.append(row("scripted", scripted))
    for i, s in enumerate(SEEDS):
        L.append(row(f"r5 BC warm start {s} (test-set pick, not re-picked)", r5[i]))
    L += ["", "Position and heading error: mean over the 200 starts of the two ducks' mean, with a 95% interval for that mean.", ""]

    def verdicts(title, other, other_rate_label, seed_rule):
        out = ["", f"**{title}** (same 200 starts, paired; seeds averaged per start)", ""]
        res = {}
        for key, label, f, unit in (("arrived", "docked in 50 steps", lambda x: 100.0 * x["arrived"], "points"),
                                    ("push", "end-to-end push success", lambda x: 100.0 * x["push_success"], "points"),
                                    ("yaw", "heading error at handoff", lambda x: err(x, "yaw_err_deg"), "deg"),
                                    ("pos", "position error at handoff", lambda x: err(x, "pos_err_cm"), "cm")):
            a = [sum(f(test_final[s][i]) for s in SEEDS) / len(SEEDS) for i in range(n)]
            b = [other(i, f) for i in range(n)]
            m, lo, hi = paired(a, b)
            seed_rates = [sum(f(x) for x in test_final[s]) / n for s in SEEDS]
            base = sum(b) / n
            if seed_rule and key in ("arrived", "push"):
                side = all(r > base for r in seed_rates) or all(r < base for r in seed_rates)
                v = ("measurably better" if lo > 0 and side else "measurably worse" if hi < 0 and side else "no measurable difference")
            else:
                v = "no measurable difference" if lo <= 0 <= hi else "measurable difference"
            res[key] = {"mean": m, "lo": lo, "hi": hi, "seeds": seed_rates, "other": base, "verdict": v}
            out.append(f"- {label}: dock payout minus {other_rate_label} {m:+.1f} {unit} ({lo:+.1f} to {hi:+.1f}); seeds "
                       f"{', '.join(f'{r:.1f}' for r in seed_rates)} vs {other_rate_label} {base:.1f}: **{v}**")
        return out, res

    o, vs_scripted = verdicts("Against scripted (the fixed rule: the paired interval excludes 0 and both seed rates are on the same side)",
                              lambda i, f: f(scripted[i]), "scripted", True)
    L += o
    o, vs_r5 = verdicts("Against r5, BC warm start (both seeds averaged)", lambda i, f: sum(f(e[i]) for e in r5) / len(r5), "r5", False)
    L += o
    L += ["", "r5 has the same flaw: its best.zip was also picked on the test set, and its checkpoints were not re-picked "
          "(they are gone too, and only its final checkpoints remain). Its numbers above are its old test-set picks, which "
          "favor r5, so the gap to r5 is if anything understated.", ""]
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "reselect.md"), "w").write("\n".join(L) + "\n")
    json.dump({"picks": picks, "check": check, "vs_scripted": vs_scripted, "vs_r5": vs_r5,
               "test_final": {s: {"arrived": sum(x["arrived"] for x in test_final[s]), "push": sum(x["push_success"] for x in test_final[s]), "n": n}
                              for s in SEEDS}},
              open(os.path.join(OUT, "reselect.json"), "w"), indent=1)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
