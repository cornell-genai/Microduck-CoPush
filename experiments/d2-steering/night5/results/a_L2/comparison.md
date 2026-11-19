# Policy comparison on experiments/test_sets/stage1_L2_large.json

One deterministic episode per start, env from `experiments/d2-steering/night5/sets/L2/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| a_s1 | 81% (162/200) | 64/67 | 54/67 | 44/66 |
| a_s2 | 82% (165/200) | 63/67 | 58/67 | 44/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| a_s1 | 57 | 45 (24 to 94) | 41 | 65/66 | 44/66 |
| a_s2 | 57 | 45 (13 to 81) | 46 | 64/66 | 44/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a_s1 | 4/200 | 2/200 | 0/200 | 32/200 | 66% | 47% | 86/200 | 8.8% | 0.71 | 0/200 | 48 | bad_part_duck_a 5, bad_part_duck_b 4, contact_share 156, edge 1, fall_duck_a 2, fall_duck_b 4, reward_vs_dist 8 |
| a_s2 | 3/200 | 3/200 | 0/200 | 29/200 | 73% | 51% | 88/200 | 8.1% | 0.71 | 0/200 | 46 | bad_part_duck_a 1, bad_part_duck_b 6, contact_share 117, edge 1, fall_duck_a 1, fall_duck_b 5, reward_vs_dist 25 |
