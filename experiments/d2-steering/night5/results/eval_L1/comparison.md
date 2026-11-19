# Policy comparison on experiments/test_sets/stage1_L1_large.json

One deterministic episode per start, env from `experiments/d2-steering/night5/sets/L1/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| l1_s1 | 90% (179/200) | 65/67 | 59/67 | 55/66 |
| l2_s1 | 88% (177/200) | 64/67 | 59/67 | 54/66 |
| l1_s2 | 92% (184/200) | 66/67 | 60/67 | 58/66 |
| l2_s2 | 90% (180/200) | 66/67 | 55/67 | 59/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| l1_s1 | 57 | 45 (-13 to 67) | 36 | 64/66 | 55/66 |
| l2_s1 | 57 | 46 (-12 to 74) | 37 | 64/66 | 54/66 |
| l1_s2 | 57 | 42 (-34 to 72) | 34 | 65/66 | 58/66 |
| l2_s2 | 57 | 44 (-17 to 70) | 35 | 65/66 | 59/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| l1_s1 | 5/200 | 1/200 | 0/200 | 15/200 | 68% | 44% | 94/200 | 6.4% | 0.70 | 5/200 | 42 | bad_part_duck_a 3, bad_part_duck_b 1, contact_share 159, edge 1, fall_duck_a 5, reward_vs_dist 18 |
| l2_s1 | 5/200 | 1/200 | 1/200 | 17/200 | 63% | 42% | 84/200 | 6.5% | 0.71 | 4/200 | 43 | bad_part_duck_a 2, bad_part_duck_b 2, contact_share 164, fall_duck_a 5, fall_duck_b 2, reward_vs_dist 12 |
| l1_s2 | 2/200 | 0/200 | 0/200 | 14/200 | 75% | 48% | 100/200 | 4.2% | 0.69 | 3/200 | 41 | bad_part_duck_a 1, contact_share 118, edge 1, fall_duck_a 2, reward_vs_dist 7 |
| l2_s2 | 3/200 | 1/200 | 0/200 | 16/200 | 77% | 44% | 107/200 | 5.5% | 0.70 | 4/200 | 43 | bad_part_duck_a 1, bad_part_duck_b 1, contact_share 120, edge 3, fall_duck_a 3, fall_duck_b 1, reward_vs_dist 18 |
