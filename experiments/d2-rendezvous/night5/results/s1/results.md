# Rendezvous evaluation: runs/d2-rendezvous-night5/s1/best.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 64.5% (57.7% to 70.8%) | 37.8 | 6.6 / 2.2 | 21.2 / 3.9 | 260 (27) | 234 (18) | 0 |
| uniform | 160 | 69.4% (61.8% to 76.0%) | 36.9 | 4.9 / 2.1 | 17.1 / 3.8 | 252 (22) | 182 (15) | 0 |
| near_symmetric | 20 | 50.0% (29.9% to 70.1%) | 42.0 | 12.0 / 2.5 | 33.1 / 3.6 | 1 (1) | 0 (0) | 0 |
| wrong_side | 20 | 40.0% (21.9% to 61.3%) | 45.0 | 14.4 / 2.8 | 41.9 / 5.1 | 7 (4) | 52 (3) | 0 |
| target_side_1+ | 150 | 59.3% (51.3% to 66.9%) | 39.8 | 7.9 / 2.2 | 25.6 / 3.9 | 164 (18) | 186 (13) | 0 |
| pairing_margin<5cm | 58 | 48.3% (35.9% to 60.8%) | 41.5 | 11.7 / 2.5 | 37.4 / 4.9 | 30 (6) | 222 (16) | 0 |

Arrived episodes only: position error 1.9 cm, heading error 3.7 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 71.5% (64.9% to 77.3%) | 115 of 129 (89.1%) | 28 of 71 |
| uniform | 160 | 72.5% (65.1% to 78.8%) | 98 of 111 (88.3%) | 18 of 49 |
| near_symmetric | 20 | 70.0% (48.1% to 85.5%) | 9 of 10 (90.0%) | 5 of 10 |
| wrong_side | 20 | 65.0% (43.3% to 81.9%) | 8 of 8 (100.0%) | 5 of 12 |
| target_side_1+ | 150 | 68.0% (60.2% to 74.9%) | 79 of 89 (88.8%) | 23 of 61 |
| pairing_margin<5cm | 58 | 55.2% (42.5% to 67.3%) | 25 of 28 (89.3%) | 7 of 30 |

Push endings, all starts: box_lost 1, box_tipped 2, fall 3, success 143, timeout 51.

Wall time 80.7 s.
