# Policy comparison on experiments/test_sets/stage1_noisy_large.json

One deterministic episode per start, env from `experiments/d2-steering/noisy-sets/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| n1_a | 80% (160/200) | 59/66 | 50/67 | 51/67 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| n1_a | 56 | 44 (27 to 68) | 34 | 67/67 | 51/67 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| n1_a | 5/200 | 1/200 | 0/200 | 34/200 | 66% | 45% | 87/200 | 12.2% | 0.72 | 0/200 | 58 | bad_part_duck_a 4, bad_part_duck_b 3, contact_share 152, edge 1, fall_duck_a 4, fall_duck_b 3, reward_vs_dist 8 |
