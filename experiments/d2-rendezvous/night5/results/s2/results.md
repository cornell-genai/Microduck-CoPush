# Rendezvous evaluation: runs/d2-rendezvous-night5/s2/best.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 52.0% (45.1% to 58.8%) | 37.9 | 6.6 / 2.5 | 29.7 / 5.8 | 562 (80) | 244 (18) | 1 |
| uniform | 160 | 58.8% (51.0% to 66.1%) | 37.7 | 5.5 / 2.4 | 23.5 / 5.4 | 499 (69) | 202 (16) | 1 |
| near_symmetric | 20 | 30.0% (14.5% to 51.9%) | 36.3 | 9.7 / 3.3 | 53.1 / 11.2 | 31 (6) | 0 (0) | 0 |
| wrong_side | 20 | 20.0% (8.1% to 41.6%) | 46.5 | 12.3 / 4.4 | 55.6 / 10.7 | 32 (5) | 42 (2) | 0 |
| target_side_1+ | 150 | 39.3% (31.9% to 47.3%) | 41.5 | 7.9 / 2.6 | 36.7 / 6.8 | 395 (59) | 183 (13) | 1 |
| pairing_margin<5cm | 58 | 32.8% (22.1% to 45.6%) | 39.6 | 11.3 / 2.8 | 47.1 / 9.3 | 166 (23) | 215 (14) | 0 |

Arrived episodes only: position error 2.1 cm, heading error 5.0 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 62.5% (55.6% to 68.9%) | 96 of 104 (92.3%) | 29 of 96 |
| uniform | 160 | 68.8% (61.2% to 75.4%) | 86 of 94 (91.5%) | 24 of 66 |
| near_symmetric | 20 | 45.0% (25.8% to 65.8%) | 6 of 6 (100.0%) | 3 of 14 |
| wrong_side | 20 | 30.0% (14.5% to 51.9%) | 4 of 4 (100.0%) | 2 of 16 |
| target_side_1+ | 150 | 55.3% (47.3% to 63.1%) | 56 of 59 (94.9%) | 27 of 91 |
| pairing_margin<5cm | 58 | 48.3% (35.9% to 60.8%) | 19 of 19 (100.0%) | 9 of 39 |

Push endings, all starts: box_tipped 1, fall 1, success 125, timeout 73.

Wall time 99.0 s.
