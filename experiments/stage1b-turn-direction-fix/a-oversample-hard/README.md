# Stage 1b, experiment A: oversample the long-turn starts

**Status:** done (2026-11-12). 1M steps with no early stop. The training clock read 73 min.

## The one change

Half of training starts are turned between +15° and +45°, the long-turn side. The other half are
between −45° and +15°. That's `env.box_start.hard_frac: 0.5`, where stage 1's uniform mix put about a
third of starts on the long-turn side. Everything else is stage 1's: reward v1.1, the same range, 8 envs.
Training warm-starts from the stage 1 policy. Config: [config.yaml](config.yaml).

Checks ran on the fixed 50-start check set ([../../test_sets/stage1_checks.json](../../test_sets/stage1_checks.json))
every 50k steps. Success stayed between 56% and 72%, so training never stopped early. Full history:
[results/training.json](results/training.json).

## Test set (stage 1's 50 starts)

| policy | overall | < −15° | −15° to +15° | > +15° |
|---|---|---|---|---|
| stage1 | 60% | 15/17 | 13/16 | 2/17 |
| **A** | **72%** | 16/17 | 16/16 | 4/17 |

- Start by start against stage 1: 7 wins gained, 1 lost.
- On the long-turn side it gains 2 starts (+16° and +21°) and loses none. Both are in the +15° to +30° bucket
  (2/8 → 4/8). From +30° to +45° it's still 0/9.
- Long-turn starts need 55° of turning to aim at the target. A turns 44° on average before the box has moved
  0.20 m toward the target, where stage 1 turned 40°.
- **New problem:** 5 falls (stage 1: 3), all on the long-turn side and all duck A. `fall_duck_a` shows up in
  6 episodes and `bad_part_duck_a` in 10.
- Fewer timeouts (9 against 17) and overshoots (10 against 14). Push share 52 / 48%. No box lost.

Tables: [results/test_set.md](results/test_set.md); plot: [results/difficulty.png](results/difficulty.png).
The three-way comparison is in [../results/comparison.md](../results/comparison.md).

## Videos

These are in `runs/stage1b-a-oversample-hard/`:
- `videos/side_by_side/start45_stage1_vs_a_oversample.mp4`: the hardest long-turn start A wins and stage 1
  loses (+21°). Stage 1 is on the left.
- `videos/step_1001472_final.mp4`: the final policy on the video seed, which is an easy start.
