# Policy comparison on experiments/test_sets/stage1_large.json

One deterministic episode per start, env from `experiments/steering/stand-still/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| clean_s1 | 96% (192/200) | 65/67 | 66/67 | 61/66 |
| noise_s1 | 94% (189/200) | 65/67 | 66/67 | 58/66 |
| clean_s2 | 98% (197/200) | 66/67 | 67/67 | 64/66 |
| noise_s2 | 92% (185/200) | 66/67 | 66/67 | 53/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| clean_s1 | 57 | 44 (21 to 78) | 36 | 66/66 | 61/66 |
| noise_s1 | 57 | 44 (20 to 77) | 34 | 66/66 | 58/66 |
| clean_s2 | 57 | 44 (24 to 75) | 35 | 66/66 | 64/66 |
| noise_s2 | 57 | 40 (21 to 65) | 31 | 66/66 | 53/66 |

## Failure modes and idling (all 200 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| clean_s1 | 1/200 | 0/200 | 0/200 | 7/200 | 77% | 50% | 97/200 | 2.0% | 0.71 | 0/200 | 39 | contact_share 137, edge 3, fall_duck_b 1, reward_vs_dist 9 |
| noise_s1 | 0/200 | 3/200 | 0/200 | 8/200 | 82% | 40% | 114/200 | 1.8% | 0.71 | 0/200 | 41 | contact_share 147, edge 4, reward_vs_dist 10 |
| clean_s2 | 0/200 | 0/200 | 0/200 | 3/200 | 80% | 42% | 111/200 | 2.5% | 0.70 | 0/200 | 39 | bad_part_duck_a 1, bad_part_duck_b 1, contact_share 132, edge 3, reward_vs_dist 7 |
| noise_s2 | 0/200 | 3/200 | 0/200 | 12/200 | 79% | 46% | 102/200 | 2.3% | 0.70 | 0/200 | 40 | contact_share 144, edge 7, reward_vs_dist 5 |
