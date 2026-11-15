# Policy comparison on experiments/test_sets/stage1.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| d2_exact | 74% (37/50) | 17/17 | 15/16 | 5/17 |
| th_chirp_2s_30deg | 62% (31/50) | 17/17 | 14/16 | 0/17 |
| th_chirp_2s_10deg | 66% (33/50) | 16/17 | 14/16 | 3/17 |
| th_chirp_0.5s_30deg | 70% (35/50) | 17/17 | 15/16 | 3/17 |
| th_chirp_4s_60deg | 50% (25/50) | 13/17 | 10/16 | 2/17 |
| th_control_no_noise | 74% (37/50) | 17/17 | 15/16 | 5/17 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| d2_exact | 55 | 42 (15 to 112) | 102 | 16/17 | 5/17 |
| th_chirp_2s_30deg | 55 | 54 (18 to 117) | 119 | 13/17 | 0/17 |
| th_chirp_2s_10deg | 55 | 55 (15 to 184) | 120 | 15/17 | 3/17 |
| th_chirp_0.5s_30deg | 55 | 55 (19 to 188) | 150 | 16/17 | 3/17 |
| th_chirp_4s_60deg | 55 | 57 (12 to 180) | 152 | 14/17 | 2/17 |
| th_control_no_noise | 55 | 42 (15 to 112) | 102 | 16/17 | 5/17 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d2_exact | 5/50 | 2/50 | 1/50 | 6/50 | 51% | 94% | 0/50 | 14.6% | 0.88 | 0/50 | 45 | bad_part_duck_a 6, bad_part_duck_b 3, contact_share 17, edge 1, fall_duck_a 4, fall_duck_b 2, reward_vs_dist 2 |
| th_chirp_2s_30deg | 4/50 | 0/50 | 5/50 | 15/50 | 52% | 85% | 0/50 | 17.6% | 1.02 | 0/50 | 55 | bad_part_duck_a 7, bad_part_duck_b 5, contact_share 21, fall_duck_a 6, fall_duck_b 4, reward_vs_dist 5 |
| th_chirp_2s_10deg | 5/50 | 2/50 | 6/50 | 10/50 | 52% | 90% | 0/50 | 13.5% | 0.98 | 0/50 | 51 | bad_part_duck_a 5, bad_part_duck_b 4, contact_share 17, fall_duck_a 4, fall_duck_b 3, reward_vs_dist 3, spin 2 |
| th_chirp_0.5s_30deg | 2/50 | 0/50 | 4/50 | 13/50 | 50% | 89% | 0/50 | 12.8% | 0.99 | 0/50 | 51 | bad_part_duck_a 9, bad_part_duck_b 2, contact_share 19, fall_duck_a 5, fall_duck_b 2, reward_vs_dist 7 |
| th_chirp_4s_60deg | 3/50 | 0/50 | 11/50 | 22/50 | 49% | 86% | 0/50 | 19.0% | 1.23 | 0/50 | 64 | bad_part_duck_a 11, bad_part_duck_b 2, contact_share 19, fall_duck_a 8, fall_duck_b 1, reward_vs_dist 7 |
| th_control_no_noise | 5/50 | 2/50 | 1/50 | 6/50 | 51% | 94% | 0/50 | 14.6% | 0.88 | 0/50 | 45 | bad_part_duck_a 6, bad_part_duck_b 3, contact_share 17, edge 1, fall_duck_a 4, fall_duck_b 2, reward_vs_dist 2 |
