# Docking-spot sweep: the L2-s2 push policy under shifted duck placements

*Evaluation only, no training. Policy: night 5 `l2-s2` (`runs/d2-steering-night5/l2-s2/model.zip`, sha256 `ab82e344b275ce617123cf89b70d998f2dbf9003e7fd8feec437607503dd3366`), one training seed. Script: [scripts/rl/docking_sweep.py](../../../scripts/rl/docking_sweep.py); every number below comes from [results.json](results.json) and [results.md](results.md).*

## Question

Where should a duck dock against the box? The push policy was trained with the ducks placed symmetrically (0.10 m either side of the box centre, 0.095 m behind it). If a scripted rendezvous brings the ducks to a different spot, how much does the policy lose, and does any placement beat the trained one?

## What was tested

Each duck's placement is two numbers: its sideways offset from the box centre along the box's long axis (A on the left of the push direction, B on the right), and its setback (distance behind the box centre). The eval set's own start noise (heading, spacing, setback) is added on top, exactly as in training. The env is subclassed in the script; `copush/env.py` is untouched.

| config | A offset | B offset | A setback | B setback |
|---|---|---|---|---|
| baseline (symmetric) | 0.10 | 0.10 | 0.095 | 0.095 |
| B-closer | 0.13 | 0.07 | 0.095 | 0.095 |
| B-closer + A further back | 0.13 | 0.07 | 0.11 | 0.08 |
| B-tight | 0.15 | 0.05 | 0.095 | 0.095 |
| A further back only | 0.10 | 0.10 | 0.11 | 0.08 |

All distances in metres; the spacing between the ducks is 0.20 m in every config. Each config ran on four 200-start sets (clean `stage1_large`, `stage1_noisy_large`, `stage1_L1_large`, `stage1_L2_large`): deterministic, 100 steps, per-start seeds 10000 + i, success = box centre in the target, yaw within 15 degrees, both ducks up, held 1 s. **Check:** the baseline reproduces the saved night 5 evaluation of the same policy exactly (800 of 800 episodes identical in outcome, steps and push share).

## Results

**Success rate** (200 starts per set, 800 for ALL; 95% Wilson intervals)

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| baseline | 97.5% (94.3% to 98.9%) | 93.0% (88.6% to 95.8%) | 90.0% (85.1% to 93.4%) | 88.0% (82.8% to 91.8%) | 92.1% (90.1% to 93.8%) |
| B-closer | 84.5% (78.8% to 88.9%) | 81.5% (75.5% to 86.3%) | 74.5% (68.0% to 80.0%) | 66.5% (59.7% to 72.7%) | 76.8% (73.7% to 79.5%) |
| B-closer+A-back | 89.5% (84.5% to 93.0%) | 82.0% (76.1% to 86.7%) | 68.5% (61.8% to 74.5%) | 61.0% (54.1% to 67.5%) | 75.2% (72.1% to 78.1%) |
| B-tight | 45.0% (38.3% to 51.9%) | 51.0% (44.1% to 57.8%) | 52.5% (45.6% to 59.3%) | 43.0% (36.3% to 49.9%) | 47.9% (44.4% to 51.3%) |
| A-back | 96.0% (92.3% to 98.0%) | 91.0% (86.2% to 94.2%) | 83.5% (77.7% to 88.0%) | 74.5% (68.0% to 80.0%) | 86.2% (83.7% to 88.5%) |

**Difference from the baseline, same starts** (percentage points; 95% interval on the per-start differences; starts won only by the config / only by the baseline)

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| B-closer | -13.0 (-18.3 to -7.7; 3/29) | -11.5 (-17.7 to -5.3; 10/33) | -15.5 (-22.0 to -9.0; 9/40) | -21.5 (-28.6 to -14.4; 9/52) | -15.4 (-18.5 to -12.2; 31/154) |
| B-closer+A-back | -8.0 (-12.5 to -3.5; 3/19) | -11.0 (-17.5 to -4.5; 12/34) | -21.5 (-28.7 to -14.3; 10/53) | -27.0 (-34.8 to -19.2; 12/66) | -16.9 (-20.2 to -13.5; 37/172) |
| B-tight | -52.5 (-59.7 to -45.3; 2/107) | -42.0 (-49.8 to -34.2; 7/91) | -37.5 (-45.7 to -29.3; 11/86) | -45.0 (-52.6 to -37.4; 5/95) | -44.2 (-48.1 to -40.4; 25/379) |
| A-back | -1.5 (-4.4 to +1.4; 3/6) | -2.0 (-6.6 to +2.6; 9/13) | -6.5 (-12.6 to -0.4; 13/26) | -13.5 (-19.8 to -7.2; 9/36) | -5.9 (-8.5 to -3.3; 34/81) |

**Mean steps to success**

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| baseline | 37.2 | 37.6 | 38.2 | 38.4 | 37.8 |
| B-closer | 39.7 | 41.5 | 42.4 | 40.8 | 41.1 |
| B-closer+A-back | 40.4 | 41.7 | 40.3 | 40.9 | 40.8 |
| B-tight | 41.2 | 41.9 | 41.7 | 40.3 | 41.3 |
| A-back | 37.5 | 38.1 | 38.9 | 39.8 | 38.5 |

