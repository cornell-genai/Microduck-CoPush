# Policy comparison on experiments/test_sets/stage1_large.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| a_s1 | 94% (189/200) | 66/67 | 64/67 | 59/66 |
| a_s2 | 96% (192/200) | 67/67 | 65/67 | 60/66 |
| a_s1_smp1 | 92% (183/200) | 65/67 | 60/67 | 58/66 |
| a_s1_smp2 | 92% (183/200) | 63/67 | 62/67 | 58/66 |
| a_s1_smp3 | 91% (182/200) | 64/67 | 60/67 | 58/66 |
| a_s2_smp1 | 98% (195/200) | 67/67 | 63/67 | 65/66 |
| a_s2_smp2 | 96% (191/200) | 67/67 | 63/67 | 61/66 |
| a_s2_smp3 | 98% (196/200) | 67/67 | 67/67 | 62/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| a_s1 | 57 | 45 (31 to 69) | 34 | 66/66 | 59/66 |
| a_s2 | 57 | 48 (32 to 73) | 39 | 66/66 | 60/66 |
| a_s1_smp1 | 57 | 45 (16 to 65) | 36 | 66/66 | 58/66 |
| a_s1_smp2 | 57 | 46 (26 to 76) | 37 | 66/66 | 58/66 |
| a_s1_smp3 | 57 | 46 (16 to 73) | 37 | 66/66 | 58/66 |
| a_s2_smp1 | 57 | 49 (35 to 79) | 39 | 66/66 | 65/66 |
| a_s2_smp2 | 57 | 51 (26 to 76) | 40 | 66/66 | 61/66 |
| a_s2_smp3 | 57 | 50 (22 to 73) | 40 | 66/66 | 62/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a_s1 | 1/200 | 0/200 | 0/200 | 10/200 | 64% | 52% | 81/200 | 4.3% | 0.72 | 0/200 | 40 | bad_part_duck_a 1, bad_part_duck_b 1, contact_share 148, fall_duck_a 1, reward_vs_dist 11 |
| a_s2 | 1/200 | 0/200 | 0/200 | 7/200 | 71% | 56% | 84/200 | 4.3% | 0.73 | 0/200 | 40 | contact_share 121, fall_duck_a 1, reward_vs_dist 23 |
| a_s1_smp1 | 3/200 | 0/200 | 0/200 | 14/200 | 63% | 50% | 78/200 | 4.7% | 0.71 | 0/200 | 42 | bad_part_duck_a 3, bad_part_duck_b 3, contact_share 149, fall_duck_a 3, fall_duck_b 2, reward_vs_dist 12 |
| a_s1_smp2 | 2/200 | 0/200 | 0/200 | 15/200 | 63% | 53% | 76/200 | 4.8% | 0.72 | 0/200 | 42 | bad_part_duck_a 2, bad_part_duck_b 1, contact_share 153, edge 1, fall_duck_a 3, reward_vs_dist 12 |
| a_s1_smp3 | 2/200 | 0/200 | 0/200 | 16/200 | 63% | 50% | 79/200 | 5.4% | 0.72 | 0/200 | 42 | bad_part_duck_a 3, contact_share 155, edge 1, fall_duck_a 2, reward_vs_dist 16 |
| a_s2_smp1 | 0/200 | 0/200 | 0/200 | 5/200 | 70% | 54% | 86/200 | 4.2% | 0.72 | 0/200 | 41 | contact_share 123, reward_vs_dist 23 |
| a_s2_smp2 | 0/200 | 0/200 | 0/200 | 9/200 | 70% | 55% | 83/200 | 5.2% | 0.73 | 0/200 | 42 | contact_share 127, edge 1, reward_vs_dist 20 |
| a_s2_smp3 | 0/200 | 0/200 | 0/200 | 4/200 | 69% | 56% | 81/200 | 4.2% | 0.72 | 0/200 | 40 | contact_share 124, reward_vs_dist 22 |
