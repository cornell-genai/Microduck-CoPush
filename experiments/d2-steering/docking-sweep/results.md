# Docking sweep: runs/d2-steering-night5/l2-s2/model.zip

200 starts per set, deterministic, 100-step limit, per-start seeds 10000 + i; policy seed 2 only. Baseline check against the saved night 5 evaluation (reason, steps, push share): clean 200/200 identical, noisy 200/200 identical, L1 200/200 identical, L2 200/200 identical.

## Configs

| config | A offset | B offset | A setback | B setback |
|---|---|---|---|---|
| baseline | 0.1 | 0.1 | 0.095 | 0.095 |
| B-closer | 0.13 | 0.07 | 0.095 | 0.095 |
| B-closer+A-back | 0.13 | 0.07 | 0.11 | 0.08 |
| B-tight | 0.15 | 0.05 | 0.095 | 0.095 |
| A-back | 0.1 | 0.1 | 0.11 | 0.08 |

## Success rate (95% Wilson interval)

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| baseline | 97.5% (94.3% to 98.9%) | 93.0% (88.6% to 95.8%) | 90.0% (85.1% to 93.4%) | 88.0% (82.8% to 91.8%) | 92.1% (90.1% to 93.8%) |
| B-closer | 84.5% (78.8% to 88.9%) | 81.5% (75.5% to 86.3%) | 74.5% (68.0% to 80.0%) | 66.5% (59.7% to 72.7%) | 76.8% (73.7% to 79.5%) |
| B-closer+A-back | 89.5% (84.5% to 93.0%) | 82.0% (76.1% to 86.7%) | 68.5% (61.8% to 74.5%) | 61.0% (54.1% to 67.5%) | 75.2% (72.1% to 78.1%) |
| B-tight | 45.0% (38.3% to 51.9%) | 51.0% (44.1% to 57.8%) | 52.5% (45.6% to 59.3%) | 43.0% (36.3% to 49.9%) | 47.9% (44.4% to 51.3%) |
| A-back | 96.0% (92.3% to 98.0%) | 91.0% (86.2% to 94.2%) | 83.5% (77.7% to 88.0%) | 74.5% (68.0% to 80.0%) | 86.2% (83.7% to 88.5%) |

## Paired difference from baseline, percentage points (95% interval; starts won only by the config / only by baseline)

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| B-closer | -13.0 (-18.3 to -7.7; 3/29) | -11.5 (-17.7 to -5.3; 10/33) | -15.5 (-22.0 to -9.0; 9/40) | -21.5 (-28.6 to -14.4; 9/52) | -15.4 (-18.5 to -12.2; 31/154) |
| B-closer+A-back | -8.0 (-12.5 to -3.5; 3/19) | -11.0 (-17.5 to -4.5; 12/34) | -21.5 (-28.7 to -14.3; 10/53) | -27.0 (-34.8 to -19.2; 12/66) | -16.9 (-20.2 to -13.5; 37/172) |
| B-tight | -52.5 (-59.7 to -45.3; 2/107) | -42.0 (-49.8 to -34.2; 7/91) | -37.5 (-45.7 to -29.3; 11/86) | -45.0 (-52.6 to -37.4; 5/95) | -44.2 (-48.1 to -40.4; 25/379) |
| A-back | -1.5 (-4.4 to +1.4; 3/6) | -2.0 (-6.6 to +2.6; 9/13) | -6.5 (-12.6 to -0.4; 13/26) | -13.5 (-19.8 to -7.2; 9/36) | -5.9 (-8.5 to -3.3; 34/81) |

## Mean steps to success (successful episodes only)

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| baseline | 37.2 | 37.6 | 38.2 | 38.4 | 37.8 |
| B-closer | 39.7 | 41.5 | 42.4 | 40.8 | 41.1 |
| B-closer+A-back | 40.4 | 41.7 | 40.3 | 40.9 | 40.8 |
| B-tight | 41.2 | 41.9 | 41.7 | 40.3 | 41.3 |
| A-back | 37.5 | 38.1 | 38.9 | 39.8 | 38.5 |

## Duck A's share of the pushing (mean over episodes)

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| baseline | 76.7% | 76.6% | 77.0% | 78.4% | 77.2% |
| B-closer | 72.7% | 71.7% | 72.7% | 70.3% | 71.8% |
| B-closer+A-back | 72.4% | 70.2% | 68.9% | 67.8% | 69.8% |
| B-tight | 67.6% | 67.4% | 67.5% | 66.9% | 67.4% |
| A-back | 76.4% | 76.1% | 76.0% | 75.7% | 76.0% |

## Duck A's share of the pushing (mean over successful episodes)

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| baseline | 76.3% | 75.5% | 76.5% | 77.3% | 76.4% |
| B-closer | 70.1% | 71.0% | 72.4% | 69.9% | 70.9% |
| B-closer+A-back | 71.3% | 71.3% | 69.5% | 71.4% | 70.9% |
| B-tight | 58.4% | 61.0% | 61.4% | 62.2% | 60.8% |
| A-back | 76.0% | 75.5% | 78.2% | 77.4% | 76.7% |

## Start redraw rate (draws that failed the start check; 0 when the set has no start noise)

| config | clean | noisy | L1 | L2 | ALL |
|---|---|---|---|---|---|
| baseline | 0.0% | 0.5% | 2.4% | 0.0% | 1.0% |
| B-closer | 0.0% | 0.5% | 2.9% | 0.0% | 1.2% |
| B-closer+A-back | 0.0% | 7.0% | 13.8% | 16.7% | 12.7% |
| B-tight | 0.0% | 0.5% | 2.9% | 0.0% | 1.2% |
| A-back | 0.0% | 4.3% | 11.1% | 15.6% | 10.6% |

## Episode endings (count per set; success / time-out / fall / box lost or tipped)

| config | clean | noisy | L1 | L2 |
|---|---|---|---|---|
| baseline | 195 / 5 / 0 / 0 | 186 / 10 / 1 / 3 | 180 / 16 / 3 / 1 | 176 / 19 / 3 / 2 |
| B-closer | 169 / 31 / 0 / 0 | 163 / 37 / 0 / 0 | 149 / 46 / 4 / 1 | 133 / 60 / 6 / 1 |
| B-closer+A-back | 179 / 20 / 1 / 0 | 164 / 32 / 1 / 3 | 137 / 38 / 11 / 14 | 122 / 52 / 9 / 17 |
| B-tight | 90 / 105 / 4 / 1 | 102 / 94 / 4 / 0 | 105 / 87 / 7 / 1 | 86 / 104 / 10 / 0 |
| A-back | 192 / 5 / 2 / 1 | 182 / 10 / 5 / 3 | 167 / 11 / 10 / 12 | 149 / 29 / 8 / 14 |

Highest overall success (all four sets together): **baseline**. Wall time 623.1 s.
