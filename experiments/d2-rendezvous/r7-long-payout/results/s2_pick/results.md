# Rendezvous evaluation: runs/d2-rendezvous-r7-long-payout/s2/best.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 79.5% (73.4% to 84.5%) | 31.9 | 3.4 / 2.1 | 7.1 / 2.5 | 325 (41) | 102 (18) | 4 |
| uniform | 160 | 80.0% (73.1% to 85.5%) | 31.0 | 3.2 / 2.1 | 7.4 / 2.6 | 282 (34) | 80 (15) | 3 |
| near_symmetric | 20 | 85.0% (64.0% to 94.8%) | 35.7 | 4.0 / 2.1 | 3.4 / 2.3 | 5 (3) | 0 (0) | 0 |
| wrong_side | 20 | 70.0% (48.1% to 85.5%) | 35.9 | 4.6 / 2.1 | 8.2 / 2.5 | 38 (4) | 22 (3) | 1 |
| target_side_1+ | 150 | 78.0% (70.7% to 83.9%) | 34.1 | 3.7 / 2.2 | 8.1 / 2.4 | 232 (25) | 59 (13) | 3 |
| pairing_margin<5cm | 58 | 81.0% (69.1% to 89.1%) | 34.8 | 3.8 / 2.1 | 8.4 / 2.6 | 60 (12) | 66 (13) | 0 |

Arrived episodes only: position error 2.0 cm, heading error 3.5 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 85.0% (79.4% to 89.3%) | 148 of 159 (93.1%) | 22 of 41 |
| uniform | 160 | 85.6% (79.4% to 90.2%) | 120 of 128 (93.8%) | 17 of 32 |
| near_symmetric | 20 | 80.0% (58.4% to 91.9%) | 15 of 17 (88.2%) | 1 of 3 |
| wrong_side | 20 | 85.0% (64.0% to 94.8%) | 13 of 14 (92.9%) | 4 of 6 |
| target_side_1+ | 150 | 84.7% (78.0% to 89.6%) | 109 of 117 (93.2%) | 18 of 33 |
| pairing_margin<5cm | 58 | 86.2% (75.1% to 92.8%) | 44 of 47 (93.6%) | 6 of 11 |

Push endings, all starts: box_tipped 1, fall 3, success 170, timeout 26.

Wall time 58.8 s.
