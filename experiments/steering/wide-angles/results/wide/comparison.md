# Policy comparison on experiments/test_sets/steering_wide_angles_large.json

One deterministic episode per start, env from `experiments/steering/wide-angles/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| reference_s1 | 70% (139/200) | 58/83 | 33/33 | 48/84 |
| reference_s2 | 72% (144/200) | 59/83 | 31/33 | 54/84 |
| wide_s1 | 92% (184/200) | 74/83 | 32/33 | 78/84 |
| wide_s2 | 86% (173/200) | 76/83 | 33/33 | 64/84 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| reference_s1 | 68 | -24 (-259 to 87) | -25 | 56/84 | 48/84 |
| reference_s2 | 68 | -21 (-254 to 83) | -26 | 56/84 | 54/84 |
| wide_s1 | 68 | 65 (21 to 118) | 64 | 84/84 | 78/84 |
| wide_s2 | 68 | 55 (-291 to 122) | 52 | 78/84 | 64/84 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference_s1 | 14/200 | 1/200 | 42/200 | 46/200 | 70% | 54% | 76/200 | 2.7% | 0.97 | 0/200 | 54 | bad_part_duck_a 12, bad_part_duck_b 4, contact_share 145, edge 2, fall_duck_a 14, fall_duck_b 8, reward_vs_dist 25 |
| reference_s2 | 14/200 | 2/200 | 41/200 | 40/200 | 70% | 50% | 79/200 | 2.5% | 0.92 | 0/200 | 52 | bad_part_duck_a 27, bad_part_duck_b 6, contact_share 135, edge 2, fall_duck_a 13, fall_duck_b 8, reward_vs_dist 17 |
| wide_s1 | 5/200 | 3/200 | 0/200 | 8/200 | 64% | 51% | 79/200 | 1.8% | 0.76 | 0/200 | 44 | bad_part_duck_a 3, bad_part_duck_b 3, contact_share 155, fall_duck_a 3, fall_duck_b 3, reward_vs_dist 5 |
| wide_s2 | 3/200 | 1/200 | 8/200 | 23/200 | 65% | 50% | 79/200 | 4.1% | 0.81 | 1/200 | 49 | bad_part_duck_a 3, bad_part_duck_b 5, contact_share 136, edge 1, fall_duck_a 1, fall_duck_b 4, reward_vs_dist 24 |
