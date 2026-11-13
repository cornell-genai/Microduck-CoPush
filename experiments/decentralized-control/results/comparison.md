# Policy comparison on experiments/test_sets/stage1.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| stage1 | 60% (30/50) | 15/17 | 13/16 | 2/17 |
| d1 | 60% (30/50) | 15/17 | 14/16 | 1/17 |
| d2 | 74% (37/50) | 17/17 | 15/16 | 5/17 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| stage1 | 55 | 40 (20 to 93) | 38 | 16/17 | 2/17 |
| d1 | 55 | 65 (19 to 204) | 182 | 16/17 | 1/17 |
| d2 | 55 | 42 (15 to 112) | 102 | 16/17 | 5/17 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stage1 | 3/50 | 0/50 | 14/50 | 17/50 | 46% | 86% | 2/50 | 13.5% | 1.11 | 0/50 | 57 | bad_part_duck_a 8, bad_part_duck_b 2, contact_share 19, fall_duck_a 5, fall_duck_b 1, reward_vs_dist 3 |
| d1 | 2/50 | 0/50 | 4/50 | 18/50 | 48% | 92% | 0/50 | 20.6% | 1.12 | 0/50 | 57 | bad_part_duck_a 4, contact_share 16, fall_duck_a 3, fall_duck_b 1, reward_vs_dist 9 |
| d2 | 5/50 | 2/50 | 1/50 | 6/50 | 51% | 94% | 0/50 | 14.6% | 0.88 | 0/50 | 45 | bad_part_duck_a 6, bad_part_duck_b 3, contact_share 17, edge 1, fall_duck_a 4, fall_duck_b 2, reward_vs_dist 2 |
