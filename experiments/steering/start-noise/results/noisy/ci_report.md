# Confidence intervals (200 starts per policy, 95%)

Success with a Wilson interval, overall and per box-angle side; idle share is the mean over episodes with a 95% interval of the mean.

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg | idle share | overshoots | time-outs |
|---|---|---|---|---|---|---|---|
| clean_s1 | 94% (90% to 97%) | 100% (94% to 100%) of 66 | 94% (86% to 98%) of 67 | 88% (78% to 94%) of 67 | 2% (+-1) | 0% (0% to 2%) | 4% (2% to 8%) |
| noise_s1 | 93% (89% to 96%) | 94% (85% to 98%) of 66 | 97% (90% to 99%) of 67 | 88% (78% to 94%) of 67 | 2% (+-1) | 0% (0% to 2%) | 4% (2% to 7%) |
| clean_s2 | 91% (86% to 94%) | 97% (90% to 99%) of 66 | 97% (90% to 99%) of 67 | 79% (68% to 87%) of 67 | 3% (+-1) | 0% (0% to 2%) | 8% (5% to 13%) |
| noise_s2 | 90% (84% to 93%) | 97% (90% to 99%) of 66 | 96% (88% to 98%) of 67 | 76% (65% to 85%) of 67 | 2% (+-1) | 0% (0% to 2%) | 6% (3% to 10%) |

## Paired differences in success (percentage points, same starts)

| comparison | mean difference | 95% interval | McNemar p (exact) | interval excludes 0 |
|---|---|---|---|---|
| noise_s1 minus clean_s1 | -1.0 | -5.2 to +3.2 | 0.815 | no |
| noise_s2 minus clean_s2 | -1.5 | -6.6 to +3.6 | 0.701 | no |
