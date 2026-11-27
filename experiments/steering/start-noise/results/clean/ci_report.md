# Confidence intervals (200 starts per policy, 95%)

Success with a Wilson interval, overall and per box-angle side; idle share is the mean over episodes with a 95% interval of the mean.

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg | idle share | overshoots | time-outs |
|---|---|---|---|---|---|---|---|
| clean_s1 | 96% (92% to 98%) | 97% (90% to 99%) of 67 | 99% (92% to 100%) of 67 | 92% (83% to 97%) of 66 | 2% (+-1) | 0% (0% to 2%) | 4% (2% to 7%) |
| noise_s1 | 94% (90% to 97%) | 97% (90% to 99%) of 67 | 99% (92% to 100%) of 67 | 88% (78% to 94%) of 66 | 2% (+-1) | 0% (0% to 2%) | 4% (2% to 8%) |
| clean_s2 | 98% (96% to 99%) | 99% (92% to 100%) of 67 | 100% (95% to 100%) of 67 | 97% (90% to 99%) of 66 | 3% (+-1) | 0% (0% to 2%) | 2% (1% to 4%) |
| noise_s2 | 92% (88% to 95%) | 99% (92% to 100%) of 67 | 99% (92% to 100%) of 67 | 80% (69% to 88%) of 66 | 2% (+-1) | 0% (0% to 2%) | 6% (3% to 10%) |

## Paired differences in success (percentage points, same starts)

| comparison | mean difference | 95% interval | McNemar p (exact) | interval excludes 0 |
|---|---|---|---|---|
| noise_s1 minus clean_s1 | -1.5 | -5.3 to +2.3 | 0.607 | no |
| noise_s2 minus clean_s2 | -6.0 | -10.1 to -1.9 | 0.008 | yes |
