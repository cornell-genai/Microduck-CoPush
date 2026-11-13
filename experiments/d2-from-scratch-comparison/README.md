# D2 from scratch: does decentralized control need the copied start?

**Status:** 3 seeds per setup done, 2026-11-13. Fixed-start comparison only; harder setups not started.

## The question

D2 (each duck runs the same network on its own view plus its partner's position) reached 74% on the
stage 1 test set, but it started as a copy of the centralized controller. Can D2 learn the task from
random weights, and how fast compared with a centralized controller that also starts from random weights?

## The 3 setups

All three use the same fixed in-contact start (overnight layout: target 0.60 m ahead and 0.30 m to the
right, so the box must turn), reward v1.1, PPO seed 1 for seed 1, and 400k simulator steps of training.

| setup | controller | starts from | seed 1 |
|---|---|---|---|
| [central-scratch](setups/central-scratch/) | one controller for both ducks | random weights | reused: 01_reference (seeds 2 and 3: 06_seed2, 07_seed3) |
| [d2-scratch](setups/d2-scratch/) | D2, one shared network per duck | random weights | new: `runs/d2-from-scratch/d2-scratch-s1` |
| [d2-distilled](setups/d2-distilled/) | D2, one shared network per duck | copy of the stage 1 controller | reused: `runs/decentral-p1-d2` |

The only code change is `init: scratch | distilled` in a stage config (scripts/rl/stage.py). D2
counts duck entries (2 per simulator step), so its configs say 800k steps for 400k simulator steps.

Notes on fairness:
- With the same PPO settings, D2 gets 2 samples per simulator step, so each update sees twice as many
  samples and takes twice as many minibatch steps. That is part of what "decentralized" means here.
- d2-distilled has a head start: its teacher had trained 400k + 980k steps. It shows what copying buys,
  not the same budget.

## Folder layout

```
README.md            this file: the question, setups, status, results so far
runs.yaml            which run folder is which setup and seed; add a line per new seed
setups/<setup>/      config.yaml, README.md, results/test_set/ (50-start test set)
comparison/          plots and summary table across all setups (scripts/rl/compare_setups.py)
```

Checkpoints, all videos, logs and tensorboard stay in the git-ignored `runs/` folders that runs.yaml
and each setup README point to. I added runs.yaml so the plot script finds seeds without guessing
folder names.

## How the comparison is measured

- **Learning curves** ([comparison/learning_curves.png](comparison/learning_curves.png)): the
  deterministic fixed-start eval episode logged during training (`videos/evals.jsonl`), sampled every
  25k simulator steps (the latest eval at or before each point). With several seeds: the mean line and a
  min to max band. One episode per point, so one seed's success curve is 0 or 1.
- **Test set** ([comparison/test_set_success.png](comparison/test_set_success.png)): the stage 1 test
  set, 50 random box starts these policies never trained on. It measures how well a fixed-start policy
  generalizes, not the task they trained on.
- **Cooperation** ([comparison/cooperation.png](comparison/cooperation.png)): duck A's share of the
  push and the share of steps where both ducks touch the box, on the test set.
- Table: [comparison/summary.md](comparison/summary.md).

## Results (3 seeds per setup)

**D2 learns the fixed start from random weights as reliably as central does: 3 of 3 seeds, at a
similar speed.** It generalizes a bit worse to random box starts, and it has a consistent habit of
commanding low speeds and over-turning the box. Copying the central controller first (distilled)
gives the best policies, but that setup had 1.38M steps of prior training.

| setup | seeds solving the fixed start | first fixed-start success (sim steps) | test set success (seeds) | long-turn wins (of 17, seeds) |
|---|---|---|---|---|
| central-scratch | 3 / 3 | 30k, 70k, 170k | **41%** (50, 28, 44) | 1, 0, 1 |
| d2-scratch | 3 / 3 | 75k, 50k, 150k | **33%** (32, 28, 38) | 0, 1, 2 |
| d2-distilled | 3 / 3 | at the first eval (10k, 25k, 25k) | **51%** (48, 48, 58) | 1, 3, 3 |

- **Learning speed: no measurable difference** between D2 and central from scratch. Their
  first-success steps overlap (50k to 150k against 30k to 170k), and both end with every seed
  succeeding in 32 to 37 steps.
- **Test set: D2 from scratch is lower on average (33% against 41%), but the ranges overlap** (28 to 38%
  against 28 to 50%). With 3 seeds that is a hint, not a result. Distilled D2 (48 to 58%) is above both,
  with its head start.
- **Cooperation is fine everywhere:** both ducks touch the box on 88 to 98% of test-set steps, duck A
  does 50 to 55% of the pushing, and there is 1 lazy-duck episode in 450 (central seed 2).
- **D2 from scratch moves slowly, on every seed:** both ducks are commanded below 0.05 m/s on 43%, 26%
  and 31% of test-set steps (central 1%, 11%, 0%; distilled 16%, 1%, 7%). It also over-turns the box
  on long-turn starts: 64, 145 and 136 deg of total turn where 55 are needed (central 14 to 28,
  distilled 17 to 56). Falls are similar (D2 from scratch 4, 0, 3; central 0, 4, 0).
- **What it means:** decentralized control does not need the central teacher to learn this start,
  but from scratch it finds a slower, more turn-happy way of pushing that transfers less well to
  random box starts. That supports the plan: improve the central controller, then distill it into
  per-duck controllers.

Per-seed table: [comparison/summary.md](comparison/summary.md). Per-setup test-set details:
`setups/<setup>/results/test_set/comparison.md`.

### Plots and clips

- [comparison/learning_curves.png](comparison/learning_curves.png): top row, each run's own steps; bottom
  row, d2-distilled shifted right by its 1.38M prior steps.
- [comparison/test_set_success.png](comparison/test_set_success.png),
  [comparison/cooperation.png](comparison/cooperation.png)
- GIFs of each setup's seed 1 final policy on the fixed start: [central-scratch](comparison/final_central-scratch.gif),
  [d2-scratch](comparison/final_d2-scratch.gif), [d2-distilled](comparison/final_d2-distilled.gif), and all three
  [side by side](comparison/final_side_by_side.gif) (`make_gifs.sh`).

### Run notes

- Wall time per run: 26.5 to 29.6 min, except d2-scratch seed 2 (41.2 min, on battery with other work
  running) and seed 1's 27.0 min of training inside 42.5 min on the clock (the laptop slept).
- d2-distilled seed 3 trained 800,000 duck entries, not 802,816: the disk filled while it wrote its
  final video, and it was resumed from its last checkpoint (one PPO update short, 0.35%).
- Seeds 2 and 3 ran with `scripts/rl/stage.py --seed N` from `runs/d2-from-scratch/seeds_2_3.sh`.
