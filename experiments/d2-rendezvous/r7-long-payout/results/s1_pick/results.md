# Rendezvous evaluation: runs/d2-rendezvous-r7-long-payout/s1/best.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 86.0% (80.5% to 90.1%) | 32.3 | 3.1 / 1.9 | 8.3 / 3.2 | 403 (51) | 161 (16) | 2 |
| uniform | 160 | 90.6% (85.1% to 94.2%) | 31.5 | 2.5 / 1.9 | 6.3 / 3.2 | 334 (39) | 148 (13) | 1 |
| near_symmetric | 20 | 60.0% (38.7% to 78.1%) | 35.8 | 5.8 / 2.1 | 21.5 / 5.2 | 31 (7) | 0 (0) | 1 |
| wrong_side | 20 | 75.0% (53.1% to 88.8%) | 37.2 | 4.4 / 2.1 | 11.5 / 2.4 | 38 (5) | 13 (3) | 0 |
| target_side_1+ | 150 | 84.0% (77.3% to 89.0%) | 34.5 | 3.3 / 2.0 | 9.3 / 3.1 | 348 (40) | 138 (13) | 2 |
| pairing_margin<5cm | 58 | 74.1% (61.6% to 83.7%) | 35.5 | 4.2 / 2.0 | 13.0 / 3.8 | 134 (16) | 99 (12) | 1 |

Arrived episodes only: position error 1.8 cm, heading error 3.5 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 86.0% (80.5% to 90.1%) | 160 of 172 (93.0%) | 12 of 28 |
| uniform | 160 | 90.0% (84.4% to 93.8%) | 135 of 145 (93.1%) | 9 of 15 |
| near_symmetric | 20 | 60.0% (38.7% to 78.1%) | 11 of 12 (91.7%) | 1 of 8 |
| wrong_side | 20 | 80.0% (58.4% to 91.9%) | 14 of 15 (93.3%) | 2 of 5 |
| target_side_1+ | 150 | 85.3% (78.8% to 90.1%) | 118 of 126 (93.7%) | 10 of 24 |
| pairing_margin<5cm | 58 | 74.1% (61.6% to 83.7%) | 39 of 43 (90.7%) | 4 of 15 |

Push endings, all starts: box_tipped 2, fall 2, success 172, timeout 24.

Wall time 53.2 s.
