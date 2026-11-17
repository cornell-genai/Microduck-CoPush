# Policy comparison on experiments/test_sets/stage1_large.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| reference | 66% (133/200) | 65/67 | 58/67 | 10/66 |
| a_s1 | 94% (189/200) | 66/67 | 64/67 | 59/66 |
| a_s2 | 96% (192/200) | 67/67 | 65/67 | 60/66 |
| c_s1 | 92% (185/200) | 64/67 | 61/67 | 60/66 |
| c_s2 | 92% (184/200) | 66/67 | 59/67 | 59/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| reference | 57 | 57 (11 to 225) | 123 | 60/66 | 10/66 |
| a_s1 | 57 | 45 (31 to 69) | 34 | 66/66 | 59/66 |
| a_s2 | 57 | 48 (32 to 73) | 39 | 66/66 | 60/66 |
| c_s1 | 57 | 53 (29 to 75) | 41 | 66/66 | 60/66 |
| c_s2 | 57 | 48 (34 to 79) | 36 | 66/66 | 59/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 16/200 | 8/200 | 18/200 | 43/200 | 49% | 89% | 1/200 | 14.7% | 0.97 | 0/200 | 51 | bad_part_duck_a 29, bad_part_duck_b 15, contact_share 69, edge 2, fall_duck_a 23, fall_duck_b 8, reward_vs_dist 17 |
| a_s1 | 1/200 | 0/200 | 0/200 | 10/200 | 64% | 52% | 81/200 | 4.3% | 0.72 | 0/200 | 40 | bad_part_duck_a 1, bad_part_duck_b 1, contact_share 148, fall_duck_a 1, reward_vs_dist 11 |
| a_s2 | 1/200 | 0/200 | 0/200 | 7/200 | 71% | 56% | 84/200 | 4.3% | 0.73 | 0/200 | 40 | contact_share 121, fall_duck_a 1, reward_vs_dist 23 |
| c_s1 | 0/200 | 0/200 | 0/200 | 15/200 | 64% | 48% | 81/200 | 5.3% | 0.73 | 0/200 | 43 | bad_part_duck_a 1, contact_share 165, fall_duck_a 1, reward_vs_dist 14 |
| c_s2 | 0/200 | 0/200 | 0/200 | 16/200 | 71% | 57% | 81/200 | 1.5% | 0.73 | 0/200 | 42 | bad_part_duck_a 1, contact_share 115, reward_vs_dist 11 |
