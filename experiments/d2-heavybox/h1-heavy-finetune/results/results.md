# h1 heavy-box fine-tune: results

Written by `scripts/rl/run_h1_heavy_finetune.py`. Box 0.6 kg, 130-step limit, reward v1.1-t130. Deterministic, one episode per start. Cooperative success = task success and each duck at least 25% of the pushing; 95% Wilson intervals.

## Training

| seed | early check (400k) | pick (step) | check set at the pick: cooperative / task | wall time |
|---|---|---|---|---|
| 1 | 98/200 task successes at 400000 | 1801408 | 124/200 / 129/200 | 86 min |
| 2 | 87/200 task successes at 400000 | 2002944 | 130/200 / 133/200 | 62 min |
| 3 | 81/200 task successes at 400000 | 2002944 | 119/200 / 120/200 | 62 min |

Check set, every kept checkpoint (cooperative successes / task successes of the starts):

- seed 1: 200k 51/67, 400k 79/98, 401k 78/93, 601k 90/100, 801k 112/115, 1001k 115/118, 1201k 117/122, 1401k 119/126, 1601k 120/122, 1801k 124/129, 2001k 121/125, 2002k 119/123
- seed 2: 200k 39/47, 400k 84/87, 401k 88/90, 601k 102/105, 801k 111/112, 1001k 111/111, 1201k 126/128, 1401k 126/129, 1601k 110/112, 1801k 113/117, 2001k 128/131, 2002k 130/133
- seed 3: 200k 66/74, 400k 72/81, 401k 63/76, 601k 73/82, 801k 87/96, 1001k 78/88, 1201k 97/106, 1401k 110/115, 1601k 106/109, 1801k 104/107, 2001k 116/116, 2002k 119/120

## Results

### Check set (heavy box, L2 start noise; used for picking and for the decision rule)

| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | steps to success, mean (max) |
|---|---|---|---|---|---|---|---|---|---|---|
| frozen L2-s2 | 200 | 30.0% (24.1 to 36.7) | **25.0% (19.5 to 31.4)** | 24.5% (19.1 to 30.9) | 0.0% (0.0 to 1.9) | 0.0% (0.0 to 1.9) | 8/200 | 1/200 | 131/200 | 81 (127) |
| h1 seed 1 (pick, step 1801408) | 200 | 64.5% (57.7 to 70.8) | **62.0% (55.1 to 68.4)** | 62.0% (55.1 to 68.4) | 1.0% (0.3 to 3.6) | 8.5% (5.4 to 13.2) | 4/200 | 2/200 | 64/200 | 73 (130) |
| h1 seed 2 (pick, step 2002944) | 200 | 66.5% (59.7 to 72.7) | **65.0% (58.2 to 71.3)** | 65.0% (58.2 to 71.3) | 2.5% (1.1 to 5.7) | 5.0% (2.7 to 9.0) | 4/200 | 2/200 | 60/200 | 74 (130) |
| h1 seed 3 (pick, step 2002944) | 200 | 60.0% (53.1 to 66.5) | **59.5% (52.6 to 66.1)** | 59.0% (52.1 to 65.6) | 0.0% (0.0 to 1.9) | 5.5% (3.1 to 9.6) | 6/200 | 3/200 | 70/200 | 73 (129) |

Share of the pushing done by the duck doing less (contact impulse), of the task successes:

| policy | successes | 0-10% | 10-25% | 25-40% | 40-50% |
|---|---|---|---|---|---|
| frozen L2-s2 | 60 | 2 (3%) | 8 (13%) | 9 (15%) | 41 (68%) |
| h1 seed 1 (pick, step 1801408) | 129 | 4 (3%) | 1 (1%) | 0 (0%) | 124 (96%) |
| h1 seed 2 (pick, step 2002944) | 133 | 2 (2%) | 1 (1%) | 0 (0%) | 130 (98%) |
| h1 seed 3 (pick, step 2002944) | 120 | 1 (1%) | 0 (0%) | 1 (1%) | 118 (98%) |

