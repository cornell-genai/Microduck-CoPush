# Policy comparison on experiments/test_sets/stage1_noisy_large.json

One deterministic episode per start, env from `experiments/steering/start-noise/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| clean_s1 | 94% (188/200) | 66/66 | 63/67 | 59/67 |
| noise_s1 | 93% (186/200) | 62/66 | 65/67 | 59/67 |
| clean_s2 | 91% (182/200) | 64/66 | 65/67 | 53/67 |
| noise_s2 | 90% (179/200) | 64/66 | 64/67 | 51/67 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| clean_s1 | 56 | 43 (16 to 79) | 34 | 67/67 | 59/67 |
| noise_s1 | 56 | 43 (16 to 73) | 35 | 67/67 | 59/67 |
| clean_s2 | 56 | 41 (20 to 65) | 39 | 67/67 | 53/67 |
| noise_s2 | 56 | 39 (18 to 69) | 33 | 67/67 | 51/67 |

## Failure modes and idling (all 200 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| clean_s1 | 2/200 | 2/200 | 0/200 | 8/200 | 76% | 49% | 99/200 | 2.4% | 0.71 | 0/200 | 40 | contact_share 117, edge 3, fall_duck_a 1, fall_duck_b 1, reward_vs_dist 12 |
| noise_s1 | 2/200 | 5/200 | 0/200 | 7/200 | 81% | 40% | 115/200 | 1.9% | 0.71 | 0/200 | 41 | bad_part_duck_a 1, contact_share 128, edge 3, fall_duck_b 2, reward_vs_dist 13 |
| clean_s2 | 2/200 | 0/200 | 0/200 | 16/200 | 80% | 41% | 113/200 | 3.2% | 0.71 | 0/200 | 43 | bad_part_duck_a 3, bad_part_duck_b 3, contact_share 126, edge 6, fall_duck_a 2, fall_duck_b 2, reward_vs_dist 7 |
| noise_s2 | 1/200 | 9/200 | 0/200 | 11/200 | 79% | 45% | 105/200 | 1.7% | 0.70 | 0/200 | 40 | bad_part_duck_b 2, contact_share 121, edge 9, fall_duck_a 1, fall_duck_b 1, reward_vs_dist 6 |
