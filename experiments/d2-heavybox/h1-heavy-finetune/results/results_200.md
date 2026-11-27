# h1 heavy-box fine-tune: results on the 200-start heavy sets

Written by `scripts/rl/h1_fill_eval.py`. Same evaluation as `results.md` (deterministic, one episode per start, box 0.6 kg, 130-step limit, reward v1.1-t130), on `experiments/test_sets/stage1_heavy_<set>_200.json`: the 141 (noisy: 142) starts of the earlier heavy sets, unchanged, plus new starts to reach 200. Cooperative success = task success and each duck at least 25% of the pushing; 95% Wilson intervals. The 141-start tables in `results.md` stay as the first report (superseded by these for any README or decision).

## Old starts reproduce

The old starts inside each 200-start set were compared with `episodes.json` (id, reason, steps, contact_share_a, push_share_a, fell) for every policy and mode: 6780 episodes checked, 0 different.

## Results

### Test set: clean, heavy box, 200 starts (`experiments/test_sets/stage1_heavy_clean_200.json`)

| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | steps to success, mean (max) |
|---|---|---|---|---|---|---|---|---|---|---|
| frozen L2-s2 | 200 | 32.5% (26.4 to 39.3) | **24.0% (18.6 to 30.4)** | 24.0% (18.6 to 30.4) | 0.0% (0.0 to 1.9) | 0.5% (0.1 to 2.8) | 5/200 | 0/200 | 130/200 | 83 (128) |
| h1 seed 1 (pick, step 1801408) | 200 | 71.5% (64.9 to 77.3) | **70.5% (63.8 to 76.4)** | 70.5% (63.8 to 76.4) | 0.0% (0.0 to 1.9) | 8.5% (5.4 to 13.2) | 5/200 | 0/200 | 52/200 | 72 (129) |
| h1 seed 2 (pick, step 2002944) | 200 | 71.0% (64.4 to 76.8) | **71.0% (64.4 to 76.8)** | 71.0% (64.4 to 76.8) | 3.5% (1.7 to 7.0) | 3.0% (1.4 to 6.4) | 2/200 | 0/200 | 55/200 | 71 (126) |
| h1 seed 3 (pick, step 2002944) | 200 | 69.5% (62.8 to 75.5) | **69.0% (62.3 to 75.0)** | 69.0% (62.3 to 75.0) | 0.0% (0.0 to 1.9) | 4.5% (2.4 to 8.3) | 7/200 | 0/200 | 54/200 | 71 (128) |

Share of the pushing done by the duck doing less (contact impulse), of the task successes:

| policy | successes | 0-10% | 10-25% | 25-40% | 40-50% |
|---|---|---|---|---|---|
| frozen L2-s2 | 65 | 0 (0%) | 17 (26%) | 7 (11%) | 41 (63%) |
| h1 seed 1 (pick, step 1801408) | 143 | 2 (1%) | 0 (0%) | 0 (0%) | 141 (99%) |
| h1 seed 2 (pick, step 2002944) | 142 | 0 (0%) | 0 (0%) | 0 (0%) | 142 (100%) |
| h1 seed 3 (pick, step 2002944) | 139 | 1 (1%) | 0 (0%) | 0 (0%) | 138 (99%) |

