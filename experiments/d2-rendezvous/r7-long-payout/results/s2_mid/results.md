# Rendezvous evaluation: runs/d2-rendezvous-r7-long-payout/s2/checkpoints/ckpt_2000000.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 78.5% (72.3% to 83.6%) | 33.0 | 3.6 / 2.3 | 7.8 / 3.3 | 258 (33) | 97 (21) | 2 |
| uniform | 160 | 77.5% (70.4% to 83.3%) | 32.1 | 3.7 / 2.3 | 8.1 / 3.3 | 236 (28) | 80 (18) | 2 |
| near_symmetric | 20 | 80.0% (58.4% to 91.9%) | 35.3 | 3.3 / 2.4 | 6.0 / 3.7 | 21 (4) | 0 (0) | 0 |
| wrong_side | 20 | 85.0% (64.0% to 94.8%) | 37.5 | 3.1 / 2.3 | 7.8 / 2.6 | 1 (1) | 17 (3) | 0 |
| target_side_1+ | 150 | 77.3% (70.0% to 83.3%) | 35.3 | 3.7 / 2.2 | 8.2 / 3.2 | 197 (23) | 78 (17) | 2 |
| pairing_margin<5cm | 58 | 75.9% (63.5% to 85.0%) | 37.1 | 4.3 / 2.1 | 9.0 / 3.2 | 82 (15) | 83 (16) | 1 |

Arrived episodes only: position error 2.1 cm, heading error 4.3 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 86.5% (81.1% to 90.6%) | 149 of 157 (94.9%) | 24 of 43 |
| uniform | 160 | 85.6% (79.4% to 90.2%) | 116 of 124 (93.5%) | 21 of 36 |
| near_symmetric | 20 | 85.0% (64.0% to 94.8%) | 16 of 16 (100.0%) | 1 of 4 |
| wrong_side | 20 | 95.0% (76.4% to 99.1%) | 17 of 17 (100.0%) | 2 of 3 |
| target_side_1+ | 150 | 85.3% (78.8% to 90.1%) | 109 of 116 (94.0%) | 19 of 34 |
| pairing_margin<5cm | 58 | 84.5% (73.1% to 91.6%) | 42 of 44 (95.5%) | 7 of 14 |

Push endings, all starts: box_tipped 2, fall 4, success 173, timeout 21.

Wall time 57.3 s.
