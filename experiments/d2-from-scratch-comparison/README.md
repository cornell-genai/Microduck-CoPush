# D2 from scratch: does decentralized control need the copied start?

**Status:** Part 1 done (setup and smoke test), 2026-11-13. One seed of D2 from scratch; seeded runs not started.

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

## Results so far (smoke test: d2-scratch seed 1)

**D2 learns the fixed start from random weights, about as fast as central from scratch.** Its first
fixed-start success comes at 75k simulator steps (central seeds: 30k, 70k, 170k). It wobbles until 150k
(a timeout at 100k, a fall at 125k), then succeeds at every eval through 400k. The final episode takes 35
steps (central 32 to 37, d2-distilled 31). One seed, so this is a smoke test, not a result.

| setup | seeds | first fixed-start success (sim steps) | final fixed-start eval | test set success | duck A push share | both touching | lazy duck |
|---|---|---|---|---|---|---|---|
| central-scratch | 3 | 30k, 70k, 170k | success in all 3 (32 to 37 steps) | 41% (50, 28, 44) | 52% | 95% | 1/150 |
| d2-scratch | 1 | 75k | success, 35 steps | 32% | 55% | 92% | 0/50 |
| d2-distilled | 1 | 10k (first eval) | success, 31 steps | 48% | 50% | 94% | 0/50 |

- **The test set is a side measure.** These policies trained only on the fixed start. D2 from scratch
  generalizes to random box starts less well (32%) than central seed 1 (50%), but within the range of
  the central seeds (28 to 50%).
- **Cooperation is fine:** both ducks touch the box on 92% of test-set steps, duck A does 55% of the
  pushing, and no episode has a lazy duck.
- **What to watch:** D2 from scratch commands low forward speeds. On 43% of test-set steps both ducks
  are commanded below 0.05 m/s (central 0 to 11%, d2-distilled 16%). On the fixed start, duck B
  averages 0.05 m/s against duck A's 0.12, so A turns the box while B mostly holds. Central seed 2 does
  the same (0.015 against 0.17). It also has the most test-set falls (4) and turns the box more on long-turn starts (64 deg
  total turn against 55 needed). We have no direct measure of the ducks pushing against each other.
  In the final video, both stay on the push policy and the box moves steadily into the target.
- Final video: `runs/d2-from-scratch/d2-scratch-s1/videos/step_802816_final.mp4`.
- Wall time: 27.0 min of training (01_reference 35.9, central seeds 2 and 3: 26). Test set for all 5
  runs: 2.9 min.
