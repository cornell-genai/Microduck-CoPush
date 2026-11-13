# Stage 1b diagnosis

## 1. Stage 1 test set by box angle sign (successes / starts)

| controller | < -15 deg | -15 to +15 deg | > +15 deg |
|---|---|---|---|
| stand | 0/17 | 0/16 | 0/17 |
| random | 0/17 | 6/16 | 0/17 |
| push_forward | 0/17 | 4/16 | 0/17 |
| push_steer | 8/17 | 1/16 | 0/17 |
| pivot_push | 5/17 | 7/16 | 4/17 |
| 01_reference | 10/17 | 14/16 | 1/17 |
| stage1 | 15/17 | 13/16 | 2/17 |

## 2. Turning test (10 trials each, 6 s, nominal pose +-1 cm / +-3 deg)

Box yaw rate, deg/s; > 0 is counter-clockwise (CCW), < 0 clockwise (CW). Duck A is on the left of the push direction.

| condition | mean | std | min | max | both ducks in contact | episode ends |
|---|---|---|---|---|---|---|
| full turn left | +8.69 | 1.85 | +4.71 | +11.53 | 70% | ok |
| full turn right | -4.84 | 1.03 | -6.84 | -2.83 | 88% | ok |
| duck A faster | -2.27 | 0.34 | -3.08 | -1.80 | 89% | ok, success |
| duck B faster | +1.81 | 0.76 | +0.80 | +3.21 | 89% | ok |
| pivot: A pushes, B held | -12.74 | 0.47 | -13.29 | -11.90 | 0% | ok |
| pivot: B pushes, A held | +13.88 | 0.47 | +13.17 | +14.85 | 0% | ok |

## 3. Rotation each side needs (mean over test starts, deg; > 0 CCW)

| side | starts | aim at target | end within tolerance |
|---|---|---|---|
| < -15 | 17 | +0.8 (-17 to +19) | +14.8 |
| -15 to +15 | 16 | -25.1 (-42 to -5) | +0.0 |
| > +15 | 17 | -55.1 (-77 to -37) | -14.6 |

## 4. What the stage 1 policy does (fastest 2 s box rotation, deg/s, mean over starts)

| side | starts | success | fastest CW | fastest CCW | net rotation (deg) |
|---|---|---|---|---|---|
| < -15 | 17 | 15/17 | 1.3 | 11.0 | +33.0 |
| -15 to +15 | 16 | 13/16 | 7.5 | 6.5 | -7.3 |
| > +15 | 17 | 2/17 | 12.9 | 8.3 | -37.8 |
