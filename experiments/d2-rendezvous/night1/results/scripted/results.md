# Rendezvous evaluation: scripted

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 48.0% (41.2% to 54.9%) | 38.5 | 4.9 / 2.3 | 26.9 / 7.8 | 494 (120) | 150 (21) | 1 |
| uniform | 160 | 55.0% (47.3% to 62.5%) | 38.5 | 4.4 / 2.1 | 21.2 / 6.9 | 433 (104) | 139 (18) | 1 |
| near_symmetric | 20 | 30.0% (14.5% to 51.9%) | 35.5 | 6.8 / 2.8 | 51.5 / 11.3 | 37 (8) | 0 (0) | 0 |
| wrong_side | 20 | 10.0% (2.8% to 30.1%) | 47.0 | 6.8 / 6.4 | 47.9 / 30.3 | 24 (8) | 11 (3) | 0 |
| target_side_1+ | 150 | 32.7% (25.7% to 40.5%) | 43.4 | 5.9 / 2.7 | 33.7 / 9.2 | 391 (84) | 109 (16) | 1 |
| pairing_margin<5cm | 58 | 31.0% (20.6% to 43.8%) | 39.4 | 6.8 / 2.9 | 41.0 / 9.7 | 114 (27) | 112 (14) | 0 |

Arrived episodes only: position error 1.8 cm, heading error 5.7 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 65.0% (58.2% to 71.3%) | 91 of 96 (94.8%) | 39 of 104 |
| uniform | 160 | 70.0% (62.5% to 76.6%) | 83 of 88 (94.3%) | 29 of 72 |
| near_symmetric | 20 | 45.0% (25.8% to 65.8%) | 6 of 6 (100.0%) | 3 of 14 |
| wrong_side | 20 | 45.0% (25.8% to 65.8%) | 2 of 2 (100.0%) | 7 of 18 |
| target_side_1+ | 150 | 55.3% (47.3% to 63.1%) | 46 of 49 (93.9%) | 37 of 101 |
| pairing_margin<5cm | 58 | 51.7% (39.2% to 64.1%) | 18 of 18 (100.0%) | 12 of 40 |

Push endings, all starts: box_tipped 2, fall 5, success 130, timeout 63.

Wall time 56.5 s.
