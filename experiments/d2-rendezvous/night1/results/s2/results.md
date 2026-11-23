# Rendezvous evaluation: runs/d2-rendezvous-night1/s2/model.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 0.0% (0.0% to 1.9%) | n/a | 49.1 / 47.0 | 68.5 / 61.7 | 82 (18) | 21 (7) | 0 |
| uniform | 160 | 0.0% (0.0% to 2.3%) | n/a | 48.2 / 46.2 | 65.7 / 58.4 | 74 (15) | 12 (4) | 0 |
| near_symmetric | 20 | 0.0% (0.0% to 16.1%) | n/a | 52.0 / 49.0 | 79.0 / 69.4 | 4 (1) | 0 (0) | 0 |
| wrong_side | 20 | 0.0% (0.0% to 16.1%) | n/a | 53.3 / 49.4 | 80.1 / 77.4 | 4 (2) | 9 (3) | 0 |
| target_side_1+ | 150 | 0.0% (0.0% to 2.5%) | n/a | 50.7 / 48.4 | 70.1 / 61.1 | 66 (15) | 13 (6) | 0 |
| pairing_margin<5cm | 58 | 0.0% (0.0% to 6.2%) | n/a | 53.3 / 49.4 | 72.9 / 64.6 | 19 (4) | 6 (2) | 0 |

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 0.5% (0.1% to 2.8%) | 0 of 0 (n/a) | 1 of 200 |
| uniform | 160 | 0.6% (0.1% to 3.5%) | 0 of 0 (n/a) | 1 of 160 |
| near_symmetric | 20 | 0.0% (0.0% to 16.1%) | 0 of 0 (n/a) | 0 of 20 |
| wrong_side | 20 | 0.0% (0.0% to 16.1%) | 0 of 0 (n/a) | 0 of 20 |
| target_side_1+ | 150 | 0.7% (0.1% to 3.7%) | 0 of 0 (n/a) | 1 of 150 |
| pairing_margin<5cm | 58 | 0.0% (0.0% to 6.2%) | 0 of 0 (n/a) | 0 of 58 |

Push endings, all starts: box_lost 126, fall 2, success 1, timeout 71.

Wall time 123.5 s.
