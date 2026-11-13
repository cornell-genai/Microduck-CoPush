# Policy comparison on experiments/test_sets/stage1.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| s1 | 48% (24/50) | 9/17 | 14/16 | 1/17 |
| s2 | 48% (24/50) | 9/17 | 12/16 | 3/17 |
| s3 | 58% (29/50) | 12/17 | 14/16 | 3/17 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| s1 | 55 | 25 (-20 to 62) | 17 | 12/17 | 1/17 |
| s2 | 55 | 39 (18 to 99) | 56 | 15/17 | 3/17 |
| s3 | 55 | 42 (15 to 80) | 50 | 14/17 | 3/17 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s1 | 3/50 | 0/50 | 25/50 | 23/50 | 50% | 94% | 0/50 | 16.3% | 1.38 | 0/50 | 67 | bad_part_duck_a 2, bad_part_duck_b 5, contact_share 11, fall_duck_b 4, reward_vs_dist 9 |
| s2 | 1/50 | 0/50 | 25/50 | 25/50 | 52% | 95% | 0/50 | 0.6% | 1.52 | 0/50 | 66 | bad_part_duck_a 3, contact_share 11, fall_duck_a 3 |
| s3 | 0/50 | 1/50 | 18/50 | 20/50 | 51% | 91% | 0/50 | 6.8% | 1.28 | 0/50 | 59 | bad_part_duck_a 9, contact_share 16, edge 1, fall_duck_a 2, reward_vs_dist 4 |
