# Central steering: wider box angles

*Updated 2026-11-24 05:02 by `scripts/rl/overnight_wide_angles.py`.*

## Steps

| step | status | finished |
|---|---|---|
| baseline | done | 2026-11-23 22:25:16 |
| train_s1 | done | 2026-11-24 01:31:51 |
| train_s2 | done | 2026-11-24 04:42:11 |
| eval_wide | done | 2026-11-24 04:51:28 |
| forgetting | done | 2026-11-24 05:00:06 |
| clips | done | 2026-11-24 05:02:38 |

## Setup

- Central controller with stand-still, warm-started from the matching successful ±45-degree seed.
- One task change: final box angle range ±45 → ±90 degrees.
- Auto-widen levels: ±45, ±56.25, ±67.5, ±78.75 and ±90 degrees.
- Two seeds, fixed 1,000,000-step budget, 200 final test starts, 50 separate fixed checks.

## Zero-shot on ±90 degrees

| policy | overall | -90..-45 deg | -45..-15 deg | -15..15 deg | 15..45 deg | 45..90 deg |
|---|---|---|---|---|---|---|
| reference_s1 | 70% (63% to 75%) | 56% (42% to 69%) | 91% (76% to 97%) | 100% (90% to 100%) | 97% (85% to 99%) | 30% (19% to 44%) |
| reference_s2 | 72% (65% to 78%) | 54% (40% to 67%) | 97% (85% to 99%) | 94% (80% to 98%) | 100% (90% to 100%) | 40% (28% to 54%) |

## Curriculum

| seed | steps | reached full range | final check success |
|---|---|---|---|
| 1 | 1001472 | 400000 | 88% |
| 2 | 1001472 | 400000 | 90% |

## Final ±90-degree result

| policy | overall | -90..-45 deg | -45..-15 deg | -15..15 deg | 15..45 deg | 45..90 deg |
|---|---|---|---|---|---|---|
| reference_s1 | 70% (63% to 75%) | 56% (42% to 69%) | 91% (76% to 97%) | 100% (90% to 100%) | 97% (85% to 99%) | 30% (19% to 44%) |
| reference_s2 | 72% (65% to 78%) | 54% (40% to 67%) | 97% (85% to 99%) | 94% (80% to 98%) | 100% (90% to 100%) | 40% (28% to 54%) |
| wide_s1 | 92% (87% to 95%) | 84% (71% to 92%) | 97% (85% to 99%) | 97% (85% to 99%) | 100% (90% to 100%) | 88% (76% to 94%) |
| wide_s2 | 86% (81% to 91%) | 90% (79% to 96%) | 94% (80% to 98%) | 100% (90% to 100%) | 91% (77% to 97%) | 66% (52% to 78%) |

| scope | wide-trained minus reference | 95% interval | seed rates (wide; reference) | verdict |
|---|---|---|---|---|
| overall | +18.5 points | +13.4 to +23.6 | 92%, 86%; 70%, 72% | **up** |
| -90..-45 deg (n=50) | +32.0 points | +21.2 to +42.8 | 84%, 90%; 56%, 54% | **up** |
| -45..-15 deg (n=33) | +1.5 points | -5.2 to +8.2 | 97%, 94%; 91%, 97% | **no measurable difference** |
| -15..15 deg (n=33) | +1.5 points | -3.7 to +6.7 | 97%, 100%; 100%, 94% | **no measurable difference** |
| 15..45 deg (n=34) | -2.9 points | -7.0 to +1.1 | 100%, 91%; 97%, 100% | **no measurable difference** |
| 45..90 deg (n=50) | +42.0 points | +29.7 to +54.3 | 88%, 66%; 30%, 40% | **up** |

### Failure modes and behavior

| policy | time-outs | falls | box lost/tipped | overshoots | both held >=30% | pivots | push share A | lazy duck |
|---|---|---|---|---|---|---|---|---|
| reference_s1 | 46 | 14 | 1 | 42 | 4 | 103 | 70% | 76 |
| reference_s2 | 40 | 14 | 2 | 41 | 2 | 118 | 70% | 79 |
| wide_s1 | 8 | 5 | 3 | 0 | 3 | 137 | 64% | 79 |
| wide_s2 | 23 | 3 | 1 | 8 | 4 | 112 | 65% | 79 |

Raw comparison: [results/wide/comparison.md](results/wide/comparison.md).

## Stage 1 forgetting check

| policy | overall | -91..-15 deg | -15..15 deg | 15..91 deg |
|---|---|---|---|---|
| reference_s1 | 96% (92% to 98%) | 97% (90% to 99%) | 99% (92% to 100%) | 92% (83% to 97%) |
| reference_s2 | 98% (96% to 99%) | 99% (92% to 100%) | 100% (95% to 100%) | 97% (90% to 99%) |
| wide_s1 | 93% (89% to 96%) | 94% (86% to 98%) | 90% (80% to 95%) | 95% (87% to 98%) |
| wide_s2 | 98% (95% to 99%) | 100% (95% to 100%) | 96% (88% to 98%) | 98% (92% to 100%) |

| scope | wide-trained minus reference | 95% interval | seed rates (wide; reference) | verdict |
|---|---|---|---|---|
| overall | -1.8 points | -4.3 to +0.8 | 93%, 98%; 96%, 98% | **no measurable difference** |
| -91..-15 deg (n=67) | -0.7 points | -4.6 to +3.1 | 94%, 100%; 97%, 99% | **no measurable difference** |
| -15..15 deg (n=67) | -6.7 points | -11.8 to -1.7 | 90%, 96%; 99%, 100% | **down** |
| 15..91 deg (n=66) | +2.3 points | -1.6 to +6.2 | 95%, 98%; 92%, 97% | **no measurable difference** |

### Failure modes and behavior

| policy | time-outs | falls | box lost/tipped | overshoots | both held >=30% | pivots | push share A | lazy duck |
|---|---|---|---|---|---|---|---|---|
| reference_s1 | 7 | 1 | 0 | 0 | 3 | 98 | 77% | 97 |
| reference_s2 | 3 | 0 | 0 | 0 | 1 | 117 | 80% | 111 |
| wide_s1 | 12 | 1 | 1 | 0 | 10 | 150 | 80% | 103 |
| wide_s2 | 3 | 1 | 0 | 0 | 4 | 122 | 80% | 108 |

Raw comparison: [results/stage1_forgetting/comparison.md](results/stage1_forgetting/comparison.md).

## Clips

- Success: [results/gifs/success/start192_side_by_side.gif](results/gifs/success/start192_side_by_side.gif)
- Failure: [results/gifs/failure/start101_side_by_side.gif](results/gifs/failure/start101_side_by_side.gif)
