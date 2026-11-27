# Rendezvous evaluation: runs/d2-rendezvous-r7-long-payout/s1/checkpoints/ckpt_3002368.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 86.0% (80.5% to 90.1%) | 31.9 | 2.5 / 1.8 | 7.0 / 3.0 | 539 (44) | 108 (18) | 4 |
| uniform | 160 | 86.2% (80.1% to 90.7%) | 30.7 | 2.5 / 1.8 | 6.7 / 3.2 | 495 (37) | 83 (15) | 4 |
| near_symmetric | 20 | 75.0% (53.1% to 88.8%) | 34.9 | 2.8 / 1.8 | 10.2 / 2.7 | 34 (3) | 17 (2) | 0 |
| wrong_side | 20 | 95.0% (76.4% to 99.1%) | 38.0 | 2.6 / 1.9 | 5.9 / 2.6 | 10 (4) | 8 (1) | 0 |
| target_side_1+ | 150 | 86.0% (79.5% to 90.7%) | 33.8 | 2.6 / 1.9 | 6.9 / 2.8 | 321 (29) | 93 (14) | 2 |
| pairing_margin<5cm | 58 | 84.5% (73.1% to 91.6%) | 35.0 | 2.8 / 1.8 | 7.2 / 3.1 | 72 (12) | 83 (12) | 0 |

Arrived episodes only: position error 1.8 cm, heading error 3.6 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 84.0% (78.3% to 88.4%) | 152 of 172 (88.4%) | 16 of 28 |
| uniform | 160 | 83.8% (77.3% to 88.7%) | 121 of 138 (87.7%) | 13 of 22 |
| near_symmetric | 20 | 85.0% (64.0% to 94.8%) | 14 of 15 (93.3%) | 3 of 5 |
| wrong_side | 20 | 85.0% (64.0% to 94.8%) | 17 of 19 (89.5%) | 0 of 1 |
| target_side_1+ | 150 | 84.0% (77.3% to 89.0%) | 114 of 129 (88.4%) | 12 of 21 |
| pairing_margin<5cm | 58 | 84.5% (73.1% to 91.6%) | 44 of 49 (89.8%) | 5 of 9 |

Push endings, all starts: box_tipped 3, fall 4, success 168, timeout 25.

Wall time 52.2 s.
