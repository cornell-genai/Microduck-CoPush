# Policy comparison on experiments/test_sets/stage1.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| d2_exact | 74% (37/50) | 17/17 | 15/16 | 5/17 |
| d1 | 60% (30/50) | 15/17 | 14/16 | 1/17 |
| part2_seed1 | 60% (30/50) | 15/17 | 12/16 | 3/17 |
| run2_seed2 | 62% (31/50) | 17/17 | 13/16 | 1/17 |
| run1_true_heading | 72% (36/50) | 16/17 | 15/16 | 5/17 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| d2_exact | 55 | 42 (15 to 112) | 102 | 16/17 | 5/17 |
| d1 | 55 | 65 (19 to 204) | 182 | 16/17 | 1/17 |
| part2_seed1 | 55 | 62 (20 to 178) | 118 | 15/17 | 3/17 |
| run2_seed2 | 55 | 55 (16 to 202) | 149 | 15/17 | 1/17 |
| run1_true_heading | 55 | 71 (15 to 201) | 172 | 15/17 | 5/17 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d2_exact | 5/50 | 2/50 | 1/50 | 6/50 | 51% | 94% | 0/50 | 14.6% | 0.88 | 0/50 | 45 | bad_part_duck_a 6, bad_part_duck_b 3, contact_share 17, edge 1, fall_duck_a 4, fall_duck_b 2, reward_vs_dist 2 |
| d1 | 2/50 | 0/50 | 4/50 | 18/50 | 48% | 92% | 0/50 | 20.6% | 1.12 | 0/50 | 57 | bad_part_duck_a 4, contact_share 16, fall_duck_a 3, fall_duck_b 1, reward_vs_dist 9 |
| part2_seed1 | 3/50 | 0/50 | 11/50 | 17/50 | 53% | 94% | 0/50 | 30.3% | 1.12 | 0/50 | 59 | bad_part_duck_a 1, contact_share 15, fall_duck_a 5, reward_vs_dist 4 |
| run2_seed2 | 3/50 | 0/50 | 10/50 | 16/50 | 50% | 90% | 1/50 | 20.9% | 1.14 | 0/50 | 57 | bad_part_duck_a 8, contact_share 19, fall_duck_a 5, fall_duck_b 2, reward_vs_dist 7 |
| run1_true_heading | 1/50 | 2/50 | 4/50 | 11/50 | 46% | 91% | 0/50 | 8.8% | 1.03 | 0/50 | 54 | contact_share 12, fall_duck_a 3, fall_duck_b 1, reward_vs_dist 10, spin 1 |
