# Rendezvous evaluation: runs/d2-rendezvous-r7-long-payout/s1/checkpoints/ckpt_2000000.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 84.5% (78.8% to 88.9%) | 33.3 | 2.8 / 2.0 | 7.5 / 2.6 | 528 (42) | 179 (22) | 2 |
| uniform | 160 | 85.6% (79.4% to 90.2%) | 32.3 | 2.6 / 1.9 | 6.7 / 2.6 | 490 (36) | 153 (19) | 1 |
| near_symmetric | 20 | 80.0% (58.4% to 91.9%) | 37.5 | 2.5 / 2.2 | 6.9 / 2.7 | 7 (4) | 0 (0) | 0 |
| wrong_side | 20 | 80.0% (58.4% to 91.9%) | 37.6 | 4.1 / 1.9 | 14.3 / 2.2 | 31 (2) | 26 (3) | 1 |
| target_side_1+ | 150 | 82.7% (75.8% to 87.9%) | 35.5 | 2.9 / 2.0 | 8.3 / 2.5 | 396 (29) | 168 (17) | 2 |
| pairing_margin<5cm | 58 | 74.1% (61.6% to 83.7%) | 36.3 | 3.2 / 2.1 | 8.6 / 2.7 | 95 (18) | 136 (17) | 1 |

Arrived episodes only: position error 1.8 cm, heading error 3.2 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 87.0% (81.6% to 91.0%) | 157 of 169 (92.9%) | 17 of 31 |
| uniform | 160 | 86.9% (80.8% to 91.3%) | 125 of 137 (91.2%) | 14 of 23 |
| near_symmetric | 20 | 90.0% (69.9% to 97.2%) | 16 of 16 (100.0%) | 2 of 4 |
| wrong_side | 20 | 85.0% (64.0% to 94.8%) | 16 of 16 (100.0%) | 1 of 4 |
| target_side_1+ | 150 | 86.0% (79.5% to 90.7%) | 115 of 124 (92.7%) | 14 of 26 |
| pairing_margin<5cm | 58 | 84.5% (73.1% to 91.6%) | 39 of 43 (90.7%) | 10 of 15 |

Push endings, all starts: box_tipped 2, fall 3, success 174, timeout 21.

Wall time 53.1 s.
