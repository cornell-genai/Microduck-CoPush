# Stage 1b: the turn-direction blind spot from stage 1

**Status:** diagnosis done (2026-11-12). The verdict is **UNCLEAR**, so per the plan I stopped
before training. No policy was trained in this stage.

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

My suggestion: run the oversampling fix (half of training starts above +15°) with the new 50-start check set and
checks every 50k steps. That's your call, so nothing was trained.

## Reproduce

```sh
scripts/rl.sh scripts/rl/diagnose_turn.py --config experiments/stage1-random-box-pose/config.yaml \
    --out experiments/stage1b-turn-direction-fix/results
```

It takes about 1 minute.
