# Policy comparison on experiments/test_sets/stage1_L2_large.json

One deterministic episode per start, env from `experiments/d2-steering/night5/sets/L2/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| l1_s1 | 86% (173/200) | 64/67 | 59/67 | 50/66 |
| l2_s1 | 88% (177/200) | 64/67 | 61/67 | 52/66 |
| l1_s2 | 87% (174/200) | 65/67 | 60/67 | 49/66 |
| l2_s2 | 88% (176/200) | 64/67 | 57/67 | 55/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| l1_s1 | 57 | 44 (24 to 70) | 40 | 66/66 | 50/66 |
| l2_s1 | 57 | 48 (27 to 81) | 39 | 66/66 | 52/66 |
| l1_s2 | 57 | 41 (20 to 69) | 43 | 66/66 | 49/66 |
| l2_s2 | 57 | 45 (16 to 70) | 38 | 65/66 | 55/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| l1_s1 | 1/200 | 2/200 | 0/200 | 24/200 | 70% | 44% | 91/200 | 8.1% | 0.71 | 0/200 | 45 | bad_part_duck_a 4, bad_part_duck_b 3, contact_share 156, fall_duck_a 1, fall_duck_b 1, reward_vs_dist 12 |
| l2_s1 | 2/200 | 0/200 | 0/200 | 21/200 | 66% | 42% | 87/200 | 8.0% | 0.73 | 0/200 | 45 | bad_part_duck_a 1, bad_part_duck_b 3, contact_share 164, fall_duck_a 1, fall_duck_b 1, reward_vs_dist 12 |
| l1_s2 | 0/200 | 1/200 | 0/200 | 25/200 | 78% | 44% | 109/200 | 6.9% | 0.71 | 1/200 | 46 | bad_part_duck_a 2, bad_part_duck_b 2, contact_share 124, edge 4, reward_vs_dist 10 |
| l2_s2 | 3/200 | 2/200 | 1/200 | 19/200 | 78% | 43% | 106/200 | 6.9% | 0.71 | 2/200 | 44 | bad_part_duck_a 1, bad_part_duck_b 3, contact_share 130, edge 3, fall_duck_a 3, fall_duck_b 1, reward_vs_dist 17 |
