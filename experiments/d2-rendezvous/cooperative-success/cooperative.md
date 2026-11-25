# Cooperative success: the rendezvous pipeline and the L2-s2 push policy

Written by `scripts/rl/cooperation_report.py report`. 200 starts per row, deterministic, per-start seeds 10000 + i. Pipeline rows: `experiments/test_sets/rendezvous_large.json`, rendezvous then the frozen L2-s2 push policy. L2-s2 rows: the ducks start in contact with the box.

## Cooperative success

Cooperative success = task success and each duck's share of the pushing at least 25%. Contact impulse (contact force on the box, integrated over the push) is the headline measure; the along-the-line measure counts only force toward the target. 95% Wilson intervals over all starts.

| | n | task success | **cooperative success (contact impulse, 25%)** | cooperative success (along the line, 25%) | successes with one duck under 25% (contact impulse) |
|---|---|---|---|---|---|
| scripted rendezvous | 200 | 65.0% (58.2 to 71.3) | **36.5% (30.1 to 43.4)** | 36.0% (29.7 to 42.9) | 57 of 130 (43.8%) |
| r6 seed 1 (official) | 200 | 90.0% (85.1 to 93.4) | **47.0% (40.2 to 53.9)** | 47.0% (40.2 to 53.9) | 86 of 180 (47.8%) |
| r6 seed 2 | 200 | 85.5% (80.0 to 89.7) | **46.0% (39.2 to 52.9)** | 45.0% (38.3 to 51.9) | 79 of 171 (46.2%) |
| r7 seed 1 (check-set pick) | 200 | 86.0% (80.5 to 90.1) | **43.0% (36.3 to 49.9)** | 43.0% (36.3 to 49.9) | 86 of 172 (50.0%) |
| r7 seed 2 (check-set pick) | 200 | 85.0% (79.4 to 89.3) | **42.5% (35.9 to 49.4)** | 41.5% (34.9 to 48.4) | 85 of 170 (50.0%) |
| L2-s2 push policy, clean set | 200 | 97.5% (94.3 to 98.9) | **50.5% (43.6 to 57.4)** | 50.5% (43.6 to 57.4) | 94 of 195 (48.2%) |
| L2-s2 push policy, noisy set | 200 | 93.0% (88.6 to 95.8) | **47.5% (40.7 to 54.4)** | 47.5% (40.7 to 54.4) | 91 of 186 (48.9%) |
| L2-s2 push policy, L1 set | 200 | 90.0% (85.1 to 93.4) | **45.0% (38.3 to 51.9)** | 45.5% (38.7 to 52.4) | 90 of 180 (50.0%) |
| L2-s2 push policy, L2 set | 200 | 88.0% (82.8 to 91.8) | **43.5% (36.8 to 50.4)** | 43.0% (36.3 to 49.9) | 89 of 176 (50.6%) |

