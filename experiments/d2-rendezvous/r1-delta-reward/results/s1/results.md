# Rendezvous evaluation: runs/d2-rendezvous-r1-delta-reward/s1/model.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 0.0% (0.0% to 1.9%) | n/a | 49.9 / 48.0 | 65.7 / 48.2 | 89 (18) | 23 (5) | 0 |
| uniform | 160 | 0.0% (0.0% to 2.3%) | n/a | 49.2 / 47.6 | 64.7 / 48.3 | 65 (14) | 14 (2) | 0 |
| near_symmetric | 20 | 0.0% (0.0% to 16.1%) | n/a | 53.7 / 52.7 | 78.9 / 51.9 | 4 (1) | 0 (0) | 0 |
| wrong_side | 20 | 0.0% (0.0% to 16.1%) | n/a | 51.0 / 51.0 | 60.6 / 36.8 | 20 (3) | 9 (3) | 0 |
| target_side_1+ | 150 | 0.0% (0.0% to 2.5%) | n/a | 51.2 / 49.9 | 66.4 / 44.0 | 85 (17) | 23 (5) | 0 |
| pairing_margin<5cm | 58 | 0.0% (0.0% to 6.2%) | n/a | 54.2 / 54.1 | 67.7 / 50.0 | 12 (3) | 19 (3) | 0 |

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 0.0% (0.0% to 1.9%) | 0 of 0 (n/a) | 0 of 200 |
| uniform | 160 | 0.0% (0.0% to 2.3%) | 0 of 0 (n/a) | 0 of 160 |
| near_symmetric | 20 | 0.0% (0.0% to 16.1%) | 0 of 0 (n/a) | 0 of 20 |
| wrong_side | 20 | 0.0% (0.0% to 16.1%) | 0 of 0 (n/a) | 0 of 20 |
| target_side_1+ | 150 | 0.0% (0.0% to 2.5%) | 0 of 0 (n/a) | 0 of 150 |
| pairing_margin<5cm | 58 | 0.0% (0.0% to 6.2%) | 0 of 0 (n/a) | 0 of 58 |

Push endings, all starts: box_lost 148, fall 2, timeout 50.

Wall time 129.2 s.
