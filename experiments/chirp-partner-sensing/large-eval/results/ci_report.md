# Confidence intervals (200 starts per policy, 95%)

Success with a Wilson interval, overall and per box-angle side; idle share is the mean over episodes with a 95% interval of the mean.

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg | idle share | overshoots | time-outs |
|---|---|---|---|---|---|---|---|
| d2_exact | 66% (60% to 73%) | 97% (90% to 99%) of 67 | 87% (76% to 93%) of 67 | 15% (8% to 26%) of 66 | 15% (+-1) | 9% (6% to 14%) | 22% (16% to 28%) |
| d1 | 64% (57% to 70%) | 96% (88% to 98%) of 67 | 87% (76% to 93%) of 67 | 9% (4% to 18%) of 66 | 21% (+-2) | 12% (9% to 18%) | 30% (25% to 37%) |
| part2_seed1 | 63% (56% to 69%) | 97% (90% to 99%) of 67 | 81% (70% to 88%) of 67 | 11% (5% to 20%) of 66 | 26% (+-2) | 14% (9% to 19%) | 32% (26% to 39%) |
| run2_seed2 | 63% (56% to 69%) | 96% (88% to 98%) of 67 | 87% (76% to 93%) of 67 | 6% (2% to 15%) of 66 | 20% (+-2) | 14% (10% to 20%) | 30% (25% to 37%) |
| run1_true_heading | 64% (57% to 70%) | 94% (86% to 98%) of 67 | 87% (76% to 93%) of 67 | 9% (4% to 18%) of 66 | 13% (+-2) | 11% (7% to 16%) | 30% (24% to 37%) |

## Paired differences in success (percentage points, same starts)

| comparison | mean difference | 95% interval | McNemar p (exact) | interval excludes 0 |
|---|---|---|---|---|
| run1_true_heading minus part2_seed1 | +0.5 | -4.8 to +5.8 | 1.000 | no |
| run1_true_heading minus run2_seed2 | +0.5 | -3.8 to +4.8 | 1.000 | no |
| part2_seed1 minus run2_seed2 | +0.0 | -5.0 to +5.0 | 1.000 | no |
| d2_exact minus run1_true_heading | +3.0 | -2.2 to +8.2 | 0.345 | no |
| d2_exact minus part2_seed1 | +3.5 | -1.8 to +8.8 | 0.265 | no |
| d2_exact minus run2_seed2 | +3.5 | -1.2 to +8.2 | 0.210 | no |
| part2_seed1 minus d1 | -1.0 | -6.2 to +4.2 | 0.851 | no |
| run2_seed2 minus d1 | -1.0 | -5.2 to +3.2 | 0.815 | no |
| d2_exact minus d1 | +2.5 | -2.2 to +7.2 | 0.405 | no |
| run1_true_heading minus the mean of part2_seed1 and run2_seed2 | +0.5 | -3.6 to +4.6 | n/a | no |
| &nbsp;&nbsp;side < -15 deg (n=67) | -2.2 | -8.3 to +3.8 | n/a | no |
| &nbsp;&nbsp;side -15 to +15 deg (n=67) | +3.0 | -6.1 to +12.0 | n/a | no |
| &nbsp;&nbsp;side > +15 deg (n=66) | +0.8 | -5.0 to +6.5 | n/a | no |
