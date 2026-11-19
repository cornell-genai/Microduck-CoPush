# Night 1: raw per-episode results (kept outside git)

The `comparison.json` files for these evaluations are thousands to tens of thousands of lines each, so they live in the git-ignored `runs/` folder, not here. The summary tables (`comparison.md`) next to this file stay in git.

- **Where:** `runs/d2-steering/results/<set>/comparison.json`, one folder per evaluation set. Regenerate by rerunning the overnight script that wrote them (see SUMMARY.md).
- **Format:** written by `scripts/rl/compare_policies.py`. Top level: `test_set`, `config`, `wall_s` (seconds per policy), `episodes`: {policy name: a list with one record per start}. Each record has `id`, `side`, `reason` (success, timeout, fell, ...), `fell`, `box_lost`, `push_share_a`, `overshoot`, `idle_frac`, `hold_a_frac` / `hold_b_frac`, `steps`, box path and turn measures.
- **Count:** 4 files:

| set | lines |
|---|---|
| eval_large | 12,266 |
| eval_noisy | 12,244 |
| zero_shot_large | 6,054 |
| zero_shot_noisy | 6,102 |
