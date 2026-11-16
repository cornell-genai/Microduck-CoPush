# Policy comparison on experiments/test_sets/stage1_large.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| d2_exact | 66% (133/200) | 65/67 | 58/67 | 10/66 |
| d1 | 64% (128/200) | 64/67 | 58/67 | 6/66 |
| part2_seed1 | 63% (126/200) | 65/67 | 54/67 | 7/66 |
| run2_seed2 | 63% (126/200) | 64/67 | 58/67 | 4/66 |
| run1_true_heading | 64% (127/200) | 63/67 | 58/67 | 6/66 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| d2_exact | 57 | 57 (11 to 225) | 123 | 60/66 | 10/66 |
| d1 | 57 | 80 (15 to 236) | 177 | 56/66 | 6/66 |
| part2_seed1 | 57 | 71 (16 to 210) | 144 | 58/66 | 7/66 |
| run2_seed2 | 57 | 80 (16 to 254) | 160 | 50/66 | 4/66 |
| run1_true_heading | 57 | 77 (16 to 234) | 156 | 57/66 | 6/66 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d2_exact | 16/200 | 8/200 | 18/200 | 43/200 | 49% | 89% | 1/200 | 14.7% | 0.97 | 0/200 | 51 | bad_part_duck_a 29, bad_part_duck_b 15, contact_share 69, edge 2, fall_duck_a 23, fall_duck_b 8, reward_vs_dist 17 |
| d1 | 8/200 | 3/200 | 25/200 | 61/200 | 47% | 93% | 0/200 | 21.3% | 1.12 | 0/200 | 57 | bad_part_duck_a 18, bad_part_duck_b 5, contact_share 53, fall_duck_a 13, fall_duck_b 4, reward_vs_dist 31 |
| part2_seed1 | 8/200 | 2/200 | 27/200 | 64/200 | 52% | 92% | 1/200 | 25.6% | 1.09 | 0/200 | 57 | bad_part_duck_a 16, bad_part_duck_b 7, contact_share 68, edge 2, fall_duck_a 11, fall_duck_b 6, reward_vs_dist 15 |
| run2_seed2 | 11/200 | 2/200 | 29/200 | 61/200 | 48% | 92% | 0/200 | 20.4% | 1.11 | 0/200 | 56 | bad_part_duck_a 21, bad_part_duck_b 7, contact_share 55, fall_duck_a 19, fall_duck_b 2, reward_vs_dist 24, spin 2 |
| run1_true_heading | 11/200 | 2/200 | 22/200 | 60/200 | 47% | 91% | 1/200 | 12.6% | 1.09 | 0/200 | 56 | bad_part_duck_a 24, bad_part_duck_b 5, contact_share 60, edge 1, fall_duck_a 17, fall_duck_b 4, reward_vs_dist 26, spin 2 |
