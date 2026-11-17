# Policy comparison on experiments/test_sets/stage1_large.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| reference | 66% (133/200) | 65/67 | 58/67 | 10/66 |
| a_s1 | 94% (189/200) | 66/67 | 64/67 | 59/66 |
| a_s2 | 96% (192/200) | 67/67 | 65/67 | 60/66 |
| e_s1 | 76% (153/200) | 58/67 | 50/67 | 45/66 |
| e_s2 | 80% (159/200) | 56/67 | 47/67 | 56/66 |
| e_s1_smp1 | 70% (140/200) | 53/67 | 43/67 | 44/66 |
| e_s1_smp2 | 78% (156/200) | 55/67 | 53/67 | 48/66 |
| e_s1_smp3 | 80% (160/200) | 62/67 | 52/67 | 46/66 |
| e_s2_smp1 | 68% (136/200) | 45/67 | 37/67 | 54/66 |
| e_s2_smp2 | 78% (155/200) | 55/67 | 48/67 | 52/66 |
| e_s2_smp3 | 77% (154/200) | 54/67 | 47/67 | 53/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| reference | 57 | 57 (11 to 225) | 123 | 60/66 | 10/66 |
| a_s1 | 57 | 45 (31 to 69) | 34 | 66/66 | 59/66 |
| a_s2 | 57 | 48 (32 to 73) | 39 | 66/66 | 60/66 |
| e_s1 | 57 | 51 (30 to 84) | 48 | 66/66 | 45/66 |
| e_s2 | 57 | 46 (26 to 67) | 35 | 66/66 | 56/66 |
| e_s1_smp1 | 57 | 52 (39 to 71) | 44 | 66/66 | 44/66 |
| e_s1_smp2 | 57 | 51 (33 to 74) | 45 | 66/66 | 48/66 |
| e_s1_smp3 | 57 | 52 (29 to 78) | 42 | 65/66 | 46/66 |
| e_s2_smp1 | 57 | 46 (27 to 63) | 34 | 66/66 | 54/66 |
| e_s2_smp2 | 57 | 46 (29 to 68) | 36 | 66/66 | 52/66 |
| e_s2_smp3 | 57 | 46 (29 to 64) | 37 | 66/66 | 53/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 16/200 | 8/200 | 18/200 | 43/200 | 49% | 89% | 1/200 | 14.7% | 0.97 | 0/200 | 51 | bad_part_duck_a 29, bad_part_duck_b 15, contact_share 69, edge 2, fall_duck_a 23, fall_duck_b 8, reward_vs_dist 17 |
| a_s1 | 1/200 | 0/200 | 0/200 | 10/200 | 64% | 52% | 81/200 | 4.3% | 0.72 | 0/200 | 40 | bad_part_duck_a 1, bad_part_duck_b 1, contact_share 148, fall_duck_a 1, reward_vs_dist 11 |
| a_s2 | 1/200 | 0/200 | 0/200 | 7/200 | 71% | 56% | 84/200 | 4.3% | 0.73 | 0/200 | 40 | contact_share 121, fall_duck_a 1, reward_vs_dist 23 |
| e_s1 | 3/200 | 1/200 | 0/200 | 43/200 | 68% | 46% | 73/200 | 13.6% | 0.72 | 0/200 | 50 | bad_part_duck_a 3, bad_part_duck_b 3, contact_share 161, edge 2, fall_duck_b 3, reward_vs_dist 17 |
| e_s2 | 1/200 | 0/200 | 1/200 | 40/200 | 72% | 34% | 95/200 | 15.1% | 0.68 | 0/200 | 51 | bad_part_duck_a 3, bad_part_duck_b 2, contact_share 175, edge 3, fall_duck_a 1, fall_duck_b 1, reward_vs_dist 11 |
| e_s1_smp1 | 5/200 | 0/200 | 1/200 | 55/200 | 69% | 43% | 79/200 | 16.3% | 0.73 | 0/200 | 54 | bad_part_duck_a 4, bad_part_duck_b 6, contact_share 153, edge 2, fall_duck_a 5, fall_duck_b 1, reward_vs_dist 18 |
| e_s1_smp2 | 4/200 | 1/200 | 0/200 | 39/200 | 67% | 44% | 74/200 | 13.1% | 0.73 | 0/200 | 50 | bad_part_duck_a 2, bad_part_duck_b 2, contact_share 167, edge 2, fall_duck_a 3, fall_duck_b 3, reward_vs_dist 22 |
| e_s1_smp3 | 2/200 | 1/200 | 0/200 | 37/200 | 68% | 47% | 73/200 | 12.8% | 0.72 | 0/200 | 49 | bad_part_duck_a 2, bad_part_duck_b 4, contact_share 166, edge 1, fall_duck_a 1, fall_duck_b 3, reward_vs_dist 15 |
| e_s2_smp1 | 2/200 | 1/200 | 2/200 | 61/200 | 73% | 29% | 103/200 | 21.6% | 0.68 | 0/200 | 58 | bad_part_duck_a 4, bad_part_duck_b 2, contact_share 179, edge 1, fall_duck_a 3, fall_duck_b 1, reward_vs_dist 8 |
| e_s2_smp2 | 1/200 | 0/200 | 1/200 | 44/200 | 72% | 33% | 94/200 | 18.7% | 0.68 | 0/200 | 53 | bad_part_duck_a 3, bad_part_duck_b 2, contact_share 171, edge 3, fall_duck_a 1, reward_vs_dist 10 |
| e_s2_smp3 | 3/200 | 1/200 | 1/200 | 42/200 | 72% | 32% | 96/200 | 18.6% | 0.68 | 0/200 | 52 | bad_part_duck_a 3, bad_part_duck_b 3, contact_share 176, edge 1, fall_duck_a 4, fall_duck_b 2, reward_vs_dist 10 |
