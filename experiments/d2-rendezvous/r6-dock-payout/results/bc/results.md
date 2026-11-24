# Rendezvous evaluation: runs/d2-rendezvous-r6-dock-payout/bc/bc.zip

200 starts from `experiments/test_sets/rendezvous_large.json`, deterministic, seed 10000 + i. Handoff when both ducks are within 3 cm and 15 deg of their spots and upright, or at 50 steps; then the push policy `runs/d2-steering-night5/l2-s2/model.zip` for 100 steps.

## Rendezvous

| starts | n | arrived (95% interval) | mean steps to arrive | position error at handoff, mean / median (cm) | heading error at handoff, mean / median (deg) | duck-box hits (episodes) | duck-duck hits (episodes) | falls |
|---|---|---|---|---|---|---|---|---|
| all | 200 | 44.5% (37.8% to 51.4%) | 39.3 | 5.8 / 2.5 | 31.6 / 7.7 | 494 (114) | 185 (19) | 0 |
| uniform | 160 | 52.5% (44.8% to 60.1%) | 39.1 | 5.2 / 2.3 | 24.5 / 7.0 | 433 (98) | 162 (14) | 0 |
| near_symmetric | 20 | 25.0% (11.2% to 46.9%) | 41.4 | 7.5 / 9.4 | 61.8 / 66.6 | 49 (8) | 7 (2) | 0 |
| wrong_side | 20 | 0.0% (0.0% to 16.1%) | n/a | 8.6 / 8.3 | 58.0 / 52.5 | 12 (8) | 16 (3) | 0 |
| target_side_1+ | 150 | 30.0% (23.2% to 37.8%) | 43.9 | 7.0 / 2.7 | 39.6 / 9.1 | 384 (84) | 134 (13) | 0 |
| pairing_margin<5cm | 58 | 27.6% (17.8% to 40.2%) | 42.4 | 8.0 / 2.6 | 45.8 / 10.0 | 144 (28) | 164 (17) | 0 |

Arrived episodes only: position error 1.8 cm, heading error 5.7 deg (means over both ducks).

## End to end (rendezvous, handoff, push)

| starts | n | push success (95% interval) | success when the ducks arrived | success after a 50-step handoff without arrival |
|---|---|---|---|---|
| all | 200 | 61.0% (54.1% to 67.5%) | 82 of 89 (92.1%) | 40 of 111 |
| uniform | 160 | 67.5% (59.9% to 74.3%) | 77 of 84 (91.7%) | 31 of 76 |
| near_symmetric | 20 | 35.0% (18.1% to 56.7%) | 5 of 5 (100.0%) | 2 of 15 |
| wrong_side | 20 | 35.0% (18.1% to 56.7%) | 0 of 0 (n/a) | 7 of 20 |
| target_side_1+ | 150 | 52.7% (44.7% to 60.5%) | 43 of 45 (95.6%) | 36 of 105 |
| pairing_margin<5cm | 58 | 48.3% (35.9% to 60.8%) | 16 of 16 (100.0%) | 12 of 42 |

Push endings, all starts: box_tipped 3, success 122, timeout 75.

Wall time 80.4 s.
