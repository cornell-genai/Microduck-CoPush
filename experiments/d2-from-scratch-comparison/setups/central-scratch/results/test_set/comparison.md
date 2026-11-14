# Policy comparison on experiments/test_sets/stage1.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| s1 | 50% (25/50) | 10/17 | 14/16 | 1/17 |
| s2 | 28% (14/50) | 3/17 | 11/16 | 0/17 |
| s3 | 44% (22/50) | 10/17 | 11/16 | 1/17 |
| s4 | 40% (20/50) | 7/17 | 12/16 | 1/17 |
| s5 | 32% (16/50) | 6/17 | 10/16 | 0/17 |
| s6 | 48% (24/50) | 13/17 | 11/16 | 0/17 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| s1 | 55 | 25 (3 to 35) | 14 | 9/17 | 1/17 |
| s2 | 55 | 6 (-68 to 111) | 14 | 5/17 | 0/17 |
| s3 | 55 | 34 (17 to 55) | 28 | 14/17 | 1/17 |
| s4 | 55 | 39 (5 to 107) | 46 | 13/17 | 1/17 |
| s5 | 55 | 29 (-6 to 66) | 22 | 14/17 | 0/17 |
| s6 | 55 | 16 (-42 to 124) | 9 | 10/17 | 0/17 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s1 | 0/50 | 1/50 | 24/50 | 24/50 | 50% | 98% | 0/50 | 1.3% | 1.37 | 0/50 | 65 | reward_vs_dist 2 |
| s2 | 4/50 | 4/50 | 31/50 | 28/50 | 54% | 88% | 1/50 | 11.2% | 1.42 | 0/50 | 76 | bad_part_duck_a 7, bad_part_duck_b 8, contact_share 25, fall_duck_a 2, fall_duck_b 5, reward_vs_dist 4 |
| s3 | 0/50 | 0/50 | 28/50 | 28/50 | 53% | 98% | 0/50 | 0.0% | 1.50 | 0/50 | 70 | contact_share 3, reward_vs_dist 3 |
| s4 | 0/50 | 0/50 | 27/50 | 30/50 | 54% | 93% | 0/50 | 42.2% | 1.31 | 0/50 | 76 | bad_part_duck_a 2, bad_part_duck_b 1, contact_share 17, fall_duck_a 1, fall_duck_b 1, reward_vs_dist 2 |
| s5 | 2/50 | 0/50 | 31/50 | 32/50 | 53% | 94% | 0/50 | 4.3% | 1.59 | 0/50 | 76 | bad_part_duck_a 5, contact_share 9, edge 1, fall_duck_a 5, reward_vs_dist 16 |
| s6 | 3/50 | 3/50 | 23/50 | 20/50 | 52% | 95% | 0/50 | 0.0% | 1.39 | 0/50 | 63 | bad_part_duck_a 1, bad_part_duck_b 4, contact_share 13, fall_duck_a 2, fall_duck_b 2 |
