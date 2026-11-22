# Central steering: control versus stand-still

*Updated 2026-11-21 22:42 by `scripts/rl/overnight_central_steering.py`.*

## Steps

| step | status | finished |
|---|---|---|
| baseline | done | 2026-11-21 13:11:08 |
| control_s1 | done | 2026-11-21 15:56:50 |
| control_s2 | done | 2026-11-21 18:28:53 |
| stand_s1 | done | 2026-11-21 20:41:50 |
| stand_s2 | done | 2026-11-21 22:37:57 |
| eval | done | 2026-11-21 22:41:20 |
| clips | done | 2026-11-21 22:42:20 |

## Setup

- Central controller, Stage 1 random box starts, reward v1.1.
- Both groups warm-start from the released Stage 1 central policy.
- Fixed 1,000,000-step budget, no early stopping, two PPO seeds per group.
- The only group difference is `env.stand_still.enabled`.
- Full results use the same 200 held-out starts for every policy.

## Zero-shot diagnostic

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| stage1 | 60% (54% to 67%) | 84% (73% to 91%) | 90% (80% to 95%) | 8% (3% to 17%) |
| stage1_zero_shot_hold | 20% (15% to 26%) | 25% (16% to 37%) | 27% (18% to 39%) | 8% (3% to 17%) |

## Success

| policy | overall | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|---|
| stage1 | 60% (54% to 67%) | 84% (73% to 91%) | 90% (80% to 95%) | 8% (3% to 17%) |
| control_s1 | 66% (59% to 72%) | 91% (82% to 96%) | 85% (75% to 92%) | 21% (13% to 33%) |
| control_s2 | 68% (61% to 74%) | 99% (92% to 100%) | 87% (76% to 93%) | 18% (11% to 29%) |
| stand_s1 | 96% (92% to 98%) | 97% (90% to 99%) | 99% (92% to 100%) | 92% (83% to 97%) |
| stand_s2 | 98% (96% to 99%) | 99% (92% to 100%) | 100% (95% to 100%) | 97% (90% to 99%) |

## Matched-group verdict

| scope | stand-still minus control | 95% interval | seed rates (stand; control) | verdict |
|---|---|---|---|---|
| overall | +30.2 points | +24.2 to +36.3 | 96%, 98%; 66%, 68% | **up** |
| < -15 deg (n=67) | +3.0 points | -1.1 to +7.1 | 97%, 99%; 91%, 99% | **no measurable difference** |
| -15 to +15 deg (n=67) | +13.4 points | +6.7 to +20.2 | 99%, 100%; 85%, 87% | **up** |
| > +15 deg (n=66) | +75.0 points | +65.2 to +84.8 | 92%, 97%; 21%, 18% | **up** |

## Failure modes and behavior

| policy | time-outs | falls | box lost/tipped | overshoots | both held >=30% | pivots | push share A |
|---|---|---|---|---|---|---|---|
| stage1 | 63 | 14 | 2 | 60 | 0 | 0 | 47% |
| control_s1 | 55 | 12 | 1 | 45 | 0 | 0 | 50% |
| control_s2 | 45 | 16 | 3 | 46 | 0 | 0 | 52% |
| stand_s1 | 7 | 1 | 0 | 0 | 3 | 98 | 77% |
| stand_s2 | 3 | 0 | 0 | 0 | 1 | 117 | 80% |

Raw comparison: [results/comparison/comparison.md](results/comparison/comparison.md).
