# Policy comparison on experiments/test_sets/stage1_noisy_large.json

One deterministic episode per start, env from `experiments/d2-steering/noisy-sets/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| reference | 64% (127/200) | 60/66 | 56/67 | 11/67 |
| n1_a | 80% (160/200) | 59/66 | 50/67 | 51/67 |
| n1_b | 82% (164/200) | 62/66 | 56/67 | 46/67 |
| a_s1 | 96% (192/200) | 66/66 | 61/67 | 65/67 |
| a_s2 | 95% (190/200) | 64/66 | 64/67 | 62/67 |
| b_s1 | 89% (178/200) | 62/66 | 62/67 | 54/67 |
| b_s2 | 88% (176/200) | 65/66 | 57/67 | 54/67 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| reference | 56 | 54 (-115 to 220) | 171 | 62/67 | 11/67 |
| n1_a | 56 | 44 (27 to 68) | 34 | 67/67 | 51/67 |
| n1_b | 56 | 54 (27 to 70) | 40 | 66/67 | 46/67 |
| a_s1 | 56 | 44 (24 to 64) | 34 | 67/67 | 65/67 |
| a_s2 | 56 | 48 (30 to 77) | 39 | 67/67 | 62/67 |
| b_s1 | 56 | 45 (28 to 68) | 37 | 67/67 | 54/67 |
| b_s2 | 56 | 52 (35 to 72) | 44 | 67/67 | 54/67 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 15/200 | 3/200 | 32/200 | 55/200 | 50% | 85% | 2/200 | 15.1% | 1.32 | 0/200 | 71 | bad_part_duck_a 30, bad_part_duck_b 10, contact_share 101, fall_duck_a 25, fall_duck_b 5, reward_vs_dist 37 |
| n1_a | 5/200 | 1/200 | 0/200 | 34/200 | 66% | 45% | 87/200 | 12.2% | 0.72 | 0/200 | 58 | bad_part_duck_a 4, bad_part_duck_b 3, contact_share 152, edge 1, fall_duck_a 4, fall_duck_b 3, reward_vs_dist 8 |
| n1_b | 4/200 | 1/200 | 1/200 | 31/200 | 65% | 56% | 67/200 | 8.7% | 0.75 | 0/200 | 57 | bad_part_duck_a 1, bad_part_duck_b 3, contact_share 134, edge 3, fall_duck_a 1, fall_duck_b 4, reward_vs_dist 23 |
| a_s1 | 0/200 | 1/200 | 0/200 | 7/200 | 65% | 48% | 84/200 | 3.9% | 0.72 | 0/200 | 41 | bad_part_duck_a 2, contact_share 137, edge 2, fall_duck_a 1, reward_vs_dist 6 |
| a_s2 | 0/200 | 0/200 | 0/200 | 10/200 | 71% | 52% | 87/200 | 4.7% | 0.73 | 0/200 | 44 | contact_share 106, edge 1, reward_vs_dist 20 |
| b_s1 | 1/200 | 0/200 | 0/200 | 21/200 | 68% | 50% | 89/200 | 9.0% | 0.73 | 0/200 | 50 | bad_part_duck_a 1, contact_share 121, edge 1, fall_duck_a 1, reward_vs_dist 9 |
| b_s2 | 2/200 | 0/200 | 1/200 | 22/200 | 75% | 51% | 88/200 | 10.3% | 0.73 | 0/200 | 49 | bad_part_duck_a 3, bad_part_duck_b 3, contact_share 111, fall_duck_a 1, fall_duck_b 2, reward_vs_dist 16 |
