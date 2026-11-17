# Policy comparison on experiments/test_sets/stage1_noisy_large.json

One deterministic episode per start, env from `experiments/d2-steering/noisy-sets/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| reference | 62% (125/200) | 60/66 | 56/67 | 9/67 |
| a_s1 | 96% (192/200) | 66/66 | 61/67 | 65/67 |
| a_s2 | 95% (190/200) | 64/66 | 64/67 | 62/67 |
| e_s1 | 74% (149/200) | 53/66 | 49/67 | 47/67 |
| e_s2 | 64% (127/200) | 40/66 | 40/67 | 47/67 |
| e_s1_smp1 | 76% (152/200) | 53/66 | 48/67 | 51/67 |
| e_s1_smp2 | 80% (159/200) | 58/66 | 50/67 | 51/67 |
| e_s1_smp3 | 78% (156/200) | 56/66 | 49/67 | 51/67 |
| e_s2_smp1 | 74% (148/200) | 47/66 | 48/67 | 53/67 |
| e_s2_smp2 | 74% (148/200) | 51/66 | 47/67 | 50/67 |
| e_s2_smp3 | 74% (147/200) | 51/66 | 47/67 | 49/67 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| reference | 56 | 54 (17 to 213) | 132 | 59/67 | 9/67 |
| a_s1 | 56 | 44 (24 to 64) | 34 | 67/67 | 65/67 |
| a_s2 | 56 | 48 (30 to 77) | 39 | 67/67 | 62/67 |
| e_s1 | 56 | 52 (39 to 97) | 45 | 67/67 | 47/67 |
| e_s2 | 56 | 43 (22 to 65) | 41 | 67/67 | 47/67 |
| e_s1_smp1 | 56 | 48 (33 to 73) | 51 | 67/67 | 51/67 |
| e_s1_smp2 | 56 | 51 (36 to 67) | 45 | 67/67 | 51/67 |
| e_s1_smp3 | 56 | 50 (31 to 96) | 42 | 67/67 | 51/67 |
| e_s2_smp1 | 56 | 44 (23 to 69) | 38 | 67/67 | 53/67 |
| e_s2_smp2 | 56 | 43 (27 to 62) | 39 | 67/67 | 50/67 |
| e_s2_smp3 | 56 | 43 (24 to 61) | 42 | 67/67 | 49/67 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 13/200 | 3/200 | 23/200 | 59/200 | 51% | 89% | 0/200 | 15.6% | 1.08 | 0/200 | 56 | bad_part_duck_a 26, bad_part_duck_b 9, contact_share 95, fall_duck_a 22, fall_duck_b 5, reward_vs_dist 28 |
| a_s1 | 0/200 | 1/200 | 0/200 | 7/200 | 65% | 49% | 84/200 | 3.5% | 0.72 | 0/200 | 40 | bad_part_duck_a 2, contact_share 137, edge 2, fall_duck_a 1, reward_vs_dist 6 |
| a_s2 | 0/200 | 0/200 | 0/200 | 10/200 | 71% | 53% | 87/200 | 4.0% | 0.73 | 0/200 | 41 | contact_share 106, edge 1, reward_vs_dist 20 |
| e_s1 | 2/200 | 1/200 | 2/200 | 48/200 | 69% | 41% | 82/200 | 14.6% | 0.73 | 0/200 | 53 | bad_part_duck_a 2, bad_part_duck_b 5, contact_share 165, edge 3, fall_duck_a 2, fall_duck_b 2, reward_vs_dist 20, spin 1 |
| e_s2 | 6/200 | 1/200 | 4/200 | 66/200 | 73% | 30% | 97/200 | 20.6% | 0.69 | 0/200 | 59 | bad_part_duck_a 5, bad_part_duck_b 6, contact_share 179, edge 3, fall_duck_a 7, fall_duck_b 3, reward_vs_dist 8 |
| e_s1_smp1 | 6/200 | 0/200 | 5/200 | 42/200 | 70% | 41% | 85/200 | 11.7% | 0.75 | 0/200 | 52 | bad_part_duck_a 3, bad_part_duck_b 3, contact_share 159, edge 2, fall_duck_a 4, fall_duck_b 4, reward_vs_dist 12 |
| e_s1_smp2 | 2/200 | 0/200 | 2/200 | 39/200 | 69% | 44% | 78/200 | 10.9% | 0.74 | 0/200 | 51 | bad_part_duck_a 5, bad_part_duck_b 4, contact_share 157, edge 1, fall_duck_a 4, fall_duck_b 3, reward_vs_dist 11, spin 1 |
| e_s1_smp3 | 2/200 | 1/200 | 1/200 | 41/200 | 70% | 42% | 79/200 | 12.7% | 0.72 | 0/200 | 51 | bad_part_duck_a 4, bad_part_duck_b 2, contact_share 159, fall_duck_a 2, fall_duck_b 2, reward_vs_dist 16, spin 2 |
| e_s2_smp1 | 2/200 | 0/200 | 2/200 | 50/200 | 73% | 29% | 106/200 | 18.0% | 0.69 | 0/200 | 57 | bad_part_duck_a 3, bad_part_duck_b 2, contact_share 172, edge 3, fall_duck_a 2, fall_duck_b 2, reward_vs_dist 13 |
| e_s2_smp2 | 2/200 | 1/200 | 3/200 | 49/200 | 73% | 31% | 103/200 | 18.4% | 0.68 | 0/200 | 55 | bad_part_duck_a 3, bad_part_duck_b 2, contact_share 176, edge 1, fall_duck_a 2, reward_vs_dist 8 |
| e_s2_smp3 | 2/200 | 0/200 | 5/200 | 51/200 | 73% | 30% | 101/200 | 17.8% | 0.70 | 0/200 | 56 | bad_part_duck_a 4, bad_part_duck_b 2, contact_share 174, edge 1, fall_duck_a 4, fall_duck_b 2, reward_vs_dist 8 |
