# Policy comparison on experiments/test_sets/stage1.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| stage1 | 60% (30/50) | 15/17 | 13/16 | 2/17 |
| a_oversample | 72% (36/50) | 16/17 | 16/16 | 4/17 |
| b_time_penalty | 68% (34/50) | 17/17 | 16/16 | 1/17 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| stage1 | 55 | 40 (20 to 93) | 38 | 16/17 | 2/17 |
| a_oversample | 55 | 44 (17 to 111) | 39 | 15/17 | 4/17 |
| b_time_penalty | 55 | 37 (7 to 74) | 51 | 15/17 | 1/17 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|
| stage1 | 3/50 | 0/50 | 14/50 | 17/50 | 46% | 13.5% | 1.11 | 0/50 | 57 | bad_part_duck_a 8, bad_part_duck_b 2, contact_share 19, fall_duck_a 5, fall_duck_b 1, reward_vs_dist 3 |
| a_oversample | 5/50 | 0/50 | 10/50 | 9/50 | 52% | 7.6% | 1.01 | 0/50 | 49 | bad_part_duck_a 10, bad_part_duck_b 1, contact_share 8, fall_duck_a 6, reward_vs_dist 1 |
| b_time_penalty | 2/50 | 0/50 | 13/50 | 14/50 | 50% | 17.7% | 1.07 | 0/50 | 54 | bad_part_duck_a 5, bad_part_duck_b 1, contact_share 13, fall_duck_a 3, fall_duck_b 1 |
