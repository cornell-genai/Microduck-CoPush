# Policy comparison on experiments/test_sets/stage1.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| s1 | 32% (16/50) | 5/17 | 11/16 | 0/17 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| s1 | 55 | 53 (15 to 176) | 64 | 13/17 | 0/17 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s1 | 4/50 | 0/50 | 28/50 | 30/50 | 55% | 92% | 0/50 | 43.4% | 1.54 | 0/50 | 77 | bad_part_duck_a 5, bad_part_duck_b 1, contact_share 14, fall_duck_a 6, fall_duck_b 3, reward_vs_dist 7 |
