# Policy comparison on experiments/test_sets/stage1_noisy_large.json

One deterministic episode per start, env from `experiments/d2-steering/noisy-sets/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| a_s1 | 96% (192/200) | 66/66 | 61/67 | 65/67 |
| a_s2 | 95% (190/200) | 64/66 | 64/67 | 62/67 |
| a_s1_smp1 | 92% (183/200) | 62/66 | 62/67 | 59/67 |
| a_s1_smp2 | 90% (181/200) | 64/66 | 58/67 | 59/67 |
| a_s1_smp3 | 92% (184/200) | 66/66 | 58/67 | 60/67 |
| a_s2_smp1 | 96% (192/200) | 64/66 | 63/67 | 65/67 |
| a_s2_smp2 | 94% (187/200) | 65/66 | 59/67 | 63/67 |
| a_s2_smp3 | 98% (197/200) | 64/66 | 66/67 | 67/67 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| a_s1 | 56 | 44 (24 to 64) | 34 | 67/67 | 65/67 |
| a_s2 | 56 | 48 (30 to 77) | 39 | 67/67 | 62/67 |
| a_s1_smp1 | 56 | 44 (14 to 85) | 36 | 67/67 | 59/67 |
| a_s1_smp2 | 56 | 46 (24 to 62) | 36 | 67/67 | 59/67 |
| a_s1_smp3 | 56 | 45 (24 to 70) | 36 | 67/67 | 60/67 |
| a_s2_smp1 | 56 | 49 (29 to 75) | 39 | 67/67 | 65/67 |
| a_s2_smp2 | 56 | 49 (25 to 79) | 40 | 67/67 | 63/67 |
| a_s2_smp3 | 56 | 48 (35 to 75) | 39 | 67/67 | 67/67 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a_s1 | 0/200 | 1/200 | 0/200 | 7/200 | 65% | 49% | 84/200 | 3.5% | 0.72 | 0/200 | 40 | bad_part_duck_a 2, contact_share 137, edge 2, fall_duck_a 1, reward_vs_dist 6 |
| a_s2 | 0/200 | 0/200 | 0/200 | 10/200 | 71% | 53% | 87/200 | 4.0% | 0.73 | 0/200 | 41 | contact_share 106, edge 1, reward_vs_dist 20 |
| a_s1_smp1 | 0/200 | 3/200 | 0/200 | 14/200 | 65% | 47% | 85/200 | 4.6% | 0.71 | 0/200 | 42 | bad_part_duck_a 2, bad_part_duck_b 2, contact_share 151, edge 2, fall_duck_a 1, reward_vs_dist 9 |
| a_s1_smp2 | 1/200 | 0/200 | 0/200 | 18/200 | 65% | 48% | 83/200 | 6.3% | 0.72 | 0/200 | 44 | bad_part_duck_a 4, bad_part_duck_b 3, contact_share 145, edge 1, fall_duck_a 3, fall_duck_b 1, reward_vs_dist 18 |
| a_s1_smp3 | 1/200 | 0/200 | 0/200 | 15/200 | 64% | 48% | 84/200 | 4.9% | 0.72 | 0/200 | 43 | bad_part_duck_a 2, bad_part_duck_b 3, contact_share 147, edge 1, fall_duck_b 1, reward_vs_dist 12 |
| a_s2_smp1 | 1/200 | 0/200 | 0/200 | 7/200 | 71% | 51% | 88/200 | 4.1% | 0.73 | 0/200 | 41 | contact_share 112, edge 1, fall_duck_a 1, reward_vs_dist 15 |
| a_s2_smp2 | 0/200 | 0/200 | 0/200 | 13/200 | 70% | 52% | 86/200 | 5.3% | 0.73 | 0/200 | 43 | contact_share 114, reward_vs_dist 20 |
| a_s2_smp3 | 0/200 | 0/200 | 0/200 | 3/200 | 70% | 52% | 86/200 | 3.8% | 0.73 | 0/200 | 40 | bad_part_duck_b 1, contact_share 114, edge 1, fall_duck_b 1, reward_vs_dist 20 |