h1 (the 3 seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success +33.7 (+27.6 to +39.7); seeds +34.5, +36.5, +30.0; **measurable**. Cooperative success (contact impulse) +37.2 (+30.9 to +43.4); seeds +37.0, +40.0, +34.5; **measurable**. Cooperative success (along the line) +37.5 (+31.3 to +43.7); seeds +37.5, +40.5, +34.5; **measurable**.

### Test set: clean, heavy box (`experiments/test_sets/stage1_heavy_clean_large.json`)

| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | steps to success, mean (max) |
|---|---|---|---|---|---|---|---|---|---|---|
| frozen L2-s2 | 141 | 32.6% (25.4 to 40.7) | **22.7% (16.6 to 30.3)** | 22.7% (16.6 to 30.3) | 0.0% (0.0 to 2.7) | 0.7% (0.1 to 3.9) | 4/141 | 0/141 | 91/141 | 84 (124) |
| h1 seed 1 (pick, step 1801408) | 141 | 73.8% (65.9 to 80.3) | **73.0% (65.2 to 79.7)** | 73.0% (65.2 to 79.7) | 0.0% (0.0 to 2.7) | 9.2% (5.5 to 15.1) | 2/141 | 0/141 | 35/141 | 71 (129) |
| h1 seed 2 (pick, step 2002944) | 141 | 70.2% (62.2 to 77.1) | **70.2% (62.2 to 77.1)** | 70.2% (62.2 to 77.1) | 2.8% (1.1 to 7.1) | 3.5% (1.5 to 8.0) | 2/141 | 0/141 | 40/141 | 71 (118) |
| h1 seed 3 (pick, step 2002944) | 141 | 71.6% (63.7 to 78.4) | **70.9% (63.0 to 77.8)** | 70.9% (63.0 to 77.8) | 0.0% (0.0 to 2.7) | 5.0% (2.4 to 9.9) | 6/141 | 0/141 | 34/141 | 71 (128) |

Share of the pushing done by the duck doing less (contact impulse), of the task successes:

| policy | successes | 0-10% | 10-25% | 25-40% | 40-50% |
|---|---|---|---|---|---|
| frozen L2-s2 | 46 | 0 (0%) | 14 (30%) | 5 (11%) | 27 (59%) |
| h1 seed 1 (pick, step 1801408) | 104 | 1 (1%) | 0 (0%) | 0 (0%) | 103 (99%) |
| h1 seed 2 (pick, step 2002944) | 99 | 0 (0%) | 0 (0%) | 0 (0%) | 99 (100%) |
| h1 seed 3 (pick, step 2002944) | 101 | 1 (1%) | 0 (0%) | 0 (0%) | 100 (99%) |

h1 (the 3 seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success +39.2 (+31.4 to +47.1); seeds +41.1, +37.6, +39.0; **measurable**. Cooperative success (contact impulse) +48.7 (+40.7 to +56.7); seeds +50.4, +47.5, +48.2; **measurable**. Cooperative success (along the line) +48.7 (+40.7 to +56.7); seeds +50.4, +47.5, +48.2; **measurable**.

### Test set: noisy, heavy box (`experiments/test_sets/stage1_heavy_noisy_large.json`)

| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | steps to success, mean (max) |
|---|---|---|---|---|---|---|---|---|---|---|
| frozen L2-s2 | 142 | 36.6% (29.1 to 44.8) | **27.5% (20.8 to 35.3)** | 27.5% (20.8 to 35.3) | 0.0% (0.0 to 2.6) | 0.0% (0.0 to 2.6) | 3/142 | 1/142 | 86/142 | 84 (129) |
| h1 seed 1 (pick, step 1801408) | 142 | 69.7% (61.7 to 76.7) | **69.7% (61.7 to 76.7)** | 69.7% (61.7 to 76.7) | 0.7% (0.1 to 3.9) | 4.9% (2.4 to 9.8) | 1/142 | 1/142 | 41/142 | 71 (123) |
| h1 seed 2 (pick, step 2002944) | 142 | 72.5% (64.7 to 79.2) | **72.5% (64.7 to 79.2)** | 72.5% (64.7 to 79.2) | 6.3% (3.4 to 11.6) | 2.8% (1.1 to 7.0) | 3/142 | 1/142 | 35/142 | 73 (124) |
| h1 seed 3 (pick, step 2002944) | 142 | 64.8% (56.6 to 72.2) | **64.1% (55.9 to 71.5)** | 64.1% (55.9 to 71.5) | 0.0% (0.0 to 2.6) | 2.8% (1.1 to 7.0) | 3/142 | 1/142 | 46/142 | 70 (129) |

Share of the pushing done by the duck doing less (contact impulse), of the task successes:

| policy | successes | 0-10% | 10-25% | 25-40% | 40-50% |
|---|---|---|---|---|---|
| frozen L2-s2 | 52 | 0 (0%) | 13 (25%) | 6 (12%) | 33 (63%) |
| h1 seed 1 (pick, step 1801408) | 99 | 0 (0%) | 0 (0%) | 0 (0%) | 99 (100%) |
| h1 seed 2 (pick, step 2002944) | 103 | 0 (0%) | 0 (0%) | 0 (0%) | 103 (100%) |
| h1 seed 3 (pick, step 2002944) | 92 | 1 (1%) | 0 (0%) | 0 (0%) | 91 (99%) |

h1 (the 3 seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success +32.4 (+25.1 to +39.7); seeds +33.1, +35.9, +28.2; **measurable**. Cooperative success (contact impulse) +41.3 (+33.8 to +48.9); seeds +42.3, +45.1, +36.6; **measurable**. Cooperative success (along the line) +41.3 (+33.8 to +48.9); seeds +42.3, +45.1, +36.6; **measurable**.

### Test set: L1, heavy box (`experiments/test_sets/stage1_heavy_L1_large.json`)

| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | steps to success, mean (max) |
|---|---|---|---|---|---|---|---|---|---|---|
| frozen L2-s2 | 141 | 29.8% (22.9 to 37.8) | **27.0% (20.3 to 34.8)** | 27.0% (20.3 to 34.8) | 0.0% (0.0 to 2.7) | 0.7% (0.1 to 3.9) | 5/141 | 1/141 | 93/141 | 75 (125) |
| h1 seed 1 (pick, step 1801408) | 141 | 65.2% (57.1 to 72.6) | **61.7% (53.5 to 69.3)** | 61.7% (53.5 to 69.3) | 0.0% (0.0 to 2.7) | 7.1% (3.9 to 12.6) | 4/141 | 3/141 | 42/141 | 73 (130) |
| h1 seed 2 (pick, step 2002944) | 141 | 70.9% (63.0 to 77.8) | **69.5% (61.5 to 76.5)** | 68.8% (60.7 to 75.9) | 2.1% (0.7 to 6.1) | 5.7% (2.9 to 10.8) | 6/141 | 1/141 | 34/141 | 73 (130) |
| h1 seed 3 (pick, step 2002944) | 141 | 63.1% (54.9 to 70.6) | **61.0% (52.8 to 68.7)** | 61.0% (52.8 to 68.7) | 0.0% (0.0 to 2.7) | 3.5% (1.5 to 8.0) | 5/141 | 2/141 | 45/141 | 72 (130) |

Share of the pushing done by the duck doing less (contact impulse), of the task successes:

| policy | successes | 0-10% | 10-25% | 25-40% | 40-50% |
|---|---|---|---|---|---|
| frozen L2-s2 | 42 | 0 (0%) | 4 (10%) | 3 (7%) | 35 (83%) |
| h1 seed 1 (pick, step 1801408) | 92 | 5 (5%) | 0 (0%) | 0 (0%) | 87 (95%) |
| h1 seed 2 (pick, step 2002944) | 100 | 2 (2%) | 0 (0%) | 1 (1%) | 97 (97%) |
| h1 seed 3 (pick, step 2002944) | 89 | 2 (2%) | 1 (1%) | 0 (0%) | 86 (97%) |

h1 (the 3 seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success +36.6 (+29.1 to +44.2); seeds +35.5, +41.1, +33.3; **measurable**. Cooperative success (contact impulse) +37.1 (+29.6 to +44.6); seeds +34.8, +42.6, +34.0; **measurable**. Cooperative success (along the line) +36.9 (+29.4 to +44.4); seeds +34.8, +41.8, +34.0; **measurable**.

### Test set: L2, heavy box (`experiments/test_sets/stage1_heavy_L2_large.json`)

| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | steps to success, mean (max) |
|---|---|---|---|---|---|---|---|---|---|---|
| frozen L2-s2 | 141 | 32.6% (25.4 to 40.7) | **27.7% (20.9 to 35.6)** | 26.2% (19.7 to 34.1) | 0.0% (0.0 to 2.7) | 0.0% (0.0 to 2.7) | 1/141 | 1/141 | 93/141 | 84 (130) |
| h1 seed 1 (pick, step 1801408) | 141 | 67.4% (59.3 to 74.6) | **65.2% (57.1 to 72.6)** | 65.2% (57.1 to 72.6) | 0.0% (0.0 to 2.7) | 5.7% (2.9 to 10.8) | 0/141 | 0/141 | 46/141 | 74 (130) |
| h1 seed 2 (pick, step 2002944) | 141 | 65.2% (57.1 to 72.6) | **64.5% (56.4 to 72.0)** | 63.8% (55.6 to 71.3) | 1.4% (0.4 to 5.0) | 4.3% (2.0 to 9.0) | 4/141 | 1/141 | 44/141 | 72 (122) |
| h1 seed 3 (pick, step 2002944) | 141 | 64.5% (56.4 to 72.0) | **63.8% (55.6 to 71.3)** | 63.1% (54.9 to 70.6) | 0.0% (0.0 to 2.7) | 2.1% (0.7 to 6.1) | 3/141 | 0/141 | 47/141 | 72 (127) |

Share of the pushing done by the duck doing less (contact impulse), of the task successes:

| policy | successes | 0-10% | 10-25% | 25-40% | 40-50% |
|---|---|---|---|---|---|
| frozen L2-s2 | 46 | 0 (0%) | 7 (15%) | 6 (13%) | 33 (72%) |
| h1 seed 1 (pick, step 1801408) | 95 | 3 (3%) | 0 (0%) | 2 (2%) | 90 (95%) |
| h1 seed 2 (pick, step 2002944) | 92 | 0 (0%) | 1 (1%) | 1 (1%) | 90 (98%) |
| h1 seed 3 (pick, step 2002944) | 91 | 1 (1%) | 0 (0%) | 2 (2%) | 88 (97%) |

h1 (the 3 seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success +33.1 (+26.2 to +40.0); seeds +34.8, +32.6, +31.9; **measurable**. Cooperative success (contact impulse) +36.9 (+29.7 to +44.0); seeds +37.6, +36.9, +36.2; **measurable**. Cooperative success (along the line) +37.8 (+30.7 to +45.0); seeds +39.0, +37.6, +36.9; **measurable**.

### Forgetting check: LIGHT box (0.15 kg, 100 steps), clean test set

| policy | n | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | duck B alone (A idle): task success | duck A alone (B idle): task success | falls | tip-overs | timeouts | steps to success, mean (max) |
|---|---|---|---|---|---|---|---|---|---|---|
| frozen L2-s2 | 200 | 97.5% (94.3 to 98.9) | **50.5% (43.6 to 57.4)** | 50.5% (43.6 to 57.4) | not run | not run | 0/200 | 0/200 | 5/200 | 37 (75) |
| h1 seed 1 (pick, step 1801408) | 200 | 43.5% (36.8 to 50.4) | **40.0% (33.5 to 46.9)** | 40.0% (33.5 to 46.9) | not run | not run | 2/200 | 1/200 | 110/200 | 33 (54) |
| h1 seed 2 (pick, step 2002944) | 200 | 56.5% (49.6 to 63.2) | **43.0% (36.3 to 49.9)** | 43.0% (36.3 to 49.9) | not run | not run | 4/200 | 1/200 | 82/200 | 43 (100) |
| h1 seed 3 (pick, step 2002944) | 200 | 24.5% (19.1 to 30.9) | **17.5% (12.9 to 23.4)** | 17.0% (12.4 to 22.8) | not run | not run | 10/200 | 3/200 | 138/200 | 38 (59) |

Share of the pushing done by the duck doing less (contact impulse), of the task successes:

| policy | successes | 0-10% | 10-25% | 25-40% | 40-50% |
|---|---|---|---|---|---|
| frozen L2-s2 | 195 | 94 (48%) | 0 (0%) | 4 (2%) | 97 (50%) |
| h1 seed 1 (pick, step 1801408) | 87 | 6 (7%) | 1 (1%) | 13 (15%) | 67 (77%) |
| h1 seed 2 (pick, step 2002944) | 113 | 25 (22%) | 2 (2%) | 14 (12%) | 72 (64%) |
| h1 seed 3 (pick, step 2002944) | 49 | 14 (29%) | 0 (0%) | 5 (10%) | 30 (61%) |

h1 (the 3 seeds averaged per start) minus frozen L2-s2, same starts, percentage points: task success -56.0 (-61.1 to -50.9); seeds -54.0, -41.0, -73.0; **measurable**. Cooperative success (contact impulse) -17.0 (-21.6 to -12.4); seeds -10.5, -7.5, -33.0; **measurable**. Cooperative success (along the line) -17.2 (-21.8 to -12.6); seeds -10.5, -7.5, -33.5; **measurable**.

## Decision rule (check set)

- Cooperative success measurably above frozen L2-s2: **yes** (+37.2 (+30.9 to +43.4); seeds +37.0, +40.0, +34.5; **measurable**).
- Both solo tests under 10% task success: **yes** (h1 seed 1 (pick, step 1801408): duck B alone 1.0%, duck A alone 8.5%; h1 seed 2 (pick, step 2002944): duck B alone 2.5%, duck A alone 5.0%; h1 seed 3 (pick, step 2002944): duck B alone 0.0%, duck A alone 5.5%).
- **h1 works: yes.**
- Successes where one duck does under 25%: h1 seed 1 (pick, step 1801408): 5 of 129 (4%); h1 seed 2 (pick, step 2002944): 3 of 133 (2%); h1 seed 3 (pick, step 2002944): 1 of 120 (1%). Add the balanced-push bonus next (solo rule met and more than a third in any seed): **no**.

## Full pipeline (r6 rendezvous, then the push policy; heavy box; `experiments/test_sets/rendezvous_large.json`)

| push policy | n | docked | task success | **cooperative success (contact impulse, 25%)** | cooperative (along the line, 25%) | push endings |
|---|---|---|---|---|---|---|
| frozen L2-s2 | 200 | 168/200 | 37.5% (31.1 to 44.4) | **27.5% (21.8 to 34.1)** | 27.0% (21.3 to 33.5) | fall 4, success 75, timeout 121 |
| h1 seed 2 (pick, step 2002944) | 200 | 168/200 | 69.5% (62.8 to 75.5) | **64.5% (57.7 to 70.8)** | 64.5% (57.7 to 70.8) | fall 6, success 139, timeout 55 |

h1 seed 2 (pick, step 2002944) minus frozen L2-s2, same starts (one seed, so no seed rule): task success +32.0 (+24.4 to +39.6); seeds +32.0; **measurable**. Cooperative success +37.0 (+29.5 to +44.5); seeds +37.0; **measurable**.

## Clips

- `cooperative_success_start001.gif`: cooperative success, start 1, ended success in 71 steps
- `cooperative_success_start002.gif`: cooperative success, start 2, ended success in 65 steps
- `failure_start004.gif`: failure, start 4, ended timeout in 130 steps
- `solo_test_duck_a_idle_start001.gif`: solo test duck a idle, start 1, ended timeout in 130 steps
