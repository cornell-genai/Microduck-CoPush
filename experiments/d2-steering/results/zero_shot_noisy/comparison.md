# Policy comparison on experiments/test_sets/stage1_noisy_large.json

One deterministic episode per start, env from `experiments/d2-steering/noisy-sets/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| reference | 62% (125/200) | 60/66 | 56/67 | 9/67 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| reference | 56 | 54 (17 to 213) | 132 | 59/67 | 9/67 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 13/200 | 3/200 | 23/200 | 59/200 | 51% | 89% | 0/200 | 15.6% | 1.08 | 0/200 | 56 | bad_part_duck_a 26, bad_part_duck_b 9, contact_share 95, fall_duck_a 22, fall_duck_b 5, reward_vs_dist 28 |
