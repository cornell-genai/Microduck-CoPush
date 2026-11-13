# Stage 1b: the turn-direction blind spot from stage 1

**Status:** done (2026-11-12). The diagnosis came out **UNCLEAR**, so two experiments followed, each one
change from stage 1: [A, oversample the long-turn starts](a-oversample-hard/) and
[B, a lower time penalty](b-lower-time-penalty/). **Neither fixed the long-turn side** (stage 1: 2/17,
A: 4/17, B: 1/17). Both raised overall success (60% → 72% and 68%), mostly on the easy sides.

## The problem

On stage 1's 50-start test set, the stage 1 policy succeeds on 15 of 17 starts where the box is turned
more than 15° negative, and on 2 of 17 where it is turned more than 15° positive
([stage 1](../stage1-random-box-pose/README.md)). Angles are box yaw minus the nominal yaw, and positive is
counter-clockwise (CCW).

## Diagnosis (no training)

Script: [scripts/rl/diagnose_turn.py](../../scripts/rl/diagnose_turn.py). Full output:
[results/diagnosis.md](results/diagnosis.md) and [results/diagnosis.json](results/diagnosis.json).

### 1. Every controller, by box angle sign (stage 1 test set)

| controller | < −15° | −15° to +15° | > +15° |
|---|---|---|---|
| stand | 0/17 | 0/16 | 0/17 |
| random | 0/17 | 6/16 | 0/17 |
| push_forward | 0/17 | 4/16 | 0/17 |
| push_steer | 8/17 | 1/16 | 0/17 |
| pivot_push | 5/17 | 7/16 | 4/17 |
| 01_reference | 10/17 | 14/16 | 1/17 |
| stage1 | 15/17 | 13/16 | 2/17 |

The scripts are split. push_steer fails every positive start (8 against 0), but pivot_push, the only
script built to turn the box, is about even (5 against 4). push_forward and random only ever win near 0°.

### 2. Turning test

Both ducks start against the box on Shoe Push at the nominal pose, jittered by up to ±1 cm and ±3°
per trial. Each trial holds one command for 6 s, 10 trials per condition. The table gives the box yaw rate;
negative is clockwise (CW). Duck A is on the left of the push direction.

| condition | mean (deg/s) | spread (min to max) |
|---|---|---|
| full turn left (both ducks yaw +1.5 rad/s) | **+8.7** | +4.7 to +11.5 |
| full turn right (both ducks yaw −1.5 rad/s) | **−4.8** | −6.8 to −2.8 |
| duck A faster (0.3 against 0.1 m/s) | −2.3 | −3.1 to −1.8 |
| duck B faster (0.1 against 0.3 m/s) | +1.8 | +0.8 to +3.2 |
| *extra:* pivot, A pushes alone, B held on velstand | **−12.7** | −13.3 to −11.9 |
| *extra:* pivot, B pushes alone, A held on velstand | **+13.9** | +13.2 to +14.9 |

- With turn commands, CW is 1.8x slower than CCW.
- With differential speed, CW is a little faster (1.25x).
- With a pivot, the fastest way to turn and the one pivot_push uses, the two directions are within 1.09x
  of each other.

I added the two pivot rows to the four conditions you asked for. Without them the turn-command row
alone would have suggested a physical limit.

### 3. Which way the positive side has to turn

The target is 0.60 m ahead and 0.30 m to the right, so the bearing from the box to the target is about
−27°. A positive start points the push face away from the target, while a negative start already points
roughly at it.

| side | rotation to aim the push face at the target | rotation to end within the 15° tolerance |
|---|---|---|
| < −15° | +1° on average (−17 to +19) | +15° (CCW) |
| −15° to +15° | −25° (−42 to −5) | 0° |
| > +15° | **−55°** (−77 to −37), CW | −15° (CW) |

So the positive side needs about 55° of clockwise turning before pushing, and the negative side needs almost none.

### 4. What the stage 1 policy actually does

| side | success | fastest 2 s CW turn | fastest 2 s CCW turn | net rotation |
|---|---|---|---|---|
| < −15° | 15/17 | 1.3°/s | 11.0°/s | +33° |
| −15° to +15° | 13/16 | 7.5°/s | 6.5°/s | −7° |
| > +15° | 2/17 | **12.9°/s** | 8.3°/s | −38° |

On positive starts the policy does turn clockwise, at about the pivot rate (12.9°/s). It just doesn't turn
far enough (−38° net against the −55° needed to aim), and in 11 of stage 1's 20 failures the box ends farther away than it started.

## Verdict: UNCLEAR

- **Not PHYSICAL.** pivot_push is about even across the two sides (5 against 4), and the fastest physical
  rotation is about the same both ways (pivot: 12.7 against 13.9°/s). Only the turn-command channel is 1.8x
  weaker clockwise.
