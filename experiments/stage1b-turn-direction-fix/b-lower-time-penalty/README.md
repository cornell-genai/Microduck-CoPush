# Stage 1b, experiment B: lower time penalty

**Status:** done (2026-11-12). 1M steps with no early stop. The training clock read 81 min, but it took
101 min of real time because the machine was busy with other work.

## The one change

Reward v1.3 is v1.1 with a time penalty of −0.01 per step instead of −0.03 (see
[docs/REWARD_LOG.md](../../../docs/REWARD_LOG.md)). The idea was that time pressure makes the policy start
pushing before the long turn is finished. Everything else is stage 1's, including the normal start mix.
Training warm-starts from the stage 1 policy. Config: [config.yaml](config.yaml).

Checks ran on the fixed 50-start check set every 50k steps. Success stayed between 58% and 74%, so
training never stopped early. History: [results/training.json](results/training.json).

## Test set (stage 1's 50 starts)

| policy | overall | < −15° | −15° to +15° | > +15° |
|---|---|---|---|---|
| stage1 | 60% | 15/17 | 13/16 | 2/17 |
| **B** | **68%** | 17/17 | 16/16 | 1/17 |

- Start by start against stage 1: 5 wins gained, 1 lost. All the gains are on the easy sides. On the long-turn
  side it loses one start and gains none.
- On long-turn starts it turns 37° before the box has moved 0.20 m toward the target, less than stage 1's
  40°. The 55° the target needs is still out of reach.
- **Standing still is partly back, but only on the hard side.** On long-turn starts, both ducks are commanded
  below 0.05 m/s for 34% of steps (stage 1: 12%, A: 15%). On the easy sides it's 8 to 10%.
- **No slow wandering in general.** Episodes are no longer (54 steps on average against 57), and no episode leaves the
  box where it started. In the clip below, B gets the box within 0.31 m of the target, then waits while Shoe
  Push lets the box drift away and turn 59° off. Stage 1 also loses this start.
- Falls 2 (stage 1: 3), no box lost, push share 50 / 50%, overshoots 13.

Tables: [results/test_set.md](results/test_set.md); plot: [results/difficulty.png](results/difficulty.png).
Returns here are under reward v1.3, so don't compare them with stage 1's v1.1 returns. Compare success instead.

## Videos

These are in `runs/stage1b-b-lower-time-penalty/`:
- `videos/side_by_side/start44_stage1_vs_b_time_penalty.mp4`: B's most idle long-turn start (+31°). Both
  time out. Stage 1 is on the left.
- `videos/step_1001472_final.mp4`: the final policy on the video seed.
