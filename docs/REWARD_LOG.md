# Reward shaping log

There is one entry per reward version. Each version is selected in
[configs/copush.yaml](../configs/copush.yaml) (`reward.version` picks an entry of `reward_versions`,
which is applied on top of the `reward` values) and implemented in `copush.rewards.TaskReward`.

- Results come from scripted baselines on the eval split. With a fixed start, only `random` varies
  between episodes.
- The video links point into `runs/`, which is git-ignored, so they only work on the machine that
  made the run.
- Rerun the baselines with `scripts/rl.sh scripts/rl/baselines.py`, and the older checks with
  `scripts/rl.sh scripts/rl/check_env.py`.

## v1 (2026-11-12)

**What:** For each 0.2 s step, the reward is the sum of:
- position: 10 × the drop in box-to-target distance
- yaw: 3 × the drop in yaw error (measured modulo 180°)
- time: −0.01

Other events:
- success (inside the target, yaw error ≤ 15° and both ducks up, for 1 s): +10, ends the episode
- fall: −10, ends the episode
- box tipped (> 30°) or lost (> 0.40 m from both ducks): −5, ends the episode

The v2 options exist but are off: continuous falls and the balance-gated cooperation bonus.

**Why:** This is the first RL reward. It rewards progress rather than closeness, so standing near
the target pays nothing.

**Results:** 20 episodes per controller, `hard` layout (walk 0.35 m to the box, target 0.85 m away),
run `rl-checks-20261112-001140`.

| controller | mean return | success | falls | box lost | push share A / B | flags (episodes) |
|---|---|---|---|---|---|---|
| stand | −1.00 | 0% | 0/20 | 0/20 | – | none |
| zero (vx 0.15) | −4.98 | 0% | 0/20 | 0/20 | 100 / 0% | contact_share 20 |
| random | −6.58 ± 3.34 | 0% | 5/20 | 5/20 | 54 / 46% | contact_share 15, fall 5, bad_part 3, reward_vs_dist 2 |
| push_forward | −6.61 | 0% | 0/20 | 0/20 | 61 / 39% | bad_part_duck_b 20, contact_share 20, reward_vs_dist 20 |

**Findings:**
- The scripted push did not beat random, and standing still beat every controller that moved.
  - The progress terms only count the final state, so `push_forward` gave back all its progress
    when it overshot: it got to 0.38 m, then ended 1.15 m away and turned about 50°.
- The scale table flagged two problems:
  - Losing the box (−3.0) scored better than an overshooting timeout (−7.1).
  - With continuous falls, a late fall cost only −2.2.
- A 0.02 s stumble counted as a fall: −10, even though the duck recovered.
- `reward_vs_dist` fired because the yaw term (+1.04) outweighed losing 8.4 cm of distance
  (−0.87).

**Videos:**
- [push_forward](../runs/rl-checks-20261112-001140/videos/step_0_baseline_push_forward.mp4)
- [random](../runs/rl-checks-20261112-001140/videos/step_0_baseline_random.mp4)
- [zero](../runs/rl-checks-20261112-001140/videos/step_0_baseline_zero.mp4)
- [index](../runs/rl-checks-20261112-001140/videos/index.md)

## v1.1 (2026-11-12)

**What changed from v1:**
- A fall counts only after a duck has been down for 0.2 s without a break.
- w_yaw 3 → 1.
- Box lost or tipped: −5 → −10, the same as a fall.
- Time penalty −0.01 → −0.03 per step.
- PPO entropy coefficient 0.01 (in `ppo:`, not part of the reward).

The default RL setup also changed, separately from the reward:
- Layout `close`: an `in_contact` start, with both ducks already against the box on Shoe Push, and
  the target 0.40 m straight ahead.
- A new `push_steer` baseline.

**Why:**
- To stop ending episodes on stumbles.
- To stop the yaw term from paying for moving the box away.
- To make losing the box as bad as falling.
- To make waiting cost more, so standing still is no longer the safe choice.

**Results:** 5 episodes per controller, `close` layout, run `rl-baselines-20261112-005350`.

