# Larger evaluation: 200 new starts, five policies, no training

**Result (2026-11-15): the partner-heading effect does not hold.** On 200 starts the true-heading diagnostic (Run 1)
wins 64%, the two heading-removed runs 63% and 63%: a paired difference of **+0.5 points (95% interval -3.6 to +4.6)**.
All five policies, including D2 with exact info, are within 63 to 66%. The 72% against 60% on the 50-start test set was
mostly noise.

## The set

`experiments/test_sets/stage1_large.json`: 200 starts over stage 1's full box range, made once with its own seed
(20261115) by the same sampler as the 50-start sets (a Latin hypercube per axis: one start in each of 200 equal slices of
the +-45 degree box angle, and the same for the offsets, so the angle is spread evenly: 67 / 67 / 66 starts on the three
sides). It shares no start with the test set or the check set, and was never trained on or used for early stopping.
Config: [config.yaml](config.yaml); evaluation: [run.sh](run.sh); results: [results/comparison.md](results/comparison.md),
[results/ci_report.md](results/ci_report.md), per-episode data in [results/comparison.json](results/comparison.json).

## Success, 95% confidence intervals (Wilson), one episode per start

| policy | overall | < -15 deg (67) | -15 to +15 deg (67) | > +15 deg (66) |
|---|---|---|---|---|
| D2, exact partner info | **66%** (60 to 73) | 97% (90 to 99) | 87% (76 to 93) | 15% (8 to 26) |
| D1, own view only | **64%** (57 to 70) | 96% (88 to 98) | 87% (76 to 93) | 9% (4 to 18) |
| Part 2, seed 1 (chirps, heading removed) | **63%** (56 to 69) | 97% (90 to 99) | 81% (70 to 88) | 11% (5 to 20) |
| Run 2, seed 2 (chirps, heading removed) | **63%** (56 to 69) | 96% (88 to 98) | 87% (76 to 93) | 6% (2 to 15) |
| Run 1, true heading (DIAGNOSTIC) | **64%** (57 to 70) | 94% (86 to 98) | 87% (76 to 93) | 9% (4 to 18) |

## Behavior

| policy | idle share (mean, 95% interval) | overshoots | time-outs | falls | box lost |
|---|---|---|---|---|---|
| D2, exact | 15% (+-1) | 9% | 22% | 16 | 8 |
| D1 | 21% (+-2) | 12% | 30% | 8 | 3 |
| Part 2, seed 1 | 26% (+-2) | 14% | 32% | 8 | 2 |
| Run 2, seed 2 | 20% (+-2) | 14% | 30% | 11 | 2 |
| Run 1, true heading | **13%** (+-2) | 11% | 30% | 11 | 2 |

## Paired differences (same starts, percentage points)

| comparison | difference | 95% interval | McNemar p | measurable? |
|---|---|---|---|---|
| Run 1 minus Part 2 | +0.5 | -4.8 to +5.8 | 1.00 | no |
| Run 1 minus Run 2 | +0.5 | -3.8 to +4.8 | 1.00 | no |
| **Run 1 minus the mean of the two heading-removed runs** | **+0.5** | **-3.6 to +4.6** | | **no** |
| Part 2 minus Run 2 (seed to seed) | 0.0 | -5.0 to +5.0 | 1.00 | no |
| D2 exact minus Run 1 | +3.0 | -2.2 to +8.2 | 0.35 | no |
| D2 exact minus Part 2 (chirps, seed 1) | +3.5 | -1.8 to +8.8 | 0.27 | no |
| D2 exact minus Run 2 (chirps, seed 2) | +3.5 | -1.2 to +8.2 | 0.21 | no |
| Part 2 (chirps) minus D1 (no partner info) | -1.0 | -6.2 to +4.2 | 0.85 | no |
| Run 2 (chirps) minus D1 | -1.0 | -5.2 to +3.2 | 0.82 | no |
| D2 exact minus D1 | +2.5 | -2.2 to +7.2 | 0.41 | no |

## Read

- **Heading and success: no effect.** Run 1 is 0.5 points above the two heading-removed runs, with an interval of
  about +-4. A gap of 10 points, which the 50-start test set showed (72% against 60 to 62%), is ruled out. Per side
  it is the same: -2, +3 and +1 points, all inside +-6 to +12. The earlier reading, that the heading is the bottleneck
  (and the proposal to build it into the chirp), is **withdrawn**.
- **Heading and style: a real, small effect.** With the true heading the idle share is 13%, against 20 to 26% for the
  heading-removed runs (intervals of about +-2) and 15% for D2 with exact info. The heading changes how the ducks move
  (less standing still) without changing how often they win.
- **Seeds agree:** Part 2 seed 1 and seed 2 give the same 63%, so 63% is not a fluke of one seed.
- **Chirps cost nothing measurable on stage 1.** D2 with exact info 66%, chirps 63% (D2 minus chirps: +3.5 points,
  interval about -1.5 to +8.5 for either seed). A cost of up to about 8 points is not ruled out, and neither is none.
- **Partner info is not what limits stage 1.** D1, with no partner info at all, is at 64%; D2 exact is +2.5 points above
  it (interval -2 to +7). The 74% against 60% on the 50-start test set was the high end of the noise. Every policy
  wins 87 to 97% on the easy sides and only 4 to 15% on the long-turn side (box turned more than +15 degrees), and that
  side is what holds all of them at about 64%.

## What it means for earlier results

A rate on 50 starts has an interval of about +-13 points, so differences of 10 to 14 points between policies on the
50-start test sets (for example D2 74% against central 60%) are inside the noise; this larger set suggests the true gap
between D2 with exact info and D1 is a few points at most. Earlier headline comparisons that rest on one 50-start set
deserve a re-check on this set. These claims are in the main README and `experiments/decentralized-control/`; I have
not changed them.

## Proposed next steps (not decided)

1. Make this 200-start set (with intervals) the standard evaluation, and re-evaluate the key earlier policies on it (no
   training, minutes): the central stage 1 policy, stage 1b A and B, D2 and D1.
2. Stage 1 cannot show a difference from the ducks' sensing, since partner info barely matters here (D1 = D2). Test
   realistic sensing where it could matter: the ducks-start-apart setup (step 4 of the plan), with D1, D2 exact and chirps
   side by side, before spending runs on missed chirps and flips (step 2) or box mass (step 3).
3. The long-turn side is the real bottleneck for every policy; that is the steering track's problem, not sensing.
