# Rendezvous evaluation: runs/d2-rendezvous-r7-long-payout/s2/checkpoints/ckpt_3002368.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 69.5% (62.8% to 75.5%) | 31.1 | 4.3 / 2.3 | 9.7 / 2.5 | 566 (36) | 152 (23) | 7 |
| uniform | 160 | 67.5% (59.9% to 74.3%) | 30.0 | 4.2 / 2.4 | 9.0 / 2.5 | 407 (29) | 110 (15) | 5 |
| near_symmetric | 20 | 80.0% (58.4% to 91.9%) | 34.3 | 2.9 / 2.1 | 5.7 / 1.9 | 3 (2) | 6 (2) | 0 |
| wrong_side | 20 | 75.0% (53.1% to 88.8%) | 35.7 | 6.6 / 2.3 | 19.0 / 3.4 | 156 (5) | 36 (6) | 2 |
| target_side_1+ | 150 | 70.0% (62.2% to 76.8%) | 33.1 | 4.4 / 2.2 | 9.6 / 2.6 | 463 (25) | 85 (16) | 6 |
| pairing_margin<5cm | 58 | 60.3% (47.5% to 71.9%) | 33.9 | 4.7 / 2.4 | 8.3 / 2.5 | 73 (9) | 64 (14) | 2 |

Arrived episodes only: position error 2.1 cm, heading error 3.3 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 80.0% (73.9% to 85.0%) | 127 of 139 (91.4%) | 33 of 61 |
| uniform | 160 | 79.4% (72.5% to 84.9%) | 99 of 108 (91.7%) | 28 of 52 |
| near_symmetric | 20 | 90.0% (69.9% to 97.2%) | 14 of 16 (87.5%) | 4 of 4 |
| wrong_side | 20 | 75.0% (53.1% to 88.8%) | 14 of 15 (93.3%) | 1 of 5 |
| target_side_1+ | 150 | 80.7% (73.6% to 86.2%) | 97 of 105 (92.4%) | 24 of 45 |
| pairing_margin<5cm | 58 | 77.6% (65.3% to 86.4%) | 30 of 35 (85.7%) | 15 of 23 |

Push endings, all starts: fall 8, success 160, timeout 32.

Wall time 59.0 s.