| controller | mean return | success | falls | box lost | push share A / B | flags |
|---|---|---|---|---|---|---|
| stand | −3.00 | 0% | 0/5 | 0/5 | – | none |
| random | +12.89 ± 0.20 | 100% | 0/5 | 0/5 | 52 / 48% | none |
| push_forward | +13.03 | 100% | 0/5 | 0/5 | 50 / 50% | none |
| push_steer | +12.62 | 100% | 0/5 | 0/5 | 48 / 52% | none |
| PPO A | not run (gate failed) | | | | | |

- **Scale table** (start 0.40 m): success +12.7, fall early −10.3, fall late −10.3, box lost
  early −10.3, box lost late −9.5, timeout with half the distance covered −1.2, stand still −3.0,
  overshoot −5.7. **No flags**: no failure scores at or above success, and no failure beats
  continuing.
- **Gate failed:** `push_steer` beat `stand` but not `random`. With the target straight ahead, any
  forward motion succeeds, and the small differences come from `push_steer` stopping as soon as the
  box centre is inside (final 0.07 m vs 0.03–0.04 m).
- **Diagnostic, outside the gate:** I offset the target 0.15 m sideways.
  - Target to the right: every mover still succeeds, because the target's 0.40 m length already
    covers the offset.
  - Target to the left: `push_steer` failed (0/5). It stops once the centre is inside, but the yaw
    error was above 15°, and Shoe Push at a zero command keeps nudging the box until it drifts out.
- **Hard layout under v1.1:** stand −3.00, random −2.62 ± 8.78 (20% success), push_forward −6.87,
  push_steer −4.10.

**Videos** (all seed 10000):
- [stand](../runs/rl-baselines-20261112-005350/videos/step_0_baseline_stand_v11.mp4)
- [random](../runs/rl-baselines-20261112-005350/videos/step_0_baseline_random_v11.mp4)
- [push_forward](../runs/rl-baselines-20261112-005350/videos/step_0_baseline_push_forward_v11.mp4)
- [push_steer](../runs/rl-baselines-20261112-005350/videos/step_0_baseline_push_steer_v11.mp4)
- [index](../runs/rl-baselines-20261112-005350/videos/index.md)

## v1.2 (2026-11-12)

**What changed from v1.1** (one change): a contact penalty of −0.02 per step for each duck that has
been off the box for more than 0.3 s without a break. It doesn't apply while the box is inside the
target, and it's logged as its own term (`contact`).

**Why:** To discourage walking away from the box, or leaving one duck to do the pushing.

**Results:** 5 episodes per controller, `close` layout, the same run as v1.1.

| controller | mean return | success | falls | box lost | push share A / B | flags |
|---|---|---|---|---|---|---|
| stand | −6.96 (contact −3.96) | 0% | 0/5 | 0/5 | – | none |
| random | +12.89 ± 0.20 | 100% | 0/5 | 0/5 | 52 / 48% | none |
| push_forward | +13.03 | 100% | 0/5 | 0/5 | 50 / 50% | none |
| push_steer | +12.62 | 100% | 0/5 | 0/5 | 48 / 52% | none |
| PPO B | not run (gate failed) | | | | | |

- Only `stand` changes. A standing duck on Shoe Push at vx 0 drifts off the 5 mm gap and never
  touches the box, so it pays the penalty. The controllers that move stay on the box, so the
  penalty never applies to them.
- **Scale table:** standing still off the box drops from −3.0 to −7.0, and walking away before
  losing the box from −10.3 to −10.5. **No flags.**
- **Gate failed** for the same reason as v1.1.

**Videos** (seed 10000):
- [stand](../runs/rl-baselines-20261112-005350/videos/step_0_baseline_stand_v12.mp4)
- [random](../runs/rl-baselines-20261112-005350/videos/step_0_baseline_random_v12.mp4)
- [push_forward](../runs/rl-baselines-20261112-005350/videos/step_0_baseline_push_forward_v12.mp4)
- [push_steer](../runs/rl-baselines-20261112-005350/videos/step_0_baseline_push_steer_v12.mp4)
