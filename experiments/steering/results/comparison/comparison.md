# Policy comparison on experiments/test_sets/stage1_large.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| stage1 | 60% (121/200) | 56/67 | 60/67 | 5/66 |
| control_s1 | 66% (132/200) | 61/67 | 57/67 | 14/66 |
| control_s2 | 68% (136/200) | 66/67 | 58/67 | 12/66 |
| stand_s1 | 96% (192/200) | 65/67 | 66/67 | 61/66 |
| stand_s2 | 98% (197/200) | 66/67 | 67/67 | 64/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| stage1 | 57 | 40 (15 to 97) | 40 | 50/66 | 5/66 |
| control_s1 | 57 | 34 (-35 to 103) | 23 | 60/66 | 14/66 |
| control_s2 | 57 | 37 (-46 to 107) | 29 | 55/66 | 12/66 |
| stand_s1 | 57 | 44 (21 to 78) | 36 | 66/66 | 61/66 |
| stand_s2 | 57 | 44 (24 to 75) | 35 | 66/66 | 64/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stage1 | 14/200 | 2/200 | 60/200 | 63/200 | 47% | 90% | 3/200 | 16.3% | 1.14 | 0/200 | 57 | bad_part_duck_a 24, bad_part_duck_b 4, contact_share 61, fall_duck_a 21, fall_duck_b 1, reward_vs_dist 5, spin 1 |
| control_s1 | 12/200 | 1/200 | 45/200 | 55/200 | 50% | 85% | 3/200 | 10.9% | 1.03 | 0/200 | 54 | bad_part_duck_a 22, bad_part_duck_b 14, contact_share 76, fall_duck_a 18, fall_duck_b 8, reward_vs_dist 13, spin 1 |
| control_s2 | 16/200 | 3/200 | 46/200 | 45/200 | 52% | 88% | 4/200 | 17.8% | 1.04 | 0/200 | 52 | bad_part_duck_a 19, bad_part_duck_b 14, contact_share 56, fall_duck_a 24, fall_duck_b 9, reward_vs_dist 15, spin 1 |
| stand_s1 | 1/200 | 0/200 | 0/200 | 7/200 | 77% | 50% | 97/200 | 2.0% | 0.71 | 0/200 | 39 | contact_share 137, edge 3, fall_duck_b 1, reward_vs_dist 9 |
| stand_s2 | 0/200 | 0/200 | 0/200 | 3/200 | 80% | 42% | 111/200 | 2.5% | 0.70 | 0/200 | 39 | bad_part_duck_a 1, bad_part_duck_b 1, contact_share 132, edge 3, reward_vs_dist 7 |
