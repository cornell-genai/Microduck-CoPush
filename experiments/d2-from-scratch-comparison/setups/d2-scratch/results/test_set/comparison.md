# Policy comparison on experiments/test_sets/stage1.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| s1 | 32% (16/50) | 5/17 | 11/16 | 0/17 |
| s2 | 28% (14/50) | 4/17 | 9/16 | 1/17 |
| s3 | 38% (19/50) | 3/17 | 14/16 | 2/17 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| s1 | 55 | 53 (15 to 176) | 64 | 13/17 | 0/17 |
| s2 | 55 | 63 (8 to 199) | 145 | 14/17 | 1/17 |
| s3 | 55 | 68 (19 to 201) | 136 | 13/17 | 2/17 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s1 | 4/50 | 0/50 | 28/50 | 30/50 | 55% | 92% | 0/50 | 43.4% | 1.54 | 0/50 | 77 | bad_part_duck_a 5, bad_part_duck_b 1, contact_share 14, fall_duck_a 6, fall_duck_b 3, reward_vs_dist 7 |
| s2 | 0/50 | 3/50 | 25/50 | 33/50 | 54% | 94% | 0/50 | 25.8% | 1.60 | 0/50 | 77 | bad_part_duck_a 5, bad_part_duck_b 3, contact_share 12, fall_duck_a 3, fall_duck_b 2, reward_vs_dist 9 |
| s3 | 3/50 | 0/50 | 23/50 | 28/50 | 55% | 93% | 0/50 | 31.3% | 1.51 | 0/50 | 74 | bad_part_duck_a 9, bad_part_duck_b 1, contact_share 14, fall_duck_a 7, fall_duck_b 1, reward_vs_dist 7 |
