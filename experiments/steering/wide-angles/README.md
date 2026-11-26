# Central steering: widen box angles to ±90 degrees

**Status:** complete (2026-11-24). Both training seeds reached the full ±90-degree range at
400,000 steps, and the held-out evaluation and Stage 1 forgetting check are complete. See
[SUMMARY.md](SUMMARY.md) for confidence intervals, failure diagnostics, raw comparisons and clips.

This stage keeps the successful central stand-still controller and changes one task setting: the
box-angle range widens from ±45 to ±90 degrees. Each PPO seed warm-starts from its matching
stand-still seed and trains for a fixed 1,000,000 additional simulator steps.

The curriculum starts at the solved ±45-degree range and advances through ±56.25, ±67.5, ±78.75
and ±90 degrees when success is at least 80% on 50 separate fixed check starts. Those starts are
scaled to the current level; the immutable 200-start final test set is never used for widening.

Run or resume the complete experiment with:

```sh
scripts/rl.sh scripts/rl/overnight_wide_angles.py --dry-run
scripts/rl.sh scripts/rl/overnight_wide_angles.py
```

The runner is restart-safe. It evaluates both original policies zero-shot, trains both matching
seeds, evaluates all four policies on the ±90-degree test set, repeats the Stage 1 test as a
forgetting check, and records one success and one failure comparison clip. The generated report is
written to `SUMMARY.md`; checkpoints and logs remain under the ignored `runs/` directory.

## Frozen inputs

| input | SHA-256 |
|---|---|
| stand-still seed 1 | `6b69e13607175ccf128a5c298a1b156c512d8e58cc791df9990226608415a679` |
| stand-still seed 2 | `3233c1e397a85b37a435ae3f50a88827f88324c244e4567992efa9b7926eb616` |
| 200-start final test set | `ae621b9f480979a36e66cc8281376b0998688b6d672273f5995a1e5f552fe39c` |
| 50-start curriculum check set | `f7c02ccf1b0b79c4712a829c4ee58cb801f91dac54b88cbb91a539a37bf2acb8` |

The report includes 95% intervals overall and in five signed angle bands, paired two-seed
comparisons against the original policies, Stage 1 forgetting, falls, box loss, overshoots,
time-outs, pivots, both-held stalls, push share and lazy-duck episodes.
