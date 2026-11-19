# Policy comparison on experiments/test_sets/stage1_large.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| a_s1 | 94% (189/200) | 66/67 | 64/67 | 59/66 |
| a_s2 | 96% (192/200) | 67/67 | 65/67 | 60/66 |
| l1_s1 | 95% (190/200) | 66/67 | 63/67 | 61/66 |
| l2_s1 | 92% (185/200) | 67/67 | 61/67 | 57/66 |
| l1_s2 | 97% (194/200) | 66/67 | 67/67 | 61/66 |
| l2_s2 | 98% (195/200) | 66/67 | 66/67 | 63/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| a_s1 | 57 | 45 (31 to 69) | 34 | 66/66 | 59/66 |
| a_s2 | 57 | 48 (32 to 73) | 39 | 66/66 | 60/66 |
| l1_s1 | 57 | 44 (19 to 63) | 34 | 66/66 | 61/66 |
| l2_s1 | 57 | 49 (27 to 75) | 36 | 66/66 | 57/66 |
| l1_s2 | 57 | 41 (21 to 70) | 34 | 66/66 | 61/66 |
| l2_s2 | 57 | 45 (23 to 71) | 35 | 66/66 | 63/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a_s1 | 1/200 | 0/200 | 0/200 | 10/200 | 64% | 52% | 81/200 | 4.3% | 0.72 | 0/200 | 40 | bad_part_duck_a 1, bad_part_duck_b 1, contact_share 148, fall_duck_a 1, reward_vs_dist 11 |
| a_s2 | 1/200 | 0/200 | 0/200 | 7/200 | 71% | 56% | 84/200 | 4.3% | 0.73 | 0/200 | 40 | contact_share 121, fall_duck_a 1, reward_vs_dist 23 |
| l1_s1 | 2/200 | 0/200 | 0/200 | 8/200 | 68% | 49% | 86/200 | 4.3% | 0.72 | 0/200 | 39 | bad_part_duck_a 3, contact_share 150, edge 2, fall_duck_a 3, reward_vs_dist 8 |
| l2_s1 | 0/200 | 1/200 | 0/200 | 14/200 | 64% | 48% | 82/200 | 5.8% | 0.72 | 0/200 | 41 | bad_part_duck_a 1, contact_share 153, reward_vs_dist 12, spin 1 |
| l1_s2 | 0/200 | 2/200 | 0/200 | 4/200 | 76% | 51% | 98/200 | 2.1% | 0.70 | 0/200 | 37 | contact_share 129, reward_vs_dist 8 |
| l2_s2 | 0/200 | 0/200 | 0/200 | 5/200 | 77% | 49% | 98/200 | 3.3% | 0.71 | 0/200 | 39 | bad_part_duck_b 1, contact_share 125, edge 1, reward_vs_dist 15 |
