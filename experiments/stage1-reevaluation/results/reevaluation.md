# Re-evaluation on 200 held-out starts (stage1_large) against the old 50-start numbers

One deterministic episode per start. Old = the 50-start test-set number recorded in the READMEs (**superseded**); new = this evaluation with a Wilson 95% interval. "Old inside new interval" says whether the old number was within what the larger set allows.

## 1. Named policies

| policy | old, 50 starts (superseded) | new, 200 starts (95% interval) | old inside new interval |
|---|---|---|---|
| stage 1, central (one network, both ducks) | 60% (30/50) | **58% (51% to 65%)** | yes |
| 01_reference (central from scratch, seed 1) | 50% (25/50) | **50% (44% to 57%)** | yes |
| stage 1b A (central, hard starts oversampled) | 72% (36/50) | **70% (64% to 76%)** | yes |
| stage 1b B (central, smaller time penalty) | 68% (34/50) | **65% (58% to 71%)** | yes |
| D1 (decentralized, own view only) | 60% (30/50) | **64% (57% to 70%)** | yes |
| D2 (decentralized, own view + partner) | 74% (37/50) | **66% (60% to 73%)** | **no** |
| D2 distilled, seed 1 (fixed-start run) | 48% (24/50) | **51% (44% to 58%)** | yes |
| D2 distilled, seed 2 | 48% (24/50) | **49% (42% to 56%)** | yes |
| D2 distilled, seed 3 | 58% (29/50) | **55% (48% to 61%)** | yes |
| pivot_push (script) | 32% (16/50) | **38% (32% to 45%)** | **no** |
| push_steer (script) | 18% (9/50) | **20% (15% to 26%)** | yes |

Per box-angle side on the 200 starts (successes / starts):

| policy | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|
| stage 1, central (one network, both ducks) | 54/67 (81%, 70% to 88%) | 59/67 (88%, 78% to 94%) | 3/66 (5%, 2% to 13%) |
| 01_reference (central from scratch, seed 1) | 43/67 (64%, 52% to 75%) | 54/67 (81%, 70% to 88%) | 4/66 (6%, 2% to 15%) |
| stage 1b A (central, hard starts oversampled) | 66/67 (99%, 92% to 100%) | 61/67 (91%, 82% to 96%) | 14/66 (21%, 13% to 33%) |
| stage 1b B (central, smaller time penalty) | 62/67 (93%, 84% to 97%) | 60/67 (90%, 80% to 95%) | 8/66 (12%, 6% to 22%) |
| D1 (decentralized, own view only) | 64/67 (96%, 88% to 98%) | 58/67 (87%, 76% to 93%) | 6/66 (9%, 4% to 18%) |
| D2 (decentralized, own view + partner) | 65/67 (97%, 90% to 99%) | 58/67 (87%, 76% to 93%) | 10/66 (15%, 8% to 26%) |
| D2 distilled, seed 1 (fixed-start run) | 42/67 (63%, 51% to 73%) | 55/67 (82%, 71% to 89%) | 5/66 (8%, 3% to 17%) |
| D2 distilled, seed 2 | 35/67 (52%, 40% to 64%) | 56/67 (84%, 73% to 91%) | 7/66 (11%, 5% to 20%) |
| D2 distilled, seed 3 | 48/67 (72%, 60% to 81%) | 57/67 (85%, 75% to 92%) | 4/66 (6%, 2% to 15%) |
| pivot_push (script) | 31/67 (46%, 35% to 58%) | 30/67 (45%, 33% to 57%) | 16/66 (24%, 16% to 36%) |
| push_steer (script) | 38/67 (57%, 45% to 68%) | 2/67 (3%, 1% to 10%) | 0/66 (0%, 0% to 6%) |

## 2. From-scratch policies, 10 seeds each (trained on the fixed start, tested on random starts)

| seed | central, old (50) | central, new (200) | D2, old (50) | D2, new (200) |
|---|---|---|---|---|
| 1 | 50% | 50% (44% to 57%) | 32% | 32% (26% to 39%) |
| 2 | 28% | 34% (28% to 41%) | 28% | 28% (23% to 35%) |
| 3 | 44% | 54% (47% to 60%) | 38% | 28% (22% to 35%) |
| 4 | 40% | 42% (36% to 49%) | 50% | 56% (49% to 63%) |
| 5 | 32% | 34% (28% to 41%) | 34% | 38% (32% to 45%) |
| 6 | 48% | 47% (40% to 54%) | 60% | 54% (47% to 61%) |
| 7 | 54% | 52% (46% to 59%) | 40% | 40% (34% to 47%) |
| 8 | 52% | 48% (41% to 54%) | 28% | 37% (31% to 44%) |
| 9 | 64% | 55% (48% to 61%) | 38% | 36% (29% to 42%) |
| 10 | 44% | 38% (31% to 44%) | 48% | 51% (44% to 58%) |

