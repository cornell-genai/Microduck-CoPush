#!/usr/bin/env python3
"""Summary of the episode reviews of a run: how often the reviewers agree with the metric.

    scripts/rl.sh scripts/review/summarize.py --run r6-dock-payout          (plain python3 works too: no simulator)
    scripts/rl.sh scripts/review/summarize.py --run r6-dock-payout --json

Reads every experiments/**/<run>/reviews/*.json (all reviewers, all sessions; a reviewer's newest label of an episode
wins) and prints: the number reviewed, the agreement with task success and with cooperative success (Wilson 95%
intervals), the counts per reason, every disagreement with its start id, and, with several reviewers, the episodes
they labeled differently. Rates use the blind label (the one given before the metric was shown).

A label agrees with a metric when "real success" meets a metric success, or "fake success" / "real failure" meets a
metric failure. "Unclear" labels are counted but left out of the rates. The combined rates count each episode once and
leave out episodes on which reviewers gave different verdicts. The labels are for catching metric bugs, not ground truth.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reviewlib as rl  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--reviewer", action="append", default=[], help="only these reviewers (repeatable)")
    ap.add_argument("--policy", default=None, help="only this policy of the run (s1, l2_s2, ...)")
    ap.add_argument("--reviews-dir", default=None, help="read the label files of this folder instead of experiments/**/<run>/reviews")
    ap.add_argument("--json", action="store_true", help="print the numbers as JSON")
    a = ap.parse_args()
    rows = rl.load_reviews(a.run, reviews_dir=rl.repo_path(a.reviews_dir) if a.reviews_dir else None)
    if a.reviewer:
        rows = [r for r in rows if r["reviewer"] in a.reviewer]
    if a.policy:
        rows = [r for r in rows if rl.norm(r["policy"]) == rl.norm(a.policy)]
    s = rl.summarize(rows)
    print(json.dumps(s, indent=1) if a.json else rl.report(a.run, s), end="" if not a.json else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
