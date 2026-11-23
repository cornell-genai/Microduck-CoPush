# Rendezvous evaluation: runs/d2-rendezvous-r5-bc-warmstart/bc/bc.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 44.0% (37.3% to 50.9%) | 38.8 | 6.2 / 2.5 | 36.1 / 8.3 | 599 (110) | 251 (23) | 1 |
| uniform | 160 | 50.6% (43.0% to 58.3%) | 38.9 | 5.6 / 2.3 | 28.6 / 7.7 | 534 (93) | 223 (19) | 1 |
| near_symmetric | 20 | 30.0% (14.5% to 51.9%) | 36.0 | 7.5 / 9.8 | 63.8 / 62.9 | 34 (8) | 6 (1) | 0 |
| wrong_side | 20 | 5.0% (0.9% to 23.6%) | 49.0 | 10.0 / 11.1 | 68.2 / 86.5 | 31 (9) | 22 (3) | 0 |
| target_side_1+ | 150 | 30.0% (23.2% to 37.8%) | 43.4 | 7.5 / 2.7 | 45.1 / 10.8 | 506 (81) | 194 (18) | 1 |
| pairing_margin<5cm | 58 | 25.9% (16.3% to 38.4%) | 40.6 | 8.5 / 3.3 | 52.2 / 13.7 | 168 (26) | 212 (18) | 0 |

Arrived episodes only: position error 1.8 cm, heading error 6.0 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 56.0% (49.1% to 62.7%) | 84 of 88 (95.5%) | 28 of 112 |
| uniform | 160 | 62.5% (54.8% to 69.6%) | 77 of 81 (95.1%) | 23 of 79 |
| near_symmetric | 20 | 35.0% (18.1% to 56.7%) | 6 of 6 (100.0%) | 1 of 14 |
| wrong_side | 20 | 25.0% (11.2% to 46.9%) | 1 of 1 (100.0%) | 4 of 19 |
| target_side_1+ | 150 | 46.7% (38.9% to 54.6%) | 44 of 45 (97.8%) | 26 of 105 |
| pairing_margin<5cm | 58 | 37.9% (26.6% to 50.8%) | 15 of 15 (100.0%) | 7 of 43 |

Push endings, all starts: box_lost 1, box_tipped 3, fall 6, success 112, timeout 78.

Wall time 133.1 s.