| group (10 seeds) | old mean (50-start rates) | new mean (200 starts), 95% interval across seeds | range across seeds (new) |
|---|---|---|---|
| central from scratch | 46% | **45%** (40% to 51%) | 34% to 55% |
| D2 from scratch | 40% | **40%** (33% to 47%) | 28% to 56% |

Central minus D2 from scratch: old +6 points; new **+5.3 points** (95% interval -3.5 to +14.0, Welch on the seed rates): no measurable difference.

D2 distilled (3 seeds): old 51%; new **52%** (45% to 58% across seeds, a wide interval from only 3 seeds).

## 3. Which earlier claims hold?

Paired difference in success on the same 200 starts (percentage points), 95% interval, exact McNemar p. For "beats" claims, "holds" = the interval excludes 0 in the claimed direction and the exact test has p < 0.05; for "matches" claims, "holds" = the interval contains 0. For the two "did not fix" claims the first policy is the fix, so "holds" means the fix did help the long-turn side (the old claim is not supported).

| claim (old 50-start evidence) | difference | 95% interval | McNemar p | verdict |
|---|---|---|---|---|
| PPO (stage 1) beats 01_reference (60% against 50%) | +7.5 | +1.8 to +13.2 | 0.017 | holds |
| PPO (stage 1) beats the best script, pivot_push (60% against 32%) | +19.5 | +10.7 to +28.3 | 0.000 | holds |
| PPO (stage 1) beats push_steer (60% against 18%) | +38.0 | +29.7 to +46.3 | 0.000 | holds |
| Stage 1b A beats stage 1 (72% against 60%) | +12.5 | +7.7 to +17.3 | 0.000 | holds |
| Stage 1b B beats stage 1 (68% against 60%) | +7.0 | +2.5 to +11.5 | 0.004 | holds |
| D2 beats the central stage 1 policy (74% against 60%) | +8.5 | +3.7 to +13.3 | 0.001 | holds |
| Control for that: stage 1b A (central, also 1M extra steps) is as good as D2 | +4.0 | -0.1 to +8.1 | 0.096 | holds (no measurable difference) |
| D2 beats D1: seeing the partner helps (74% against 60%) | +2.5 | -2.2 to +7.2 | 0.405 | no measurable difference |
| D1 matches the central stage 1 policy (60% against 60%) | +6.0 | +1.5 to +10.5 | 0.017 | does not hold: first is higher |
| D2 wins the long-turn side more than D1 (5/17 against 1/17) (side > +15 deg, n=66) | +6.1 | -3.3 to +15.4 | 0.344 | no measurable difference |
| D2 wins the long-turn side more than central stage 1 (5/17 against 2/17) (side > +15 deg, n=66) | +10.6 | +3.1 to +18.1 | 0.016 | holds |
| Stage 1b A did not fix the long-turn side (4/17 against 2/17) (side > +15 deg, n=66) | +16.7 | +7.6 to +25.7 | 0.001 | holds |
| Stage 1b B did not fix the long-turn side (1/17 against 2/17) (side > +15 deg, n=66) | +7.6 | +1.1 to +14.0 | 0.062 | borderline (the interval and the exact test disagree) |

## 4. Wall time (8 worker processes per policy, starts dealt out round robin)

| policy | wall time |
|---|---|
| stage1_central | 34 s |
| central_scratch_s1 | 41 s |
| stage1b_A | 35 s |
| stage1b_B | 34 s |
| d1 | 35 s |
| d2 | 34 s |
| d2_distilled_s1 | 42 s |
| d2_distilled_s2 | 41 s |
| d2_distilled_s3 | 39 s |
| central_scratch_s2 | 45 s |
| central_scratch_s3 | 41 s |
| central_scratch_s4 | 47 s |
| central_scratch_s5 | 47 s |
| central_scratch_s6 | 40 s |
| central_scratch_s7 | 39 s |
| central_scratch_s8 | 38 s |
| central_scratch_s9 | 40 s |
| central_scratch_s10 | 47 s |
| d2_scratch_s1 | 49 s |
| d2_scratch_s2 | 50 s |
| d2_scratch_s3 | 57 s |
| d2_scratch_s4 | 48 s |
| d2_scratch_s5 | 55 s |
| d2_scratch_s6 | 44 s |
| d2_scratch_s7 | 48 s |
| d2_scratch_s8 | 50 s |
| d2_scratch_s9 | 50 s |
| d2_scratch_s10 | 42 s |
| pivot_push | 42 s |
| push_steer | 47 s |
| **total, 30 policies** | **21.7 min** |
