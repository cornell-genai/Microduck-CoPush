# D2 from scratch: does decentralized control need the copied start?

**Status:** 10 seeds each for central and D2 from scratch, 3 for distilled, done 2026-11-14. Fixed-start
comparison only; harder setups not started.

## The question

D2 (each duck runs the same network on its own view plus its partner's position) reached 74% on the
stage 1 test set, but it started as a copy of the centralized controller. Can D2 learn the task from
random weights, and how fast compared with a centralized controller that also starts from random weights?

## The 3 setups

All three use the same fixed in-contact start (overnight layout: target 0.60 m ahead and 0.30 m to the
right, so the box must turn), reward v1.1, PPO seed N for seed N, and 400k simulator steps of training.

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

## Results (10 seeds for central and D2 from scratch, 3 for distilled)

**With 10 seeds each, D2 from scratch matches central from scratch: 40% against 46% on the test set,
no measurable difference.** The 8-point gap at 3 seeds (33% against 41%) was mostly seed luck. D2 gets
there with a different style: more idling, more over-turning, and fewer lazy-duck episodes. Copying the
central controller first (distilled) still gives the best mean, 51%, but with 3 seeds and 1.38M steps
of prior training.

| setup | seeds solving the fixed start | first fixed-start success (sim steps) | test set success | long-turn wins (of 17 per seed) |
|---|---|---|---|---|
| central-scratch | 10 / 10 | median 60k (25k to 200k) | **46%** (28 to 64%) | 6 of 170 |
| d2-scratch | 10 / 10 | median 75k (25k to 150k) | **40%** (28 to 60%) | 9 of 170 |
| d2-distilled | 3 / 3 | at the first eval (10k, 25k, 25k) | **51%** (48, 48, 58%) | 7 of 51 |

Per seed, first fixed-start success / test set:

| seed | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| central-scratch | 70k / 50% | 170k / 28% | 30k / 44% | 200k / 40% | 100k / 32% | 50k / 48% | 25k / 54% | 50k / 52% | 25k / 64% | 200k / 44% |
| d2-scratch | 75k / 32% | 50k / 28% | 150k / 38% | 50k / 50% | 25k / 34% | 125k / 60% | 125k / 40% | 75k / 28% | 150k / 38% | 50k / 48% |

- **Test set: no measurable difference.** The means differ by 6 points, the ranges nearly coincide
  (28 to 64% against 28 to 60%), and a permutation test on the 10 + 10 seed scores gives p = 0.23.
  Distilled D2 (48 to 58%) is above both means but inside central's range.
- **Learning speed: no measurable difference.** Every seed of both setups solves the fixed start,
  and the first-success steps overlap. Central seeds 1 to 3 (the overnight runs) logged an eval
  every 10k steps, the rest every 25k, so first-success steps are only that precise.
- **The hard side stays unsolved by all setups:** 0 to 3 of the 17 long-turn starts per seed. The
  differences come from the other 33 starts.
- **D2 idles, on every seed:** both ducks are commanded below 0.05 m/s on 11 to 47% of test-set steps
  (mean 29%). Central mostly does not (mean 9%, 0 to 11% on 8 seeds), but 2 central seeds also idle
  (42% and 23%), and the second of them is central's best seed (64%). So idling is D2's usual style,
  not by itself the reason for failing.
- **D2 over-turns the box on long-turn starts, on every seed:** 56 to 145 deg of total turn where 55
  are needed. Central under-turns (-2 to 46 deg).
- **Cooperation is fine everywhere, and D2 shares more evenly:** both ducks touch the box on 87 to 98%
  of test-set steps and duck A does 50 to 55% of the pushing in both setups, but lazy-duck episodes are
  1 in 500 for D2 against 7 in 500 for central (4 of them central seed 7). Falls: D2 15 in 500,
  central 20 in 500; box lost: D2 5, central 11.
- **What it means:** decentralized control does not need the central teacher to learn this start, and
  with enough seeds it is no worse than central from scratch on random box starts. Distillation stays
  the plan for the end (it gives the best policies, and the final central controller will know more
  than this fixed start), but D2 from scratch is a real alternative, not a weaker one.

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
- Seeds 4 to 10 (central and D2 from scratch, interleaved) ran overnight from
  `runs/d2-from-scratch/seeds_4_10.sh`: 24 to 36 min per run, all 14 finished, intermediate
  checkpoints deleted after each run (final policies and videos kept). Central seeds 4 to 10 are the
  first central runs through `scripts/rl/stage.py`; their resolved config matches 01_reference's
  except for the seed and the 25k eval interval.
- The GIFs show seed 1 of each setup.
