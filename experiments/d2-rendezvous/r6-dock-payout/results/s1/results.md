# Rendezvous evaluation: runs/d2-rendezvous-r6-dock-payout/s1/best.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 87.0% (81.6% to 91.0%) | 33.3 | 2.6 / 2.0 | 5.9 / 2.6 | 335 (48) | 117 (19) | 4 |
| uniform | 160 | 86.9% (80.8% to 91.3%) | 32.2 | 2.5 / 2.0 | 5.4 / 2.6 | 306 (44) | 91 (16) | 4 |
| near_symmetric | 20 | 90.0% (69.9% to 97.2%) | 37.8 | 2.0 / 2.0 | 3.5 / 1.9 | 2 (1) | 0 (0) | 0 |
| wrong_side | 20 | 85.0% (64.0% to 94.8%) | 37.5 | 3.9 / 2.2 | 12.1 / 2.7 | 27 (3) | 26 (3) | 0 |
| target_side_1+ | 150 | 85.3% (78.8% to 90.1%) | 35.5 | 2.6 / 2.1 | 6.1 / 2.5 | 223 (30) | 99 (14) | 4 |
| pairing_margin<5cm | 58 | 86.2% (75.1% to 92.8%) | 36.5 | 2.8 / 2.1 | 6.3 / 2.7 | 40 (10) | 95 (13) | 0 |

Arrived episodes only: position error 1.9 cm, heading error 3.4 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 90.0% (85.1% to 93.4%) | 163 of 174 (93.7%) | 17 of 26 |
| uniform | 160 | 91.2% (85.8% to 94.7%) | 131 of 139 (94.2%) | 15 of 21 |
| near_symmetric | 20 | 90.0% (69.9% to 97.2%) | 16 of 18 (88.9%) | 2 of 2 |
| wrong_side | 20 | 80.0% (58.4% to 91.9%) | 16 of 17 (94.1%) | 0 of 3 |
| target_side_1+ | 150 | 88.7% (82.6% to 92.8%) | 119 of 128 (93.0%) | 14 of 22 |
| pairing_margin<5cm | 58 | 84.5% (73.1% to 91.6%) | 44 of 50 (88.0%) | 5 of 8 |

Push endings, all starts: box_tipped 1, fall 1, success 180, timeout 18.

Wall time 53.6 s.