- **Not LEARNING in the sense of "only turns one way".** The policy turns clockwise on positive starts, at
  the same rate as the physical pivot.
- **What the numbers do show:** the two sides are different tasks. Because the target is off to the right,
  a positive start needs a long clockwise turn (about 55°, roughly 4 to 5 s of pivoting) and then a
  regroup before pushing. A negative start needs almost no turning. The policy, warm-started from one fixed start,
  turns part of the way and then pushes, so it pushes the box past the target at the wrong angle.

### What this means for the two planned fixes

- **Mirrored training** would mostly add target-on-the-left episodes. The mirror of a hard positive start is
  "turn 55° CCW toward a target on the left", which isn't a test task. It would teach the long-turn
  maneuver only indirectly.
- **Oversampling hard-side starts** targets the real gap: practice at the long-turn case. It fits better, even though
  the cause isn't physical.

My suggestion at the time was to run the oversampling fix (half of training starts above +15°) with the new 50-start
check set and checks every 50k steps. The results are below.

## Experiments A and B

Both warm-start from the stage 1 policy, train up to 1M steps on 8 envs, and are scored on stage 1's 50-start test set.
Training checks run every 50k steps on a separate fixed check set of 50 evenly spread starts
([../test_sets/stage1_checks.json](../test_sets/stage1_checks.json)). Training stops early only after 3 checks in a row
at 80% or more. Neither run stopped early. Each run's final check matched its test-set score (A 72% and 72%, B 68% and 68%),
which the 20-start checks in stage 1 did not. Full table: [results/comparison.md](results/comparison.md).

| policy | overall | < −15° | −15° to +15° | > +15° | turn before push, long-turn starts (55° needed) | falls | overshoot | both ducks idle, long-turn starts |
|---|---|---|---|---|---|---|---|---|
| stage1 | 60% | 15/17 | 13/16 | 2/17 | 40° | 3 | 14 | 12% |
| A: oversample hard | **72%** | 16/17 | 16/16 | **4/17** | 44° | 5 | 10 | 15% |
| B: time penalty 0.01 | 68% | 17/17 | 16/16 | 1/17 | 37° | 2 | 13 | 34% |

*Turn before push* is the rotation made before the box has moved 0.20 m toward the target. *Idle* means both
ducks are commanded below 0.05 m/s.

- **Neither made the easy side worse.** Both improved it, from 28/33 to 32/33 (A) and 33/33 (B).
- **The long-turn side barely moved.** A gains 2 starts (+16° and +21°), B loses 1, and from +30° to +45° all
  three are 0/9. A two-start difference out of 17, on one seed each, is within luck.
- **No control run.** A and B each got 1M more training steps than stage 1. The shared gain on the easy sides
  (13/16 → 16/16 for both) is probably just the extra training rather than either change. A run with stage 1 plus
  1M steps and no change would settle it.
- **Odd behavior:**
  - A falls more (5, all duck A, all on long-turn starts).
  - B partly brings back standing still on the long-turn side: 34% of its steps there have both ducks idle,
    and the box drifts away.
- **Which to keep: A**, cautiously. It has the best overall score, the only gain on the long-turn side, and the fewest
  timeouts and overshoots. The extra falls count against it. B's idling on hard starts is the reward-hacking
  pattern v1.1 was built to stop, so I'd drop v1.3.

**Next (not started):** the long turn still doesn't happen. The policy turns about 40 to 44° and then pushes. Options:
1. A control run, to separate extra training from the change.
2. Give the coordinator a way to hold one duck still (the `env.stand_still` action). Then it can pivot the way
   pivot_push does, which is the fastest physical turn. The overnight stand-still run turned into one duck pushing
   alone, so that would need watching.
3. Shape the reward on aim error before the push.

## Reproduce

```sh
nohup scripts/rl/overnight.sh --config configs/stage1b.yaml >> runs/stage1b-20261112/queue.log 2>&1 &   # A then B
scripts/rl.sh scripts/rl/compare_policies.py --config experiments/stage1-random-box-pose/config.yaml \
    --test-set experiments/test_sets/stage1.json --policy stage1=runs/stage1-random-box-pose/model.zip \
    --policy a_oversample=runs/stage1b-a-oversample-hard/model.zip \
    --policy b_time_penalty=runs/stage1b-b-lower-time-penalty/model.zip --out experiments/stage1b-turn-direction-fix/results
scripts/rl.sh scripts/rl/diagnose_turn.py --config experiments/stage1-random-box-pose/config.yaml \
    --out experiments/stage1b-turn-direction-fix/results
```

The diagnosis takes about 1 minute, and the comparison about 2.
