# D2 steering: can two independent ducks learn to pivot the box?

**Question:** on long-turn starts (box turned more than +15 degrees) every policy wins only 0 to 24% (D2 stage 1: 15%
on 200 starts). Can the decentralized controller learn to pivot, one duck holding while the other pushes, if each duck
gets a real stand-still action? And does it still work when the ducks' starting poses are not perfect?

**Status:** set up, not run yet. One unattended night runs everything: [scripts/rl/overnight_steering.py](../../scripts/rl/overnight_steering.py).
Results land in [SUMMARY.md](SUMMARY.md) (rewritten after every step) and `results/`.

| run | the one change | config |
|---|---|---|
| reference | D2 stage 1 (policies-v1 `stage1-d2`), zero-shot | |
| Run A | + the stand-still action (`env.stand_still`, default threshold 0.02 m/s) | [run-a/config.yaml](run-a/config.yaml) |
| Run B | Run A + duck start noise (`start_noise`: heading 5 deg per duck, spacing 0.02 m, setback 0.01 m per duck) | [run-b/config.yaml](run-b/config.yaml) |

Later nights: [night 2](night2/SUMMARY.md) fixed budget and two seeds; [night 3](night3/SUMMARY.md) both-held penalty (reward v1.4, rejected);
[night 4](night4/SUMMARY.md) bounded exploration (rejected: measurably worse than night 2's Run A, about 3x the both-idle stalls).

Both runs: warm start from D2 stage 1, stage 1 random box starts, reward v1.1, 2M duck steps, the same training seed
(ppo.seed 1); Run A stops early on the stage 1 check set, Run B on the noisy check set. Evaluation on `stage1_large.json`
and `stage1_noisy_large.json` (200 starts each; the noisy env and its sets: [noisy-sets/config.yaml](noisy-sets/config.yaml)).
