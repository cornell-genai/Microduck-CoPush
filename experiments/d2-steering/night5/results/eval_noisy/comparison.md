# Policy comparison on experiments/test_sets/stage1_noisy_large.json

One deterministic episode per start, env from `experiments/d2-steering/noisy-sets/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| a_s1 | 96% (192/200) | 66/66 | 61/67 | 65/67 |
| a_s2 | 95% (190/200) | 64/66 | 64/67 | 62/67 |
| l1_s1 | 95% (190/200) | 64/66 | 64/67 | 62/67 |
| l2_s1 | 92% (185/200) | 63/66 | 61/67 | 61/67 |
| l1_s2 | 95% (190/200) | 64/66 | 66/67 | 60/67 |
| l2_s2 | 93% (186/200) | 65/66 | 63/67 | 58/67 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| a_s1 | 56 | 44 (24 to 64) | 34 | 67/67 | 65/67 |
| a_s2 | 56 | 48 (30 to 77) | 39 | 67/67 | 62/67 |
| l1_s1 | 56 | 44 (21 to 67) | 33 | 67/67 | 62/67 |
| l2_s1 | 56 | 47 (27 to 79) | 35 | 67/67 | 61/67 |
| l1_s2 | 56 | 41 (24 to 63) | 33 | 67/67 | 60/67 |
| l2_s2 | 56 | 44 (25 to 75) | 34 | 67/67 | 58/67 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a_s1 | 0/200 | 1/200 | 0/200 | 7/200 | 65% | 49% | 84/200 | 3.5% | 0.72 | 0/200 | 40 | bad_part_duck_a 2, contact_share 137, edge 2, fall_duck_a 1, reward_vs_dist 6 |
| a_s2 | 0/200 | 0/200 | 0/200 | 10/200 | 71% | 53% | 87/200 | 4.0% | 0.73 | 0/200 | 41 | contact_share 106, edge 1, reward_vs_dist 20 |
| l1_s1 | 1/200 | 2/200 | 0/200 | 7/200 | 68% | 47% | 88/200 | 4.1% | 0.71 | 0/200 | 39 | bad_part_duck_a 2, bad_part_duck_b 1, contact_share 150, fall_duck_a 1, reward_vs_dist 6 |
| l2_s1 | 2/200 | 0/200 | 0/200 | 13/200 | 65% | 43% | 86/200 | 5.6% | 0.73 | 0/200 | 42 | contact_share 158, edge 1, fall_duck_a 2, reward_vs_dist 6 |
| l1_s2 | 0/200 | 2/200 | 0/200 | 8/200 | 76% | 49% | 98/200 | 3.4% | 0.70 | 0/200 | 40 | contact_share 113, edge 4, reward_vs_dist 5 |
| l2_s2 | 1/200 | 3/200 | 0/200 | 10/200 | 77% | 46% | 102/200 | 4.2% | 0.71 | 0/200 | 41 | bad_part_duck_a 1, bad_part_duck_b 1, contact_share 118, edge 1, fall_duck_a 2, reward_vs_dist 18, spin 1 |
