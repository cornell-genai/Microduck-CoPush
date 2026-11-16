# Policy comparison on experiments/test_sets/stage1.json

One deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml`. Success is compared, not return.

## Success by box angle side

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| d2_exact | 74% (37/50) | 17/17 | 15/16 | 5/17 |
| d1 | 60% (30/50) | 15/17 | 14/16 | 1/17 |
| chirp_2s_30deg | 34% (17/50) | 6/17 | 9/16 | 2/17 |
| chirp_2s_10deg | 42% (21/50) | 7/17 | 12/16 | 2/17 |
| chirp_0.5s_30deg | 38% (19/50) | 7/17 | 12/16 | 0/17 |
| chirp_4s_60deg | 30% (15/50) | 5/17 | 10/16 | 0/17 |
| extra_chirp_2s_30deg_dist30 | 34% (17/50) | 6/17 | 8/16 | 3/17 |
| extra_no_noise_no_heading | 36% (18/50) | 6/17 | 9/16 | 3/17 |

## Long-turn starts (> +15 deg): turning

Turn before push = rotation toward the needed direction before the box has made 0.20 m of progress (the whole episode if it never does). Needed = rotation that aims the push face at the target.

| policy | needed (mean) | turn before push (mean, min to max) | total turn (mean) | reached the push | success |
|---|---|---|---|---|---|
| d2_exact | 55 | 42 (15 to 112) | 102 | 16/17 | 5/17 |
| d1 | 55 | 65 (19 to 204) | 182 | 16/17 | 1/17 |
| chirp_2s_30deg | 55 | 57 (13 to 152) | 120 | 15/17 | 2/17 |
| chirp_2s_10deg | 55 | 50 (18 to 129) | 122 | 13/17 | 2/17 |
| chirp_0.5s_30deg | 55 | 36 (-16 to 106) | 101 | 14/17 | 0/17 |
| chirp_4s_60deg | 55 | 59 (11 to 155) | 129 | 12/17 | 0/17 |
| extra_chirp_2s_30deg_dist30 | 55 | 53 (17 to 124) | 115 | 14/17 | 3/17 |
| extra_no_noise_no_heading | 55 | 57 (13 to 215) | 136 | 16/17 | 3/17 |

## Failure modes and idling (all 50 starts)

Idle = steps where both ducks are commanded below 0.05 m/s. Still = the box ends less than 0.1 m from where it started.

Both touch = steps where both ducks touch the box. Lazy = episodes where one duck has under 20% of the box contact time.

| policy | falls | box lost | overshoot | timeouts | push share A (mean) | both touch | lazy duck | idle steps | box path (m, mean) | still | mean steps | monitor flags (episodes) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d2_exact | 5/50 | 2/50 | 1/50 | 6/50 | 51% | 94% | 0/50 | 14.6% | 0.88 | 0/50 | 45 | bad_part_duck_a 6, bad_part_duck_b 3, contact_share 17, edge 1, fall_duck_a 4, fall_duck_b 2, reward_vs_dist 2 |
| d1 | 2/50 | 0/50 | 4/50 | 18/50 | 48% | 92% | 0/50 | 20.6% | 1.12 | 0/50 | 57 | bad_part_duck_a 4, contact_share 16, fall_duck_a 3, fall_duck_b 1, reward_vs_dist 9 |
| chirp_2s_30deg | 3/50 | 1/50 | 21/50 | 29/50 | 55% | 84% | 1/50 | 21.2% | 1.48 | 0/50 | 74 | bad_part_duck_a 7, bad_part_duck_b 5, contact_share 21, edge 1, fall_duck_a 4, fall_duck_b 2, reward_vs_dist 8 |
| chirp_2s_10deg | 5/50 | 3/50 | 17/50 | 21/50 | 56% | 88% | 0/50 | 18.7% | 1.33 | 0/50 | 67 | bad_part_duck_a 5, bad_part_duck_b 6, contact_share 26, fall_duck_a 7, fall_duck_b 1, reward_vs_dist 12 |
| chirp_0.5s_30deg | 5/50 | 1/50 | 22/50 | 25/50 | 56% | 90% | 0/50 | 20.1% | 1.43 | 0/50 | 70 | bad_part_duck_a 1, bad_part_duck_b 6, contact_share 15, fall_duck_a 2, fall_duck_b 3, reward_vs_dist 11 |
| chirp_4s_60deg | 3/50 | 2/50 | 27/50 | 30/50 | 54% | 89% | 0/50 | 24.8% | 1.55 | 0/50 | 76 | bad_part_duck_a 6, bad_part_duck_b 3, contact_share 18, fall_duck_a 2, fall_duck_b 2, reward_vs_dist 12, spin 1 |
| extra_chirp_2s_30deg_dist30 | 5/50 | 4/50 | 22/50 | 24/50 | 55% | 93% | 0/50 | 23.1% | 1.45 | 0/50 | 70 | bad_part_duck_a 4, bad_part_duck_b 3, contact_share 15, fall_duck_a 3, fall_duck_b 4, reward_vs_dist 10 |
| extra_no_noise_no_heading | 3/50 | 1/50 | 24/50 | 28/50 | 53% | 89% | 0/50 | 20.6% | 1.52 | 0/50 | 74 | bad_part_duck_a 8, bad_part_duck_b 5, contact_share 26, fall_duck_a 4, fall_duck_b 1, reward_vs_dist 11 |
