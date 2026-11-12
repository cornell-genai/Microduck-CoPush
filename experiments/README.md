# Experiments: the generalization plan

One folder per stage, each changing ONE thing from the stage before. Every stage is tested on
fixed held-out starts in [test_sets/](test_sets/), so any policy can be scored on any earlier
stage's exam.

| Stage | One change | Status | Headline result |
|---|---|---|---|
| [stage1-random-box-pose](stage1-random-box-pose/) | Random box starts (offset up to 0.15 m, angle up to 45 deg), ducks still against the box | done | 60% on its 50-start test set (01_reference 50%, pivot_push 32%); full range by step 80k, early stop at 980k; blind spot: box turned to positive angles (2/17) |
| [stage1b-turn-direction-fix](stage1b-turn-direction-fix/) | Diagnose the positive-angle blind spot, then one fix | stopped after diagnosis (UNCLEAR) | Not physical (pivot turns 12.7 vs 13.9 deg/s both ways) and the policy does turn CW; positive starts need about 55 deg of CW turning first, negative about 1 deg. No training yet |

## Layout

```
experiments/
  README.md                  this index: one line per stage
  test_sets/<stage>.json     the fixed held-out starts ("exam"), written once, never trained on
  <stage>/
    README.md                goal, the one change, status, results, videos, next step
    config.yaml              the stage's settings, on top of the shared configs it names
    results/                 small committed outputs: test-set table, per-episode JSON, plots
```

Large outputs (checkpoints, all videos, logs, tensorboard) go to the git-ignored
`runs/<stage>/`, and the stage README links to them.

## Commands

```sh
C=experiments/<stage>/config.yaml
scripts/rl.sh scripts/rl/test_set.py make --config $C            # once: the exam
scripts/rl.sh scripts/rl/stage.py --config $C                    # train (resumes from its last checkpoint)
scripts/rl.sh scripts/rl/test_set.py eval --config $C            # every controller on the exam
scripts/rl.sh scripts/rl/test_set.py side-by-side --config $C --left pivot_push --right stage1
```
