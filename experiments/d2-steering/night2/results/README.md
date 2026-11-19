# Night 2: raw per-episode results (kept outside git)

The `comparison.json` files for these evaluations are thousands to tens of thousands of lines each, so they live in the git-ignored `runs/` folder, not here. The summary tables (`comparison.md`) next to this file stay in git.

- **Where:** `runs/d2-steering/night2/results/<set>/comparison.json`, one folder per evaluation set. Regenerate by rerunning the overnight script that wrote them (see SUMMARY.md).
- **Format:** written by `scripts/rl/compare_policies.py`. Top level: `test_set`, `config`, `wall_s` (seconds per policy), `episodes`: {policy name: a list with one record per start}. Each record has `id`, `side`, `reason` (success, timeout, fell, ...), `fell`, `box_lost`, `push_share_a`, `overshoot`, `idle_frac`, `hold_a_frac` / `hold_b_frac`, `steps`, box path and turn measures.
- **Count:** 8 files:

| set | lines |
|---|---|
| diag100_large | 6,165 |
| diag100_noisy | 6,137 |
| diag150_large | 6,165 |
| diag150_noisy | 6,138 |
| eval100_large | 42,649 |
| eval100_noisy | 42,574 |
| eval150_large | 42,669 |
| eval150_noisy | 42,606 |
