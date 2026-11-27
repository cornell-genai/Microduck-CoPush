# Rendezvous evaluation: runs/d2-rendezvous-r3-heading-bonus/s1/best.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 0.5% (0.1% to 2.8%) | 15.0 | 51.3 / 54.9 | 50.8 / 30.6 | 2463 (94) | 564 (49) | 53 |
| uniform | 160 | 0.6% (0.1% to 3.5%) | 15.0 | 51.1 / 53.3 | 49.6 / 29.6 | 2024 (79) | 393 (32) | 45 |
| near_symmetric | 20 | 0.0% (0.0% to 16.1%) | n/a | 41.5 / 47.1 | 41.7 / 25.2 | 439 (15) | 141 (12) | 8 |
| wrong_side | 20 | 0.0% (0.0% to 16.1%) | n/a | 62.6 / 61.5 | 69.7 / 50.2 | 0 (0) | 30 (5) | 0 |
| target_side_1+ | 150 | 0.0% (0.0% to 2.5%) | n/a | 54.3 / 57.8 | 55.4 / 36.8 | 1543 (60) | 356 (36) | 34 |
| pairing_margin<5cm | 58 | 0.0% (0.0% to 6.2%) | n/a | 45.7 / 46.3 | 49.2 / 34.6 | 879 (34) | 355 (29) | 19 |

Arrived episodes only: position error 2.2 cm, heading error 7.3 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 1.5% (0.5% to 4.3%) | 1 of 1 (100.0%) | 2 of 199 |
| uniform | 160 | 1.2% (0.3% to 4.4%) | 1 of 1 (100.0%) | 1 of 159 |
| near_symmetric | 20 | 5.0% (0.9% to 23.6%) | 0 of 0 (n/a) | 1 of 20 |
| wrong_side | 20 | 0.0% (0.0% to 16.1%) | 0 of 0 (n/a) | 0 of 20 |
| target_side_1+ | 150 | 0.7% (0.1% to 3.7%) | 0 of 0 (n/a) | 1 of 150 |
| pairing_margin<5cm | 58 | 1.7% (0.3% to 9.1%) | 0 of 0 (n/a) | 1 of 58 |

Push endings, all starts: box_lost 114, box_tipped 1, fall 39, success 3, timeout 43.

Wall time 49.7 s.
