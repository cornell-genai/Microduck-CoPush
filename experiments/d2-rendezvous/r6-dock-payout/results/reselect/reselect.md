## Checkpoint selection (official r6 numbers)

r6 first picked each seed's best.zip by most dockings on the test set (`experiments/test_sets/rendezvous_large.json`), the same 200 starts the results are reported on. That is selection on the test set (AGENTS.md: checkpoints are picked on a separate check set). The numbers in this section replace the test-set pick and are the official r6 numbers.

- **Check set:** `experiments/test_sets/rendezvous_check.json`, 200 new starts from the same distribution as the test set (same box range as a Latin hypercube, same 0.2-0.8 m duck distances and any bearing and heading, the same 160 uniform / 20 near-symmetric / 20 wrong-side split), with their own seeds (box poses 20261124, ducks 20261125, episode seeds 20000 + i). No start and no box pose repeats a test-set one (checked when the set is made, and by a test).
- **Candidates:** training kept only the newest checkpoint, so the every-200k checkpoints are gone. What is left per seed is the final checkpoint (step 2002944) and best.zip (the old test-set pick). The final checkpoint is the only one not chosen with the test set, so it is the official pick (as the re-selection plan says when intermediate checkpoints were not saved). best.zip's check-set score is shown for information.

**Check set, rendezvous alone** (50 steps, the training ending, as the training evals)

| seed | checkpoint | docked | position / heading error (mean) | used |
|---|---|---|---|---|
| s1 | final, step 2002944 (also the old best.zip) | 82.0% (76.1% to 86.7%) | 3.0 cm / 8.0 deg | **yes** |
| s2 | final, step 2002944 | 72.5% (65.9% to 78.2%) | 2.9 cm / 6.5 deg | **yes** |
| s2 | old best.zip, step 2000000 (picked on the test set) | 69.0% (62.3% to 75.0%) | 3.5 cm / 9.0 deg | no |

- **s1:** step 2002944, unchanged (the old pick was already the final checkpoint); **s2:** step 2002944, changed from step 2000000.

**Test set, full pipeline** (200 starts; rendezvous up to 50 steps, then the frozen push policy; 95% intervals)

| controller | docked in 50 steps | end-to-end push success | position error at handoff | heading error at handoff |
|---|---|---|---|---|
| **dock payout s1, check-set pick = final (official)** | 87.0% (81.6% to 91.0%) | 90.0% (85.1% to 93.4%) | 2.6 cm (2.1 to 3.0) | 5.9 deg (4.2 to 7.5) |
| **dock payout s2, check-set pick = final (official)** | 75.0% (68.6% to 80.5%) | 85.5% (80.0% to 89.7%) | 3.7 cm (2.9 to 4.4) | 7.5 deg (5.6 to 9.5) |
| dock payout s1, old test-set pick | same checkpoint as the final one; re-run gives identical episodes | | | |
| dock payout s2, old test-set pick (step 2000000, superseded) | 78.5% (72.3% to 83.6%) | 86.5% (81.1% to 90.6%) | 3.6 cm (2.8 to 4.3) | 7.8 deg (5.5 to 10.2) |
| scripted | 48.0% (41.2% to 54.9%) | 65.0% (58.2% to 71.3%) | 4.9 cm (4.3 to 5.5) | 26.9 deg (22.8 to 31.0) |
| r5 BC warm start s1 (test-set pick, not re-picked) | 64.5% (57.7% to 70.8%) | 71.5% (64.9% to 77.3%) | 6.6 cm (5.2 to 8.0) | 21.2 deg (16.5 to 26.0) |
| r5 BC warm start s2 (test-set pick, not re-picked) | 52.0% (45.1% to 58.8%) | 62.5% (55.6% to 68.9%) | 6.6 cm (5.5 to 7.7) | 29.7 deg (24.7 to 34.6) |

Position and heading error: mean over the 200 starts of the two ducks' mean, with a 95% interval for that mean.


**Against scripted (the fixed rule: the paired interval excludes 0 and both seed rates are on the same side)** (same 200 starts, paired; seeds averaged per start)

- docked in 50 steps: dock payout minus scripted +33.0 points (+25.8 to +40.2); seeds 87.0, 75.0 vs scripted 48.0: **measurably better**
- end-to-end push success: dock payout minus scripted +22.8 points (+15.7 to +29.8); seeds 90.0, 85.5 vs scripted 65.0: **measurably better**
- heading error at handoff: dock payout minus scripted -20.2 deg (-24.2 to -16.3); seeds 5.9, 7.5 vs scripted 26.9: **measurable difference**
- position error at handoff: dock payout minus scripted -1.8 cm (-2.5 to -1.0); seeds 2.6, 3.7 vs scripted 4.9: **measurable difference**

**Against r5, BC warm start (both seeds averaged)** (same 200 starts, paired; seeds averaged per start)

- docked in 50 steps: dock payout minus r5 +22.8 points (+16.2 to +29.3); seeds 87.0, 75.0 vs r5 58.2: **measurable difference**
- end-to-end push success: dock payout minus r5 +20.8 points (+15.2 to +26.3); seeds 90.0, 85.5 vs r5 67.0: **measurable difference**
- heading error at handoff: dock payout minus r5 -18.7 deg (-23.0 to -14.5); seeds 5.9, 7.5 vs r5 25.4: **measurable difference**
- position error at handoff: dock payout minus r5 -3.4 cm (-4.6 to -2.3); seeds 2.6, 3.7 vs r5 6.6: **measurable difference**

r5 has the same flaw: its best.zip was also picked on the test set, and its checkpoints were not re-picked (they are gone too, and only its final checkpoints remain). Its numbers above are its old test-set picks, which favor r5, so the gap to r5 is if anything understated.

