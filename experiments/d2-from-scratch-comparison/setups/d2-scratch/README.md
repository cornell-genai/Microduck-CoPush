# d2-scratch

Each duck runs the same network on its own view plus its partner's position and heading (D2), and picks
only its own forward speed and turn rate. The network starts from **random weights**
(`init: scratch`). Everything else matches d2-distilled.

- **Config:** [config.yaml](config.yaml)
- **Seed 1:** `runs/d2-from-scratch/d2-scratch-s1` (checkpoints, all videos, `videos/evals.jsonl`,
  tensorboard); training log `runs/d2-from-scratch/d2-scratch-s1.log`
- **Evals:** the fixed start every 25k simulator steps, plus a 3-episode success check every 25k.
- **Steps:** 800k duck entries = 400k simulator steps, the same simulated time as central-scratch.
- **Test set results:** [results/test_set/](results/test_set/)
