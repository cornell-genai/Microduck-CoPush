# Policy comparison on experiments/test_sets/stage1_large.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| reference | 68% (136/200) | 65/67 | 59/67 | 12/66 |
| n1_a | 84% (168/200) | 64/67 | 55/67 | 49/66 |
| n1_b | 77% (154/200) | 60/67 | 57/67 | 37/66 |
| a_s1 | 94% (189/200) | 66/67 | 64/67 | 59/66 |
| a_s2 | 96% (192/200) | 67/67 | 65/67 | 60/66 |
| b_s1 | 88% (176/200) | 62/67 | 63/67 | 51/66 |
| b_s2 | 87% (174/200) | 66/67 | 56/67 | 52/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| reference | 57 | 60 (11 to 264) | 152 | 60/66 | 12/66 |
| n1_a | 57 | 46 (32 to 66) | 37 | 66/66 | 49/66 |
| n1_b | 57 | 55 (27 to 71) | 37 | 66/66 | 37/66 |
| a_s1 | 57 | 45 (31 to 69) | 34 | 66/66 | 59/66 |
| a_s2 | 57 | 48 (32 to 73) | 39 | 66/66 | 60/66 |
| b_s1 | 57 | 48 (39 to 69) | 39 | 66/66 | 51/66 |
| b_s2 | 57 | 52 (38 to 69) | 40 | 66/66 | 52/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 19/200 | 8/200 | 21/200 | 37/200 | 49% | 87% | 2/200 | 14.8% | 1.13 | 1/200 | 61 | bad_part_duck_a 31, bad_part_duck_b 15, contact_share 70, edge 3, fall_duck_a 27, fall_duck_b 8, reward_vs_dist 27 |
| n1_a | 1/200 | 1/200 | 0/200 | 30/200 | 64% | 48% | 80/200 | 12.4% | 0.71 | 0/200 | 54 | bad_part_duck_a 4, bad_part_duck_b 2, contact_share 163, edge 1, fall_duck_a 3, fall_duck_b 1, reward_vs_dist 17 |
| n1_b | 1/200 | 0/200 | 6/200 | 45/200 | 64% | 56% | 66/200 | 13.1% | 0.79 | 0/200 | 63 | bad_part_duck_a 6, bad_part_duck_b 2, contact_share 130, edge 3, fall_duck_a 3, reward_vs_dist 23, spin 1 |
| a_s1 | 1/200 | 0/200 | 0/200 | 10/200 | 64% | 52% | 81/200 | 5.0% | 0.72 | 0/200 | 42 | bad_part_duck_a 1, bad_part_duck_b 1, contact_share 148, fall_duck_a 1, reward_vs_dist 11 |
| a_s2 | 1/200 | 0/200 | 0/200 | 7/200 | 71% | 56% | 84/200 | 4.8% | 0.73 | 0/200 | 42 | contact_share 121, fall_duck_a 1, reward_vs_dist 23 |
| b_s1 | 2/200 | 0/200 | 0/200 | 22/200 | 67% | 54% | 82/200 | 9.5% | 0.73 | 0/200 | 49 | bad_part_duck_a 2, contact_share 119, edge 1, fall_duck_a 2, reward_vs_dist 14 |
| b_s2 | 2/200 | 1/200 | 0/200 | 23/200 | 74% | 55% | 85/200 | 10.9% | 0.72 | 0/200 | 49 | bad_part_duck_a 1, bad_part_duck_b 2, contact_share 130, fall_duck_a 1, fall_duck_b 2, reward_vs_dist 22 |
