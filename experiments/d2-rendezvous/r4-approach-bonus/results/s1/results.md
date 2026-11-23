# Rendezvous evaluation: runs/d2-rendezvous-r4-approach-bonus/s1/best.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 0.0% (0.0% to 1.9%) | n/a | 37.6 / 35.9 | 38.2 / 18.0 | 2742 (111) | 152 (21) | 6 |
| uniform | 160 | 0.0% (0.0% to 2.3%) | n/a | 39.1 / 37.9 | 33.2 / 17.0 | 2116 (86) | 69 (13) | 5 |
| near_symmetric | 20 | 0.0% (0.0% to 16.1%) | n/a | 29.6 / 28.0 | 53.1 / 14.1 | 497 (16) | 40 (4) | 1 |
| wrong_side | 20 | 0.0% (0.0% to 16.1%) | n/a | 34.2 / 29.6 | 63.2 / 47.2 | 129 (9) | 43 (4) | 0 |
| target_side_1+ | 150 | 0.0% (0.0% to 2.5%) | n/a | 39.9 / 38.5 | 43.6 / 22.3 | 1679 (79) | 94 (13) | 4 |
| pairing_margin<5cm | 58 | 0.0% (0.0% to 6.2%) | n/a | 36.6 / 34.1 | 48.5 / 25.4 | 1047 (40) | 102 (13) | 3 |

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 5.0% (2.7% to 9.0%) | 0 of 0 (n/a) | 10 of 200 |
| uniform | 160 | 4.4% (2.1% to 8.8%) | 0 of 0 (n/a) | 7 of 160 |
| near_symmetric | 20 | 15.0% (5.2% to 36.0%) | 0 of 0 (n/a) | 3 of 20 |
| wrong_side | 20 | 0.0% (0.0% to 16.1%) | 0 of 0 (n/a) | 0 of 20 |
| target_side_1+ | 150 | 3.3% (1.4% to 7.6%) | 0 of 0 (n/a) | 5 of 150 |
| pairing_margin<5cm | 58 | 6.9% (2.7% to 16.4%) | 0 of 0 (n/a) | 4 of 58 |

Push endings, all starts: box_lost 68, box_tipped 2, fall 11, success 10, timeout 109.

Wall time 78.4 s.
