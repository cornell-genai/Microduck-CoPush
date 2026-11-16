# Policy comparison on experiments/test_sets/stage1_large.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| stage1_central | 58% (116/200) | 54/67 | 59/67 | 3/66 |
| central_scratch_s1 | 50% (101/200) | 43/67 | 54/67 | 4/66 |
| stage1b_A | 70% (141/200) | 66/67 | 61/67 | 14/66 |
| stage1b_B | 65% (130/200) | 62/67 | 60/67 | 8/66 |
| d1 | 64% (128/200) | 64/67 | 58/67 | 6/66 |
| d2 | 66% (133/200) | 65/67 | 58/67 | 10/66 |
| d2_distilled_s1 | 51% (102/200) | 42/67 | 55/67 | 5/66 |
| d2_distilled_s2 | 49% (98/200) | 35/67 | 56/67 | 7/66 |
| d2_distilled_s3 | 54% (109/200) | 48/67 | 57/67 | 4/66 |
| central_scratch_s2 | 34% (68/200) | 28/67 | 40/67 | 0/66 |
| central_scratch_s3 | 54% (107/200) | 47/67 | 51/67 | 9/66 |
| central_scratch_s4 | 42% (85/200) | 36/67 | 49/67 | 0/66 |
| central_scratch_s5 | 34% (68/200) | 16/67 | 51/67 | 1/66 |
| central_scratch_s6 | 47% (94/200) | 44/67 | 49/67 | 1/66 |
| central_scratch_s7 | 52% (105/200) | 55/67 | 50/67 | 0/66 |
| central_scratch_s8 | 48% (95/200) | 45/67 | 49/67 | 1/66 |
| central_scratch_s9 | 54% (109/200) | 48/67 | 54/67 | 7/66 |
| central_scratch_s10 | 38% (75/200) | 22/67 | 52/67 | 1/66 |
| d2_scratch_s1 | 32% (65/200) | 20/67 | 39/67 | 6/66 |
| d2_scratch_s2 | 28% (57/200) | 11/67 | 41/67 | 5/66 |
| d2_scratch_s3 | 28% (56/200) | 11/67 | 43/67 | 2/66 |
| d2_scratch_s4 | 56% (112/200) | 55/67 | 53/67 | 4/66 |
| d2_scratch_s5 | 38% (76/200) | 20/67 | 44/67 | 12/66 |
| d2_scratch_s6 | 54% (108/200) | 50/67 | 52/67 | 6/66 |
| d2_scratch_s7 | 40% (81/200) | 19/67 | 54/67 | 8/66 |
| d2_scratch_s8 | 37% (74/200) | 20/67 | 46/67 | 8/66 |
| d2_scratch_s9 | 36% (71/200) | 16/67 | 50/67 | 5/66 |
| d2_scratch_s10 | 51% (102/200) | 52/67 | 49/67 | 1/66 |
| pivot_push | 38% (77/200) | 31/67 | 30/67 | 16/66 |
| push_steer | 20% (40/200) | 38/67 | 2/67 | 0/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| stage1_central | 57 | 40 (-33 to 115) | 42 | 51/66 | 3/66 |
| central_scratch_s1 | 57 | 25 (-37 to 64) | 16 | 35/66 | 4/66 |
| stage1b_A | 57 | 36 (-73 to 121) | 40 | 56/66 | 14/66 |
| stage1b_B | 57 | 33 (-72 to 111) | 41 | 56/66 | 8/66 |
| d1 | 57 | 80 (15 to 236) | 177 | 56/66 | 6/66 |
| d2 | 57 | 57 (11 to 225) | 123 | 60/66 | 10/66 |
| d2_distilled_s1 | 57 | 33 (-38 to 97) | 23 | 47/66 | 5/66 |
| d2_distilled_s2 | 57 | 37 (-41 to 110) | 44 | 50/66 | 7/66 |
| d2_distilled_s3 | 57 | 43 (-41 to 114) | 34 | 46/66 | 4/66 |
| central_scratch_s2 | 57 | -0 (-74 to 151) | 3 | 20/66 | 0/66 |
| central_scratch_s3 | 57 | 26 (-57 to 55) | 19 | 47/66 | 9/66 |
| central_scratch_s4 | 57 | 41 (3 to 112) | 50 | 38/66 | 0/66 |
| central_scratch_s5 | 57 | 23 (-14 to 53) | 5 | 44/66 | 1/66 |
| central_scratch_s6 | 57 | 19 (-108 to 135) | 16 | 24/66 | 1/66 |
| central_scratch_s7 | 57 | -1 (-128 to 121) | -4 | 23/66 | 0/66 |
| central_scratch_s8 | 57 | 11 (-138 to 150) | 9 | 22/66 | 1/66 |
| central_scratch_s9 | 57 | 32 (11 to 94) | 32 | 48/66 | 7/66 |
| central_scratch_s10 | 57 | 34 (-3 to 108) | 38 | 46/66 | 1/66 |
| d2_scratch_s1 | 57 | 53 (-23 to 216) | 57 | 46/66 | 6/66 |
| d2_scratch_s2 | 57 | 68 (15 to 187) | 136 | 58/66 | 5/66 |
| d2_scratch_s3 | 57 | 66 (13 to 181) | 132 | 51/66 | 2/66 |
| d2_scratch_s4 | 57 | 46 (12 to 142) | 57 | 42/66 | 4/66 |
| d2_scratch_s5 | 57 | 78 (15 to 190) | 140 | 55/66 | 12/66 |
| d2_scratch_s6 | 57 | 57 (5 to 212) | 71 | 44/66 | 6/66 |
| d2_scratch_s7 | 57 | 80 (-35 to 199) | 140 | 50/66 | 8/66 |
| d2_scratch_s8 | 57 | 81 (16 to 218) | 151 | 55/66 | 8/66 |
| d2_scratch_s9 | 57 | 63 (-42 to 190) | 126 | 52/66 | 5/66 |
| d2_scratch_s10 | 57 | 64 (-12 to 202) | 74 | 28/66 | 1/66 |
| pivot_push | 57 | 52 (33 to 70) | 67 | 66/66 | 16/66 |
| push_steer | 57 | 81 (14 to 155) | 83 | 23/66 | 0/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stage1_central | 13/200 | 3/200 | 59/200 | 68/200 | 46% | 87% | 6/200 | 13.9% | 1.15 | 0/200 | 60 | bad_part_duck_a 23, bad_part_duck_b 7, contact_share 74, fall_duck_a 26, fall_duck_b 1, reward_vs_dist 9 |
| central_scratch_s1 | 1/200 | 1/200 | 97/200 | 97/200 | 50% | 98% | 0/200 | 1.2% | 1.38 | 0/200 | 65 | contact_share 1, fall_duck_a 1, reward_vs_dist 9 |
| stage1b_A | 9/200 | 1/200 | 48/200 | 49/200 | 52% | 93% | 0/200 | 9.3% | 1.06 | 0/200 | 52 | bad_part_duck_a 17, bad_part_duck_b 8, contact_share 33, fall_duck_a 14, fall_duck_b 3, reward_vs_dist 7 |
| stage1b_B | 11/200 | 3/200 | 54/200 | 56/200 | 49% | 88% | 4/200 | 16.2% | 1.09 | 0/200 | 55 | bad_part_duck_a 27, bad_part_duck_b 12, contact_share 71, fall_duck_a 17, fall_duck_b 6, reward_vs_dist 12, spin 1 |
| d1 | 8/200 | 3/200 | 25/200 | 61/200 | 47% | 93% | 0/200 | 21.3% | 1.12 | 0/200 | 57 | bad_part_duck_a 18, bad_part_duck_b 5, contact_share 53, fall_duck_a 13, fall_duck_b 4, reward_vs_dist 31 |
| d2 | 16/200 | 8/200 | 18/200 | 43/200 | 49% | 89% | 1/200 | 14.7% | 0.97 | 0/200 | 51 | bad_part_duck_a 29, bad_part_duck_b 15, contact_share 69, edge 2, fall_duck_a 23, fall_duck_b 8, reward_vs_dist 17 |
| d2_distilled_s1 | 5/200 | 1/200 | 89/200 | 92/200 | 50% | 95% | 0/200 | 13.4% | 1.35 | 0/200 | 65 | bad_part_duck_a 11, bad_part_duck_b 5, contact_share 38, fall_duck_a 11, reward_vs_dist 27 |
| d2_distilled_s2 | 9/200 | 1/200 | 97/200 | 92/200 | 51% | 94% | 0/200 | 1.2% | 1.48 | 0/200 | 66 | bad_part_duck_a 18, bad_part_duck_b 3, contact_share 44, fall_duck_a 20, fall_duck_b 1, reward_vs_dist 9 |
| d2_distilled_s3 | 5/200 | 2/200 | 80/200 | 84/200 | 50% | 90% | 1/200 | 9.8% | 1.31 | 0/200 | 61 | bad_part_duck_a 29, bad_part_duck_b 3, contact_share 49, edge 1, fall_duck_a 17, reward_vs_dist 14, spin 1 |
| central_scratch_s2 | 12/200 | 8/200 | 103/200 | 112/200 | 54% | 85% | 15/200 | 11.8% | 1.36 | 0/200 | 75 | bad_part_duck_a 20, bad_part_duck_b 30, contact_share 112, edge 2, fall_duck_a 9, fall_duck_b 16, reward_vs_dist 11 |
| central_scratch_s3 | 1/200 | 0/200 | 93/200 | 92/200 | 53% | 97% | 0/200 | 0.0% | 1.36 | 0/200 | 64 | bad_part_duck_a 1, contact_share 21, fall_duck_a 1, reward_vs_dist 12 |
| central_scratch_s4 | 4/200 | 1/200 | 92/200 | 110/200 | 54% | 91% | 0/200 | 43.2% | 1.26 | 0/200 | 74 | bad_part_duck_a 2, bad_part_duck_b 3, contact_share 84, edge 3, fall_duck_a 2, fall_duck_b 3, reward_vs_dist 18 |
| central_scratch_s5 | 2/200 | 1/200 | 130/200 | 129/200 | 53% | 96% | 0/200 | 4.5% | 1.60 | 0/200 | 77 | bad_part_duck_a 5, contact_share 32, fall_duck_a 4, reward_vs_dist 41 |
| central_scratch_s6 | 9/200 | 18/200 | 89/200 | 79/200 | 51% | 95% | 0/200 | 0.1% | 1.37 | 0/200 | 62 | bad_part_duck_a 8, bad_part_duck_b 17, contact_share 52, fall_duck_a 10, fall_duck_b 7, reward_vs_dist 3 |
| central_scratch_s7 | 15/200 | 4/200 | 76/200 | 76/200 | 54% | 88% | 15/200 | 0.0% | 1.21 | 0/200 | 60 | bad_part_duck_a 16, bad_part_duck_b 29, contact_share 90, fall_duck_a 8, fall_duck_b 12, reward_vs_dist 4, spin 1 |
| central_scratch_s8 | 17/200 | 9/200 | 92/200 | 79/200 | 52% | 92% | 4/200 | 0.3% | 1.32 | 0/200 | 62 | bad_part_duck_a 13, bad_part_duck_b 24, contact_share 80, edge 1, fall_duck_a 10, fall_duck_b 13, reward_vs_dist 7 |
| central_scratch_s9 | 3/200 | 0/200 | 87/200 | 88/200 | 51% | 97% | 1/200 | 28.3% | 1.25 | 0/200 | 64 | bad_part_duck_a 4, bad_part_duck_b 2, contact_share 48, edge 1, fall_duck_a 5, reward_vs_dist 4 |
| central_scratch_s10 | 1/200 | 0/200 | 122/200 | 124/200 | 52% | 97% | 0/200 | 5.7% | 1.53 | 0/200 | 74 | bad_part_duck_a 1, contact_share 28, edge 2, fall_duck_b 1, reward_vs_dist 19 |
| d2_scratch_s1 | 7/200 | 3/200 | 116/200 | 125/200 | 56% | 92% | 1/200 | 43.1% | 1.54 | 0/200 | 78 | bad_part_duck_a 16, bad_part_duck_b 13, contact_share 63, edge 2, fall_duck_a 4, fall_duck_b 9, reward_vs_dist 28 |
| d2_scratch_s2 | 21/200 | 1/200 | 92/200 | 121/200 | 53% | 92% | 0/200 | 27.2% | 1.59 | 0/200 | 78 | bad_part_duck_a 29, bad_part_duck_b 12, contact_share 59, edge 4, fall_duck_a 23, fall_duck_b 10, reward_vs_dist 44, spin 1 |
| d2_scratch_s3 | 10/200 | 2/200 | 121/200 | 132/200 | 56% | 93% | 0/200 | 36.7% | 1.62 | 0/200 | 80 | bad_part_duck_a 26, bad_part_duck_b 7, contact_share 52, edge 4, fall_duck_a 18, fall_duck_b 1, reward_vs_dist 24, spin 1 |
| d2_scratch_s4 | 3/200 | 0/200 | 85/200 | 85/200 | 52% | 98% | 0/200 | 18.1% | 1.30 | 0/200 | 62 | bad_part_duck_a 12, bad_part_duck_b 3, contact_share 21, fall_duck_a 4, fall_duck_b 1, reward_vs_dist 13 |
| d2_scratch_s5 | 13/200 | 2/200 | 86/200 | 109/200 | 50% | 91% | 0/200 | 46.1% | 1.46 | 0/200 | 75 | bad_part_duck_a 37, bad_part_duck_b 7, contact_share 89, edge 3, fall_duck_a 30, fall_duck_b 5, reward_vs_dist 18, spin 1 |
| d2_scratch_s6 | 10/200 | 0/200 | 79/200 | 82/200 | 52% | 95% | 0/200 | 19.5% | 1.30 | 0/200 | 63 | bad_part_duck_a 22, bad_part_duck_b 4, contact_share 45, fall_duck_a 15, fall_duck_b 2, reward_vs_dist 17 |
| d2_scratch_s7 | 12/200 | 1/200 | 70/200 | 106/200 | 51% | 93% | 0/200 | 25.7% | 1.45 | 0/200 | 70 | bad_part_duck_a 20, bad_part_duck_b 8, contact_share 52, fall_duck_a 15, fall_duck_b 4, reward_vs_dist 21 |
| d2_scratch_s8 | 9/200 | 1/200 | 72/200 | 116/200 | 49% | 94% | 0/200 | 45.9% | 1.41 | 0/200 | 76 | bad_part_duck_a 21, bad_part_duck_b 2, contact_share 107, edge 1, fall_duck_a 14, fall_duck_b 2, reward_vs_dist 27 |
| d2_scratch_s9 | 11/200 | 2/200 | 116/200 | 116/200 | 54% | 93% | 0/200 | 12.2% | 1.63 | 0/200 | 74 | bad_part_duck_a 24, bad_part_duck_b 8, contact_share 44, edge 1, fall_duck_a 18, fall_duck_b 6, reward_vs_dist 22 |
| d2_scratch_s10 | 2/200 | 1/200 | 89/200 | 95/200 | 51% | 97% | 0/200 | 17.7% | 1.32 | 0/200 | 67 | bad_part_duck_a 7, bad_part_duck_b 3, contact_share 22, fall_duck_a 8, fall_duck_b 1, reward_vs_dist 12 |
| pivot_push | 29/200 | 2/200 | 59/200 | 92/200 | 64% | 53% | 37/200 | 4.6% | 1.10 | 0/200 | 70 | bad_part_duck_a 30, bad_part_duck_b 13, contact_share 176, edge 2, fall_duck_a 21, fall_duck_b 15, reward_vs_dist 37, spin 2 |
| push_steer | 34/200 | 3/200 | 111/200 | 123/200 | 48% | 82% | 5/200 | 2.8% | 1.64 | 0/200 | 78 | bad_part_duck_a 47, bad_part_duck_b 5, contact_share 87, edge 2, fall_duck_a 47, fall_duck_b 6, reward_vs_dist 35, spin 3 |
