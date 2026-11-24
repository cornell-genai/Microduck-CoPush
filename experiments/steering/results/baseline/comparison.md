# Policy comparison on experiments/test_sets/stage1_large.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| stage1 | 60% (121/200) | 56/67 | 60/67 | 5/66 |
| stage1_zero_shot_hold | 20% (40/200) | 17/67 | 18/67 | 5/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| stage1 | 57 | 40 (15 to 97) | 40 | 50/66 | 5/66 |
| stage1_zero_shot_hold | 57 | 59 (21 to 77) | 38 | 63/66 | 5/66 |

## Failure modes and idling (all 200 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stage1 | 14/200 | 2/200 | 60/200 | 63/200 | 47% | 90% | 3/200 | 16.3% | 1.14 | 0/200 | 57 | bad_part_duck_a 24, bad_part_duck_b 4, contact_share 61, fall_duck_a 21, fall_duck_b 1, reward_vs_dist 5, spin 1 |
| stage1_zero_shot_hold | 32/200 | 0/200 | 24/200 | 128/200 | 70% | 27% | 59/200 | 8.9% | 0.67 | 0/200 | 84 | bad_part_duck_a 19, bad_part_duck_b 5, contact_share 198, edge 4, fall_duck_a 18, fall_duck_b 15, reward_vs_dist 5 |
