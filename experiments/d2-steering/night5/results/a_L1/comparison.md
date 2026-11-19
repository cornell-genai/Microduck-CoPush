# Policy comparison on experiments/test_sets/stage1_L1_large.json

One deterministic episode per start, env from `experiments/d2-steering/night5/sets/L1/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| a_s1 | 88% (176/200) | 63/67 | 59/67 | 54/66 |
| a_s2 | 89% (178/200) | 66/67 | 56/67 | 56/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| a_s1 | 57 | 44 (-20 to 75) | 35 | 65/66 | 54/66 |
| a_s2 | 57 | 46 (-16 to 87) | 41 | 65/66 | 56/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a_s1 | 4/200 | 0/200 | 2/200 | 20/200 | 64% | 46% | 86/200 | 6.4% | 0.71 | 2/200 | 44 | bad_part_duck_a 2, bad_part_duck_b 5, contact_share 156, edge 1, fall_duck_a 3, fall_duck_b 4, reward_vs_dist 15 |
| a_s2 | 4/200 | 0/200 | 0/200 | 18/200 | 70% | 51% | 86/200 | 5.7% | 0.71 | 4/200 | 43 | bad_part_duck_b 1, contact_share 112, edge 2, fall_duck_a 4, reward_vs_dist 17 |
