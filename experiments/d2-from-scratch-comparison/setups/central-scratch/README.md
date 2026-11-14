# central-scratch

One controller sees the whole scene and picks the commands for both ducks. It starts from random
weights. This is the baseline.

- **Config:** [config.yaml](config.yaml) (for new seeds; trained by scripts/rl/stage.py with `init: scratch`)
- **Seeds 1 to 3 are reused runs.** They were trained by the overnight queue with exactly these settings
  (fixed in-contact start, overnight layout, reward v1.1, 400k simulator steps, ppo seed 1, 2 and 3):
  - seed 1: `runs/overnight-20261112/runs/01_reference` (01_reference)
  - seed 2: `runs/overnight-20261112/runs/06_seed2`
  - seed 3: `runs/overnight-20261112/runs/07_seed3`
- **Evals:** these runs evaluated the fixed start every 10k simulator steps; new seeds every 25k.
- **Large outputs** (checkpoints, videos, logs, tensorboard) stay in each run folder under `runs/`.
- **Test set results:** [results/test_set/](results/test_set/) (compare_policies.py, 50 random box starts).
