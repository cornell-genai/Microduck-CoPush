# Rendezvous evaluation: runs/d2-rendezvous-night2/s1/model.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 0.5% (0.1% to 2.8%) | 22.0 | 29.5 / 27.2 | 78.7 / 73.4 | 4166 (175) | 244 (43) | 84 |
| uniform | 160 | 0.0% (0.0% to 2.3%) | n/a | 30.0 / 28.0 | 80.6 / 76.9 | 3144 (139) | 130 (28) | 63 |
| near_symmetric | 20 | 5.0% (0.9% to 23.6%) | 22.0 | 29.2 / 24.1 | 54.6 / 38.7 | 515 (17) | 69 (8) | 11 |
| wrong_side | 20 | 0.0% (0.0% to 16.1%) | n/a | 25.6 / 25.2 | 87.8 / 104.8 | 507 (19) | 45 (7) | 10 |
| target_side_1+ | 150 | 0.0% (0.0% to 2.5%) | n/a | 29.5 / 27.0 | 81.2 / 79.4 | 3049 (133) | 141 (29) | 64 |
| pairing_margin<5cm | 58 | 1.7% (0.3% to 9.1%) | 22.0 | 28.0 / 24.1 | 64.9 / 40.8 | 1490 (54) | 122 (22) | 30 |

Arrived episodes only: position error 1.6 cm, heading error 3.8 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 3.5% (1.7% to 7.0%) | 0 of 1 (0.0%) | 7 of 199 |
| uniform | 160 | 3.1% (1.3% to 7.1%) | 0 of 0 (n/a) | 5 of 160 |
| near_symmetric | 20 | 5.0% (0.9% to 23.6%) | 0 of 1 (0.0%) | 1 of 19 |
| wrong_side | 20 | 5.0% (0.9% to 23.6%) | 0 of 0 (n/a) | 1 of 20 |
| target_side_1+ | 150 | 4.0% (1.8% to 8.5%) | 0 of 0 (n/a) | 6 of 150 |
| pairing_margin<5cm | 58 | 8.6% (3.7% to 18.6%) | 0 of 1 (0.0%) | 5 of 57 |

Push endings, all starts: box_lost 21, box_tipped 10, fall 63, success 7, timeout 99.

Wall time 114.1 s.
