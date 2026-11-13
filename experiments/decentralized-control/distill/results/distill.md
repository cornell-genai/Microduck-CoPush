# Distillation: centralized stage 1 policy -> per-duck policies

Teacher `runs/stage1-random-box-pose/model.zip` on 600 training episodes (random box starts, stage 1 range; 50% with action noise sd 0.15), 35341 sim steps = 70682 per-duck samples, then 1 DAgger round(s) of 300 episodes. Copy quality on 100 held-out episodes (5747 steps, teacher driving).

## How closely each copies the teacher (held-out episodes)

| variant | round | samples | R2 forward speed | R2 turn rate | mean abs error speed (m/s) | mean abs error turn (rad/s) |
|---|---|---|---|---|---|---|
| d1 | BC | 70682 | 0.901 | 0.938 | 0.020 | 0.158 |
| d1 | DAgger 1 | 105658 | 0.920 | 0.946 | 0.018 | 0.145 |
| d2 | BC | 70682 | 0.940 | 0.954 | 0.014 | 0.136 |
| d2 | DAgger 1 | 105026 | 0.951 | 0.963 | 0.011 | 0.115 |

R2 = 1 means a perfect copy, 0 means no better than always giving the average command. Speed is in [0, 0.3] m/s and turn rate in [-1.5, 1.5] rad/s.

## Success from copying alone (no PPO)

| policy | fixed start | test set | < -15 deg | -15 to +15 deg | > +15 deg | falls | push share A |
|---|---|---|---|---|---|---|---|
| stage1 (teacher) | success (33 steps) | 60% (30/50) | 15/17 | 13/16 | 2/17 | 3/50 | 46% |
| d1 BC only | success (32 steps) | 60% (30/50) | 15/17 | 14/16 | 1/17 | 2/50 | 47% |
| d1 after DAgger | success (32 steps) | 62% (31/50) | 16/17 | 14/16 | 1/17 | 0/50 | 49% |
| d2 BC only | success (32 steps) | 60% (30/50) | 15/17 | 14/16 | 1/17 | 2/50 | 46% |
| d2 after DAgger | success (33 steps) | 64% (32/50) | 17/17 | 14/16 | 1/17 | 3/50 | 47% |

Wall time 7.9 min.