Threshold sweep, contact impulse (cooperative successes of n, each duck's share at least the threshold):

| | 10% | 20% | 25% | 30% | 40% |
|---|---|---|---|---|---|
| scripted rendezvous | 73 (36.5%) | 73 (36.5%) | 73 (36.5%) | 71 (35.5%) | 64 (32.0%) |
| r6 seed 1 (official) | 96 (48.0%) | 96 (48.0%) | 94 (47.0%) | 94 (47.0%) | 89 (44.5%) |
| r6 seed 2 | 94 (47.0%) | 93 (46.5%) | 92 (46.0%) | 90 (45.0%) | 90 (45.0%) |
| r7 seed 1 (check-set pick) | 88 (44.0%) | 87 (43.5%) | 86 (43.0%) | 86 (43.0%) | 78 (39.0%) |
| r7 seed 2 (check-set pick) | 88 (44.0%) | 85 (42.5%) | 85 (42.5%) | 84 (42.0%) | 82 (41.0%) |
| L2-s2 push policy, clean set | 101 (50.5%) | 101 (50.5%) | 101 (50.5%) | 101 (50.5%) | 97 (48.5%) |
| L2-s2 push policy, noisy set | 98 (49.0%) | 95 (47.5%) | 95 (47.5%) | 95 (47.5%) | 91 (45.5%) |
| L2-s2 push policy, L1 set | 92 (46.0%) | 91 (45.5%) | 90 (45.0%) | 90 (45.0%) | 86 (43.0%) |
| L2-s2 push policy, L2 set | 89 (44.5%) | 88 (44.0%) | 87 (43.5%) | 87 (43.5%) | 76 (38.0%) |

Threshold sweep, along the line (cooperative successes of n, each duck's share at least the threshold):

| | 10% | 20% | 25% | 30% | 40% |
|---|---|---|---|---|---|
| scripted rendezvous | 73 (36.5%) | 73 (36.5%) | 72 (36.0%) | 72 (36.0%) | 61 (30.5%) |
| r6 seed 1 (official) | 96 (48.0%) | 96 (48.0%) | 94 (47.0%) | 94 (47.0%) | 74 (37.0%) |
| r6 seed 2 | 95 (47.5%) | 92 (46.0%) | 90 (45.0%) | 89 (44.5%) | 81 (40.5%) |
| r7 seed 1 (check-set pick) | 88 (44.0%) | 87 (43.5%) | 86 (43.0%) | 84 (42.0%) | 69 (34.5%) |
| r7 seed 2 (check-set pick) | 87 (43.5%) | 85 (42.5%) | 83 (41.5%) | 83 (41.5%) | 73 (36.5%) |
| L2-s2 push policy, clean set | 101 (50.5%) | 101 (50.5%) | 101 (50.5%) | 101 (50.5%) | 85 (42.5%) |
| L2-s2 push policy, noisy set | 97 (48.5%) | 95 (47.5%) | 95 (47.5%) | 95 (47.5%) | 85 (42.5%) |
| L2-s2 push policy, L1 set | 92 (46.0%) | 91 (45.5%) | 91 (45.5%) | 88 (44.0%) | 75 (37.5%) |
| L2-s2 push policy, L2 set | 89 (44.5%) | 88 (44.0%) | 86 (43.0%) | 82 (41.0%) | 67 (33.5%) |

The two measures disagree at 25% (task successes that only one of them calls cooperative):

| | disagree | cooperative by contact impulse only | cooperative along the line only |
|---|---|---|---|
| scripted rendezvous | 1 of 130 successes | 1 | 0 |
| r6 seed 1 (official) | 0 of 180 successes | 0 | 0 |
| r6 seed 2 | 2 of 171 successes | 2 | 0 |
| r7 seed 1 (check-set pick) | 0 of 172 successes | 0 | 0 |
| r7 seed 2 (check-set pick) | 2 of 170 successes | 2 | 0 |
| L2-s2 push policy, clean set | 0 of 195 successes | 0 | 0 |
| L2-s2 push policy, noisy set | 0 of 186 successes | 0 | 0 |
| L2-s2 push policy, L1 set | 1 of 180 successes | 0 | 1 |
| L2-s2 push policy, L2 set | 1 of 176 successes | 1 | 0 |

## Reproduction

Each pipeline was rerun on its original starts and seeds because the saved results did not hold the contact impulse. Episodes identical to the original results (docked, push ending, push steps, push share):

- scripted rendezvous: 200 of 200 (`experiments/d2-rendezvous/scripted-baseline/results.json`)
- r6 seed 1 (official): 200 of 200 (`runs/d2-rendezvous-r6-dock-payout/reselect/test_s1_final/results.json`)
- r6 seed 2: 200 of 200 (`runs/d2-rendezvous-r6-dock-payout/reselect/test_s2_final/results.json`)
- r7 seed 1 (check-set pick): 200 of 200 (`runs/d2-rendezvous-r7-long-payout/eval_s1_pick/results.json`)
- r7 seed 2 (check-set pick): 200 of 200 (`runs/d2-rendezvous-r7-long-payout/eval_s2_pick/results.json`)
- L2-s2, clean set: 200 of 200 identical to the saved night 5 evaluation (ending, steps, push share)
- L2-s2, noisy set: 200 of 200 identical to the saved night 5 evaluation (ending, steps, push share)
- L2-s2, L1 set: 200 of 200 identical to the saved night 5 evaluation (ending, steps, push share)
- L2-s2, L2 set: 200 of 200 identical to the saved night 5 evaluation (ending, steps, push share)

Along-the-line measure at a 20% cutoff, against the numbers reported earlier:

- scripted rendezvous: 36.5% now, 36.5% before (same)
- r6 seed 1 (official): 48.0% now, 48.0% before (same)
- r6 seed 2: 46.0% now, 46.0% before (same)

## Paired comparisons (same 200 starts, seeds averaged per start, percentage points)

Mean per-start difference with a 95% interval; then each seed's own difference. Measurable = the interval excludes 0 and both seeds are on the same side.

**r6 minus scripted**

| | difference |
|---|---|
| task success | +22.8 (+15.7 to +29.8); seeds +25.0, +20.5; **measurable** |
| cooperative success, contact impulse, 10% | +11.0 (+5.5 to +16.5); seeds +11.5, +10.5; **measurable** |
| cooperative success, contact impulse, 20% | +10.8 (+5.2 to +16.3); seeds +11.5, +10.0; **measurable** |
| cooperative success, contact impulse, 25% | +10.0 (+4.4 to +15.6); seeds +10.5, +9.5; **measurable** |
| cooperative success, contact impulse, 30% | +10.5 (+5.0 to +16.0); seeds +11.5, +9.5; **measurable** |
| cooperative success, contact impulse, 40% | +12.8 (+7.0 to +18.5); seeds +12.5, +13.0; **measurable** |
| cooperative success, along the line, 10% | +11.2 (+5.7 to +16.8); seeds +11.5, +11.0; **measurable** |
| cooperative success, along the line, 20% | +10.5 (+5.0 to +16.0); seeds +11.5, +9.5; **measurable** |
| cooperative success, along the line, 25% | +10.0 (+4.3 to +15.7); seeds +11.0, +9.0; **measurable** |
| cooperative success, along the line, 30% | +9.8 (+4.1 to +15.4); seeds +11.0, +8.5; **measurable** |
| cooperative success, along the line, 40% | +8.2 (+2.4 to +14.1); seeds +6.5, +10.0; **measurable** |

**r6 minus r7**

| | difference |
|---|---|
| task success | +2.2 (-1.4 to +5.9); seeds +4.0, +0.5; no measurable difference |
| cooperative success, contact impulse, 10% | +3.5 (+0.4 to +6.6); seeds +4.0, +3.0; **measurable** |
| cooperative success, contact impulse, 20% | +4.2 (+1.1 to +7.4); seeds +4.5, +4.0; **measurable** |
| cooperative success, contact impulse, 25% | +3.8 (+0.6 to +6.9); seeds +4.0, +3.5; **measurable** |
| cooperative success, contact impulse, 30% | +3.5 (+0.4 to +6.6); seeds +4.0, +3.0; **measurable** |
| cooperative success, contact impulse, 40% | +4.8 (+1.4 to +8.1); seeds +5.5, +4.0; **measurable** |
| cooperative success, along the line, 10% | +4.0 (+0.9 to +7.1); seeds +4.0, +4.0; **measurable** |
| cooperative success, along the line, 20% | +4.0 (+0.9 to +7.1); seeds +4.5, +3.5; **measurable** |
| cooperative success, along the line, 25% | +3.8 (+0.7 to +6.8); seeds +4.0, +3.5; **measurable** |
| cooperative success, along the line, 30% | +4.0 (+0.9 to +7.1); seeds +5.0, +3.0; **measurable** |
| cooperative success, along the line, 40% | +3.2 (-0.6 to +7.1); seeds +2.5, +4.0; no measurable difference |

**r7 minus scripted**

| | difference |
|---|---|
| task success | +20.5 (+13.4 to +27.6); seeds +21.0, +20.0; **measurable** |
| cooperative success, contact impulse, 10% | +7.5 (+2.0 to +13.0); seeds +7.5, +7.5; **measurable** |
| cooperative success, contact impulse, 20% | +6.5 (+0.9 to +12.1); seeds +7.0, +6.0; **measurable** |
| cooperative success, contact impulse, 25% | +6.2 (+0.7 to +11.8); seeds +6.5, +6.0; **measurable** |
| cooperative success, contact impulse, 30% | +7.0 (+1.4 to +12.6); seeds +7.5, +6.5; **measurable** |
| cooperative success, contact impulse, 40% | +8.0 (+2.2 to +13.8); seeds +7.0, +9.0; **measurable** |
| cooperative success, along the line, 10% | +7.2 (+1.7 to +12.8); seeds +7.5, +7.0; **measurable** |
| cooperative success, along the line, 20% | +6.5 (+0.9 to +12.1); seeds +7.0, +6.0; **measurable** |
| cooperative success, along the line, 25% | +6.2 (+0.6 to +11.9); seeds +7.0, +5.5; **measurable** |
| cooperative success, along the line, 30% | +5.8 (-0.1 to +11.6); seeds +6.0, +5.5; no measurable difference |
| cooperative success, along the line, 40% | +5.0 (-1.0 to +11.0); seeds +4.0, +6.0; no measurable difference |

## Where the two measures disagree

Task successes that one measure calls cooperative at 25% and the other does not (duck A's share by each measure; impulses in N s as A / B):

| | start | contact share A | along-the-line share A | contact impulse A / B | push impulse A / B |
|---|---|---|---|---|---|
| scripted rendezvous | 164 | 27% | 25% | 4.4 / 12.1 | 2.8 / 8.4 |
| r6 seed 2 | 28 | 71% | 76% | 12.3 / 5.1 | 9.6 / 3.0 |
| r6 seed 2 | 124 | 44% | 22% | 8.3 / 10.7 | 2.3 / 8.1 |
| r7 seed 2 (check-set pick) | 8 | 26% | 21% | 4.9 / 14.2 | 2.9 / 11.3 |
| r7 seed 2 (check-set pick) | 110 | 38% | 24% | 6.1 / 10.0 | 1.9 / 6.3 |
| L2-s2 push policy, L1 set | 2 | 77% | 73% | 16.1 / 4.7 | 9.2 / 3.4 |
| L2-s2 push policy, L2 set | 93 | 67% | 76% | 11.0 / 5.4 | 8.8 / 2.8 |