**Duck A's share of the pushing** (mean over episodes)

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| baseline | 76.7% | 76.6% | 77.0% | 78.4% | 77.2% |
| B-closer | 72.7% | 71.7% | 72.7% | 70.3% | 71.8% |
| B-closer+A-back | 72.4% | 70.2% | 68.9% | 67.8% | 69.8% |
| B-tight | 67.6% | 67.4% | 67.5% | 66.9% | 67.4% |
| A-back | 76.4% | 76.1% | 76.0% | 75.7% | 76.0% |

**Episode endings** (success / time-out / fall / box lost or tipped)

| config | clean | noisy | L1 | L2 |
|---|---|---|---|---|
| baseline | 195 / 5 / 0 / 0 | 186 / 10 / 1 / 3 | 180 / 16 / 3 / 1 | 176 / 19 / 3 / 2 |
| B-closer | 169 / 31 / 0 / 0 | 163 / 37 / 0 / 0 | 149 / 46 / 4 / 1 | 133 / 60 / 6 / 1 |
| B-closer+A-back | 179 / 20 / 1 / 0 | 164 / 32 / 1 / 3 | 137 / 38 / 11 / 14 | 122 / 52 / 9 / 17 |
| B-tight | 90 / 105 / 4 / 1 | 102 / 94 / 4 / 0 | 105 / 87 / 7 / 1 | 86 / 104 / 10 / 0 |
| A-back | 192 / 5 / 2 / 1 | 182 / 10 / 5 / 3 | 167 / 11 / 10 / 12 | 149 / 29 / 8 / 14 |

## Verdict

- **The trained placement wins, on every set.** The baseline reaches 92.1% over the 800 starts. The next best, A further back only, is 5.9 points lower (-8.5 to -3.3); the other two shifted configs are 15 to 17 points lower, and B-tight loses 44 points (92.1% to 47.9%, interval -48.1 to -40.4).
- **Measurable?** On the paired interval, yes for all four alternatives overall, and on every set except A further back on the clean and noisy sets (-1.5 and -2.0, intervals include 0) and on L1 where it only just excludes 0 (-6.5, -12.6 to -0.4; exact test p = 0.053). **The second half of the project's rule (seed rates must not overlap) cannot be checked: only one training seed was evaluated.** So these are preliminary. The gaps (6 to 44 points) are larger than any seed spread seen so far in this project (up to 9 points), but a second seed was not run.
- **Small shifts already cost a lot.** Moving the pair 3 cm toward A (B-closer) costs 11.5 to 21.5 points depending on the set, and the loss grows with start noise (-13.0 clean, -21.5 on L2). B-closer + A further back is better than B-closer on the clean set (89.5% against 84.5%) but worse on L1 and L2 (68.5% and 61.0% against 74.5% and 66.5%), with many more falls and lost boxes there.
- **A more even push does not help.** B-tight gives duck B the biggest share (A's share falls from 77% to 67%) but halves the success rate, mostly through time-outs (105 of 200 clean starts). A sits 0.15 m from the box centre, beyond the box's half-length of 0.14 m, so it is at or past the end of the box's long face.
- **Speed:** the baseline is also fastest (37.8 steps to success against 38.5 to 41.3).

## What it means for the rendezvous phase

The policy is only reliable where it was trained to expect the ducks. A scripted phase should deliver each duck to the baseline spot (0.095 m behind the box centre, 0.10 m to either side), facing the push direction. The smallest sideways shift tested, 3 cm, already costs 11.5 to 21.5 points, and the smallest setback shift, 1.5 cm (A further back), costs 5.9 points over the 800 starts (3.3 to 8.5; not measurable on the clean and noisy sets alone). So the docking should be accurate to under about 2 cm, and possibly tighter; this sweep did not test shifts under 1.5 cm. (Corrected 2026-11-25: this sentence first named 3 cm as the smallest shift tested.) This sweep **cannot** say which spot is best for a policy trained on a different placement: every policy here trained at the baseline, so any shift is also a shift away from its training. Finding a better docking spot would need training on the new spot, which this run did not do.

## Caveats

- One policy, one training seed (seed 2 of the L2 runs).
- **Start redraws.** The env re-draws a noisy start that fails its start check (a duck down, ducks closer than 0.12 m, or the box nudged more than 1 cm or turned more than 2 degrees while settling). With A further back the redraw rate rises on the noisy sets, which means those configs were scored on starts that passed the check, which flatters them if anything:

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| baseline | 0.0% | 0.5% | 2.4% | 0.0% | 1.0% |
| B-closer | 0.0% | 0.5% | 2.9% | 0.0% | 1.2% |
| B-closer+A-back | 0.0% | 7.0% | 13.8% | 16.7% | 12.7% |
| B-tight | 0.0% | 0.5% | 2.9% | 0.0% | 1.2% |
| A-back | 0.0% | 4.3% | 11.1% | 15.6% | 10.6% |

  In those cases the noise draws are no longer identical to the baseline's for the same start, so the pairing is by box pose and seed, not by identical noise.
- Four challengers were each compared on five views, with no correction for the number of comparisons. The gaps are far from the intervals' edges except A further back on L1.
