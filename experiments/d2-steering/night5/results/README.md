# Night 5: raw per-episode results (kept outside git)

The `comparison.json` files for these evaluations are thousands to tens of thousands of lines each, so they live in the git-ignored `runs/` folder, not here. The summary tables (`comparison.md`) next to this file stay in git.

- **Where:** `runs/d2-steering/night5/results/<set>/comparison.json`, one folder per evaluation set. Regenerate by rerunning the overnight script that wrote them (see SUMMARY.md).
- **Format:** written by `scripts/rl/compare_policies.py`. Top level: `test_set`, `config`, `wall_s` (seconds per policy), `episodes`: {policy name: a list with one record per start}. Each record has `id`, `side`, `reason` (success, timeout, fell, ...), `fell`, `box_lost`, `push_share_a`, `overshoot`, `idle_frac`, `hold_a_frac` / `hold_b_frac`, `steps`, box path and turn measures.
- **Count:** 6 files:

| set | lines |
|---|---|
| a_L1 | 12,206 |
| a_L2 | 12,224 |
| eval_L1 | 24,431 |
| eval_L2 | 24,454 |
| eval_clean | 36,573 |
| eval_noisy | 36,477 |
