# Policy comparison on experiments/test_sets/stage1.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| ft_chirp_2s_30deg | 60% (30/50) | 15/17 | 12/16 | 3/17 |
| ft_random_direction | 22% (11/50) | 6/17 | 5/16 | 0/17 |
| ft_exact_every_2s | 66% (33/50) | 17/17 | 13/16 | 3/17 |
| ft_exact_every_step | 64% (32/50) | 17/17 | 14/16 | 1/17 |
| d1 | 60% (30/50) | 15/17 | 14/16 | 1/17 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| ft_chirp_2s_30deg | 55 | 62 (20 to 178) | 118 | 15/17 | 3/17 |
| ft_random_direction | 55 | 111 (21 to 178) | 152 | 9/17 | 0/17 |
| ft_exact_every_2s | 55 | 59 (21 to 198) | 136 | 16/17 | 3/17 |
| ft_exact_every_step | 55 | 65 (26 to 193) | 154 | 14/17 | 1/17 |
| d1 | 55 | 65 (19 to 204) | 182 | 16/17 | 1/17 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ft_chirp_2s_30deg | 3/50 | 0/50 | 11/50 | 17/50 | 53% | 94% | 0/50 | 30.3% | 1.12 | 0/50 | 59 | bad_part_duck_a 1, contact_share 15, fall_duck_a 5, reward_vs_dist 4 |
| ft_random_direction | 3/50 | 1/50 | 26/50 | 35/50 | 46% | 82% | 1/50 | 40.4% | 1.60 | 0/50 | 83 | bad_part_duck_a 17, bad_part_duck_b 2, contact_share 29, edge 1, fall_duck_a 5, fall_duck_b 1, reward_vs_dist 7 |
| ft_exact_every_2s | 1/50 | 1/50 | 7/50 | 15/50 | 53% | 94% | 0/50 | 27.9% | 1.06 | 0/50 | 55 | bad_part_duck_a 4, contact_share 16, fall_duck_a 4, reward_vs_dist 4 |
| ft_exact_every_step | 1/50 | 0/50 | 5/50 | 17/50 | 53% | 93% | 0/50 | 26.6% | 1.09 | 0/50 | 56 | contact_share 14, fall_duck_a 1, reward_vs_dist 4 |
| d1 | 2/50 | 0/50 | 4/50 | 18/50 | 48% | 92% | 0/50 | 20.6% | 1.12 | 0/50 | 57 | bad_part_duck_a 4, contact_share 16, fall_duck_a 3, fall_duck_b 1, reward_vs_dist 9 |