h1 (the 3 seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success +38.2 (+31.8 to +44.6); seeds +39.0, +38.5, +37.0; **measurable**. Cooperative success (contact impulse) +46.2 (+39.6 to +52.7); seeds +46.5, +47.0, +45.0; **measurable**. Cooperative success (along the line) +46.2 (+39.6 to +52.7); seeds +46.5, +47.0, +45.0; **measurable**.

### Test set: noisy, heavy box, 200 starts (`experiments/test_sets/stage1_heavy_noisy_200.json`)

| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | steps to success, mean (max) |
|---|---|---|---|---|---|---|---|---|---|---|
| frozen L2-s2 | 200 | 35.5% (29.2 to 42.3) | **26.0% (20.4 to 32.5)** | 26.0% (20.4 to 32.5) | 0.0% (0.0 to 1.9) | 0.0% (0.0 to 1.9) | 3/200 | 1/200 | 125/200 | 85 (130) |
| h1 seed 1 (pick, step 1801408) | 200 | 69.5% (62.8 to 75.5) | **69.5% (62.8 to 75.5)** | 69.5% (62.8 to 75.5) | 0.5% (0.1 to 2.8) | 5.5% (3.1 to 9.6) | 1/200 | 1/200 | 59/200 | 70 (123) |
| h1 seed 2 (pick, step 2002944) | 200 | 71.0% (64.4 to 76.8) | **71.0% (64.4 to 76.8)** | 71.0% (64.4 to 76.8) | 5.5% (3.1 to 9.6) | 2.5% (1.1 to 5.7) | 3/200 | 2/200 | 53/200 | 72 (124) |
| h1 seed 3 (pick, step 2002944) | 200 | 64.5% (57.7 to 70.8) | **64.0% (57.1 to 70.3)** | 64.0% (57.1 to 70.3) | 0.0% (0.0 to 1.9) | 3.5% (1.7 to 7.0) | 4/200 | 1/200 | 66/200 | 70 (129) |

Share of the pushing done by the duck doing less (contact impulse), of the task successes:

| policy | successes | 0-10% | 10-25% | 25-40% | 40-50% |
|---|---|---|---|---|---|
| frozen L2-s2 | 71 | 0 (0%) | 19 (27%) | 8 (11%) | 44 (62%) |
| h1 seed 1 (pick, step 1801408) | 139 | 0 (0%) | 0 (0%) | 0 (0%) | 139 (100%) |
| h1 seed 2 (pick, step 2002944) | 142 | 0 (0%) | 0 (0%) | 1 (1%) | 141 (99%) |
| h1 seed 3 (pick, step 2002944) | 129 | 1 (1%) | 0 (0%) | 0 (0%) | 128 (99%) |

h1 (the 3 seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success +32.8 (+26.7 to +38.9); seeds +34.0, +35.5, +29.0; **measurable**. Cooperative success (contact impulse) +42.2 (+35.8 to +48.5); seeds +43.5, +45.0, +38.0; **measurable**. Cooperative success (along the line) +42.2 (+35.8 to +48.5); seeds +43.5, +45.0, +38.0; **measurable**.

### Test set: L1, heavy box, 200 starts (`experiments/test_sets/stage1_heavy_L1_200.json`)

| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | steps to success, mean (max) |
|---|---|---|---|---|---|---|---|---|---|---|
| frozen L2-s2 | 200 | 31.5% (25.5 to 38.2) | **27.5% (21.8 to 34.1)** | 27.5% (21.8 to 34.1) | 0.0% (0.0 to 1.9) | 0.5% (0.1 to 2.8) | 6/200 | 1/200 | 130/200 | 77 (125) |
| h1 seed 1 (pick, step 1801408) | 200 | 67.0% (60.2 to 73.1) | **63.5% (56.6 to 69.9)** | 63.5% (56.6 to 69.9) | 0.0% (0.0 to 1.9) | 7.0% (4.2 to 11.4) | 4/200 | 4/200 | 58/200 | 73 (130) |
| h1 seed 2 (pick, step 2002944) | 200 | 71.5% (64.9 to 77.3) | **70.0% (63.3 to 75.9)** | 69.5% (62.8 to 75.5) | 2.0% (0.8 to 5.0) | 5.5% (3.1 to 9.6) | 9/200 | 1/200 | 47/200 | 72 (130) |
| h1 seed 3 (pick, step 2002944) | 200 | 62.5% (55.6 to 68.9) | **61.0% (54.1 to 67.5)** | 61.0% (54.1 to 67.5) | 0.0% (0.0 to 1.9) | 3.0% (1.4 to 6.4) | 7/200 | 3/200 | 65/200 | 72 (130) |

Share of the pushing done by the duck doing less (contact impulse), of the task successes:

| policy | successes | 0-10% | 10-25% | 25-40% | 40-50% |
|---|---|---|---|---|---|
| frozen L2-s2 | 63 | 0 (0%) | 8 (13%) | 7 (11%) | 48 (76%) |
| h1 seed 1 (pick, step 1801408) | 134 | 7 (5%) | 0 (0%) | 0 (0%) | 127 (95%) |
| h1 seed 2 (pick, step 2002944) | 143 | 3 (2%) | 0 (0%) | 1 (1%) | 139 (97%) |
| h1 seed 3 (pick, step 2002944) | 125 | 2 (2%) | 1 (1%) | 0 (0%) | 122 (98%) |

h1 (the 3 seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success +35.5 (+29.1 to +41.9); seeds +35.5, +40.0, +31.0; **measurable**. Cooperative success (contact impulse) +37.3 (+30.9 to +43.8); seeds +36.0, +42.5, +33.5; **measurable**. Cooperative success (along the line) +37.2 (+30.7 to +43.6); seeds +36.0, +42.0, +33.5; **measurable**.

### Test set: L2, heavy box, 200 starts (`experiments/test_sets/stage1_heavy_L2_200.json`)

| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | steps to success, mean (max) |
|---|---|---|---|---|---|---|---|---|---|---|
| frozen L2-s2 | 200 | 31.5% (25.5 to 38.2) | **26.5% (20.9 to 33.0)** | 25.5% (20.0 to 32.0) | 0.0% (0.0 to 1.9) | 0.0% (0.0 to 1.9) | 2/200 | 1/200 | 134/200 | 82 (130) |
| h1 seed 1 (pick, step 1801408) | 200 | 65.5% (58.7 to 71.7) | **64.0% (57.1 to 70.3)** | 64.0% (57.1 to 70.3) | 0.0% (0.0 to 1.9) | 4.5% (2.4 to 8.3) | 0/200 | 0/200 | 69/200 | 73 (130) |
| h1 seed 2 (pick, step 2002944) | 200 | 66.5% (59.7 to 72.7) | **65.0% (58.2 to 71.3)** | 64.5% (57.7 to 70.8) | 2.0% (0.8 to 5.0) | 4.0% (2.0 to 7.7) | 4/200 | 2/200 | 61/200 | 72 (130) |
| h1 seed 3 (pick, step 2002944) | 200 | 61.5% (54.6 to 68.0) | **60.5% (53.6 to 67.0)** | 60.0% (53.1 to 66.5) | 0.0% (0.0 to 1.9) | 4.0% (2.0 to 7.7) | 5/200 | 1/200 | 71/200 | 72 (128) |

Share of the pushing done by the duck doing less (contact impulse), of the task successes:

| policy | successes | 0-10% | 10-25% | 25-40% | 40-50% |
|---|---|---|---|---|---|
| frozen L2-s2 | 63 | 0 (0%) | 10 (16%) | 7 (11%) | 46 (73%) |
| h1 seed 1 (pick, step 1801408) | 131 | 3 (2%) | 0 (0%) | 2 (2%) | 126 (96%) |
| h1 seed 2 (pick, step 2002944) | 133 | 1 (1%) | 2 (2%) | 1 (1%) | 129 (97%) |
| h1 seed 3 (pick, step 2002944) | 123 | 2 (2%) | 0 (0%) | 2 (2%) | 119 (97%) |

h1 (the 3 seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success +33.0 (+27.2 to +38.8); seeds +34.0, +35.0, +30.0; **measurable**. Cooperative success (contact impulse) +36.7 (+30.6 to +42.7); seeds +37.5, +38.5, +34.0; **measurable**. Cooperative success (along the line) +37.3 (+31.3 to +43.4); seeds +38.5, +39.0, +34.5; **measurable**.

## Where the box starts (distance to the target)

Two ducks at their open-loop speed (0.0357 m/s) cover 0.928 m in 26 s, one duck (0.0195 m/s) 0.507 m. Margin = two-duck reach divided by the 90th percentile distance, minus 1. Distances in metres, all 200 starts of each set.

| set | distance | min | p10 | p50 | p90 | max | two-duck margin over p90 | one duck could reach |
|---|---|---|---|---|---|---|---|---|
| clean | to target centre | 0.613 | 0.643 | 0.715 | 0.797 | 0.870 | +16% | 0 of 200 |
| clean | to enter the target | 0.508 | 0.526 | 0.603 | 0.685 | 0.753 | +35% | 0 of 200 |
| noisy | to target centre | 0.615 | 0.637 | 0.713 | 0.797 | 0.867 | +16% | 0 of 200 |
| noisy | to enter the target | 0.508 | 0.523 | 0.598 | 0.684 | 0.750 | +36% | 0 of 200 |
| L1 | to target centre | 0.613 | 0.643 | 0.715 | 0.797 | 0.870 | +16% | 0 of 200 |
| L1 | to enter the target | 0.508 | 0.526 | 0.603 | 0.685 | 0.753 | +35% | 0 of 200 |
| L2 | to target centre | 0.613 | 0.643 | 0.715 | 0.797 | 0.870 | +16% | 0 of 200 |
| L2 | to enter the target | 0.508 | 0.526 | 0.603 | 0.685 | 0.753 | +35% | 0 of 200 |

Box start to target centre for the h1 picks, both ducks (m; mean and 90th percentile, number of starts):

| policy | set | successes | timeouts |
|---|---|---|---|
| h1 seed 1 (pick, step 1801408) | clean | mean 0.718, p90 0.804 (n=143) | mean 0.721, p90 0.785 (n=52) |
| h1 seed 1 (pick, step 1801408) | noisy | mean 0.712, p90 0.797 (n=139) | mean 0.729, p90 0.803 (n=59) |
| h1 seed 1 (pick, step 1801408) | L1 | mean 0.714, p90 0.803 (n=134) | mean 0.727, p90 0.782 (n=58) |
| h1 seed 1 (pick, step 1801408) | L2 | mean 0.715, p90 0.793 (n=131) | mean 0.725, p90 0.822 (n=69) |
| h1 seed 1 (pick, step 1801408) | all four sets | mean 0.715, p90 0.797 (n=547) | mean 0.726, p90 0.797 (n=238) |
| h1 seed 2 (pick, step 2002944) | clean | mean 0.711, p90 0.787 (n=142) | mean 0.738, p90 0.814 (n=55) |
| h1 seed 2 (pick, step 2002944) | noisy | mean 0.712, p90 0.793 (n=142) | mean 0.727, p90 0.802 (n=53) |
| h1 seed 2 (pick, step 2002944) | L1 | mean 0.717, p90 0.798 (n=143) | mean 0.719, p90 0.783 (n=47) |
| h1 seed 2 (pick, step 2002944) | L2 | mean 0.719, p90 0.803 (n=133) | mean 0.717, p90 0.797 (n=61) |
| h1 seed 2 (pick, step 2002944) | all four sets | mean 0.715, p90 0.797 (n=560) | mean 0.725, p90 0.800 (n=216) |
| h1 seed 3 (pick, step 2002944) | clean | mean 0.715, p90 0.799 (n=139) | mean 0.725, p90 0.780 (n=54) |
| h1 seed 3 (pick, step 2002944) | noisy | mean 0.713, p90 0.794 (n=129) | mean 0.724, p90 0.810 (n=66) |
| h1 seed 3 (pick, step 2002944) | L1 | mean 0.716, p90 0.802 (n=125) | mean 0.718, p90 0.783 (n=65) |
| h1 seed 3 (pick, step 2002944) | L2 | mean 0.713, p90 0.797 (n=123) | mean 0.725, p90 0.785 (n=71) |
| h1 seed 3 (pick, step 2002944) | all four sets | mean 0.714, p90 0.797 (n=516) | mean 0.723, p90 0.798 (n=256) |
