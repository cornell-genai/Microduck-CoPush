# Policy comparison on experiments/test_sets/stage1_noisy_large.json

One deterministic episode per start, env from `experiments/d2-steering/noisy-sets/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| reference | 62% (125/200) | 60/66 | 56/67 | 9/67 |
| a_s1 | 96% (192/200) | 66/66 | 61/67 | 65/67 |
| a_s2 | 95% (190/200) | 64/66 | 64/67 | 62/67 |
| c_s1 | 90% (179/200) | 63/66 | 58/67 | 58/67 |
| c_s2 | 93% (186/200) | 64/66 | 63/67 | 59/67 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| reference | 56 | 54 (17 to 213) | 132 | 59/67 | 9/67 |
| a_s1 | 56 | 44 (24 to 64) | 34 | 67/67 | 65/67 |
| a_s2 | 56 | 48 (30 to 77) | 39 | 67/67 | 62/67 |
| c_s1 | 56 | 49 (27 to 69) | 46 | 67/67 | 58/67 |
| c_s2 | 56 | 45 (27 to 74) | 35 | 67/67 | 59/67 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 13/200 | 3/200 | 23/200 | 59/200 | 51% | 89% | 0/200 | 15.6% | 1.08 | 0/200 | 56 | bad_part_duck_a 26, bad_part_duck_b 9, contact_share 95, fall_duck_a 22, fall_duck_b 5, reward_vs_dist 28 |
| a_s1 | 0/200 | 1/200 | 0/200 | 7/200 | 65% | 49% | 84/200 | 3.5% | 0.72 | 0/200 | 40 | bad_part_duck_a 2, contact_share 137, edge 2, fall_duck_a 1, reward_vs_dist 6 |
| a_s2 | 0/200 | 0/200 | 0/200 | 10/200 | 71% | 53% | 87/200 | 4.0% | 0.73 | 0/200 | 41 | contact_share 106, edge 1, reward_vs_dist 20 |
| c_s1 | 0/200 | 2/200 | 0/200 | 19/200 | 65% | 45% | 84/200 | 6.1% | 0.73 | 0/200 | 44 | bad_part_duck_a 3, bad_part_duck_b 1, contact_share 154, edge 1, reward_vs_dist 18 |
| c_s2 | 0/200 | 0/200 | 0/200 | 14/200 | 72% | 56% | 83/200 | 0.9% | 0.73 | 0/200 | 41 | contact_share 107, edge 4, reward_vs_dist 9 |
