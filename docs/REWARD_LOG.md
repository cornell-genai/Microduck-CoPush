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

## v1.1, round 3: setup changes only (2026-11-12)

**What changed:** The reward is still v1.1. This round only changes the setup:
- **`push_steer` fix:**
  - The ducks stop only when the box is inside the target **and** its yaw error is within 15°.
  - When they stop, both ducks are held on velstand at zero speed, because Shoe Push keeps
    nudging the box at a zero command.
  - If the box is inside but crooked, only the duck on the side that has to advance pushes, so
    the box pivots.
  - If the box drifts out, the hold is released and the ducks go back on Shoe Push when they
    touch it.
  - The hold (`CoPushEnv.set_hold`) is available to scripted controllers only. The PPO action space
    can't request it.
- **New `steer` layout:** like `close`, but the target is 0.30 m to the right of the push line. That
  is beyond the target's own ±0.20 m and against Shoe Push's left drift, so a straight push misses.
- **New `scripts/rl/train.py`:** PPO.

**Why:**
- In round 2, `push_steer` failed on a left offset because it stopped with the box crooked.
- The `close` layout can't tell controllers apart, because any forward motion succeeds there.

**Results:** Baselines are from run `rl-baselines-20261112-011732`. Episodes use the eval seeds from
10000, and all videos use seed 10000.

`close`, 5 episodes:

| controller | mean return | success | falls | box lost | push share A / B |
|---|---|---|---|---|---|
| stand | −3.00 | 0% | 0/5 | 0/5 | – |
| random | +12.89 ± 0.20 | 100% | 0/5 | 0/5 | 52 / 48% |
| push_forward | +13.03 | 100% | 0/5 | 0/5 | 50 / 50% |
| push_steer | +12.60 | 100% | 0/5 | 0/5 | 48 / 52% |

`steer`, 10 episodes:

| controller | mean return | success | falls | box lost | push share A / B |
|---|---|---|---|---|---|
| stand | −3.00 | 0% | 0/10 | 0/10 | – |
| random | −15.93 ± 1.30 | 0% | 0/10 | 1/10 (tipped) | 52 / 48% |
| push_forward | −16.98 | 0% | 0/10 | 0/10 | 50 / 50% |
| push_steer | −15.10 | 0% | 0/10 | 0/10 | 58 / 42% |

**Gates:**
- `close` passes: `push_steer` +12.60 vs `stand` −3.00.
- `steer` fails: every controller has 0% success.
  - Shoe Push can't turn the box by 37° within 0.4 m of pushing. With both ducks saturated at
    +1.5 rad/s they turned about 5° in 2 s, and the box passed the target's x.
  - Four differential-speed variants (the outside duck pushes faster) also never succeeded; the
    closest got within 0.13 m.

**Other results:**
- **`push_steer` fix:** the left-offset case (target 0.15 m left) now succeeds (+11.66): it squares
  the box, holds on velstand, and the success timer completes.
- **Policy-switch wobble:** I checked the 1 s after every switch across the `close`, `steer` and
  `hard` baselines.
  - Shoe Push → velstand: 48 switches. velstand → Shoe Push: 27.
  - **No stumbles and no counted falls.** The worst tilt was 11.5° (stumble threshold 26°) and the
    lowest trunk height 0.103 m.
  - Switching needs no fix.

**Videos** (seed 10000), in `runs/rl-baselines-20261112-011732/videos/`:
- `close`:
  [stand](../runs/rl-baselines-20261112-011732/videos/step_0_baseline_close_stand.mp4) ·
  [random](../runs/rl-baselines-20261112-011732/videos/step_0_baseline_close_random.mp4) ·
  [push_forward](../runs/rl-baselines-20261112-011732/videos/step_0_baseline_close_push_forward.mp4) ·
  [push_steer](../runs/rl-baselines-20261112-011732/videos/step_0_baseline_close_push_steer.mp4)
  (this one shows the switch to velstand at the end)
- `steer`:
  [stand](../runs/rl-baselines-20261112-011732/videos/step_0_baseline_steer_stand.mp4) ·
  [random](../runs/rl-baselines-20261112-011732/videos/step_0_baseline_steer_random.mp4) ·
  [push_forward](../runs/rl-baselines-20261112-011732/videos/step_0_baseline_steer_push_forward.mp4) ·
  [push_steer](../runs/rl-baselines-20261112-011732/videos/step_0_baseline_steer_push_steer.mp4)
- [index](../runs/rl-baselines-20261112-011732/videos/index.md)

**PPO:**
- Run A (`close`, 100k steps, pipeline test), run `ppo-A-close-20261112-012145`, 6.3 min:
  - **Final policy** (5 deterministic episodes, seeds from 10000): mean return **+13.14**, success
    100%, falls 0/5, box lost 0/5, push share 52 / 48%. It beats `push_forward` (+13.03),
    `random` (+12.89) and `push_steer` (+12.60), but only by 0.1–0.5.
  - **It's faster, not smarter.** The mean commanded vx is 0.265 / 0.221 m/s, against 0.2 for the
    scripts. Training episode length fell from 25.5 to 20.7 steps, and `rollout/ep_rew_mean` rose
    from 11.3 to about 13.0.
  - **Deterministic eval curve:** flat from the first eval (+13.06 at 10k, +13.00 to +13.29
    after). The task is already solved by any forward push, so that's a ceiling, not a training
    failure.
  - **No reward gaming:** it didn't stand still or lose the box, and it raised no monitor flags.
  - Videos:
    [step_10000_baseline](../runs/ppo-A-close-20261112-012145/videos/step_10000_baseline.mp4) ·
    [step_100352_final](../runs/ppo-A-close-20261112-012145/videos/step_100352_final.mp4). No
    "improved" or "new_behavior" video was triggered, which fits a flat curve.
  - TensorBoard logs: `runs/ppo-A-close-20261112-012145/tb/`.
- Run B (`steer`, 300k): not run, because the steer gate failed.

## v1.1 / v1.2, overnight round: 7 PPO runs (2026-11-12)

**What:** A queue of seven 400k-step PPO runs (`configs/overnight.yaml`, results in
`runs/overnight-20261112/`). Reference: reward v1.1, seed 1, layout `overnight` (in-contact start,
target 0.60 m ahead and 0.30 m to the right, chosen from the reachability sweep), trained on the
fixed start. Each other run changes one thing: stand-still action, contact penalty (v1.2),
cooperation bonus (`gated_balanced`, λ 5), a 4-level curriculum, seed 2, seed 3.

**Why:** To see whether any of the four changes helps once the task needs steering, measured
against the spread of three seeds of the reference.

**Results:** All 7 finished (401,408 steps, 26–36 min each); no crashes, early stops or time caps.
"Fixed" is the final deterministic episode with the fixed start; "randomized" is the final policy on
5 episodes with the box randomized (eval seeds 10000–10004). Task-only = return minus the `coop` and
`contact` terms, so runs with different rewards can be compared.

| run | fixed, task-only | randomized success | randomized task-only mean | push share A / B | every eval a success from |
|---|---|---|---|---|---|
| 01 reference (seed 1) | +15.59 | 4/5 | +10.50 | 51 / 49% | 210k |
| 06 seed 2 | +15.09 | 3/5 | +5.97 | 53 / 47% | 290k |
| 07 seed 3 | +15.23 | 4/5 | +10.17 | 49 / 51% | 310k |
| 02 stand-still | +15.26 | 4/5 | +11.60 | **100 / 0%** | 240k |
| 03 contact penalty | +15.23 (raw +15.23) | 4/5 | +9.61 | 51 / 49% | 180k |
| 04 coop bonus | +15.58 (raw +18.02) | 4/5 | +10.57 (raw +12.79) | 52 / 48% | 120k |
| 05 curriculum | +15.51 | 4/5 | +10.20 | 50 / 50% | 100k |
| `pivot_push` (script) | +12.83 | 4/5 | +9.23 | 97 / 3% (fixed start) | – |

- **Seed range (the "luck" range):** fixed +15.09 to +15.59, randomized success 3/5 to 4/5,
  randomized mean +5.97 to +10.50, all-success from 210k to 310k steps.
- **No change is outside the seed range on the final numbers.** All four changes land at
  +15.2–15.6 fixed and 4/5 randomized. The coop bonus's +18.02 is +2.44 of bonus on top of the same
  task return.
- **Coop bonus and curriculum stabilized sooner** (every eval a success from 120k and 100k, against
  210–310k for the seeds). This is one seed each, so it's a hint, not a result. The curriculum
  reached its last level at 40k (levels 0–2 passed on the first try), so most of its run was
  ordinary training on the final layout.
- **Stand-still turned the task into a solo push.** Duck B never touched the box in the final
  policy (contact time 0, `contact_share` in 5/5 randomized episodes and in 22 of the evals from 200k
  on). The return is unchanged, because nothing in v1.1 pays for two ducks.
- **The contact penalty did nothing visible.** Its term was −0.02 on average, and the ducks stay on
  the box anyway.
- **The coop bonus pays even when the policy fails.** It paid +1.0 to +2.0 on timeout episodes
  (+1.60 for the untrained policy at 10k), so it rewards balanced contact, not progress. The final
  policy didn't exploit it, but it's a possible exploit.
- **PPO vs the script:** PPO beats `pivot_push` on the fixed start (+15.1–15.6 vs +12.83; 32–40 steps
  vs 54) and splits the push about 50/50, where the script is a one-duck push.
  With the box randomized they tie: 4/5 each (seed 2 3/5), and the means are within noise.
- **Every run fails at least 1 of the 5 randomized episodes, by timing out.** The policies were
  trained on the fixed start only. With 5 episodes, one episode is 20 points of success rate, so
  this protocol can't separate the changes.
- No falls and no lost boxes in any final randomized eval. The monitor flags in SUMMARY.md are
  mostly from early training. After 200k only `contact_share` comes up often (stand-still 25,
  contact penalty 12, 0–3 for the others).

**Videos** (in `runs/overnight-20261112/runs/`):
- [02 stand-still final](../runs/overnight-20261112/runs/02_stand_still/videos/step_401408_final.mp4):
  duck A pushes alone, duck B never touches the box.
- [06 seed 2 final](../runs/overnight-20261112/runs/06_seed2/videos/step_401408_final.mp4):
  duck B barely moves (mean vx command 0.015 m/s) but has 55% of the contact, so it's a pivot point.
- [04 coop bonus final](../runs/overnight-20261112/runs/04_coop_bonus/videos/step_401408_final.mp4):
  the cleanest two-duck push (32 steps, 51 / 49%, 0.4° final yaw).
- [pivot_push baseline](../runs/overnight-20261112/baseline_videos/videos/step_0_baseline_overnight_pivot_push.mp4)
  for comparison · [SUMMARY.md](../runs/overnight-20261112/SUMMARY.md) ·
  [DECISIONS.md](../runs/overnight-20261112/DECISIONS.md)

**Next:** Train the reference with the box randomized (`env.randomize: true`) and evaluate on 20 or
more randomized episodes. The fixed-start eval is at its ceiling for every run, and the randomized
eval is where all of them fail.

## v1.3 (2026-11-12)

**What changed from v1.1** (one change): the time penalty goes from −0.03 back to −0.01 per step. That's
v1.1 with v1's time penalty. Everything else is unchanged.

**Why:** On long-turn starts (box turned more than +15°) the stage 1 policy turns about 40° and then pushes,
when aiming at the target needs about 55°. The question was whether −0.03 per step rushes it into pushing
early.

**Results:** stage 1b experiment B
([experiments/stage1b-turn-direction-fix/b-lower-time-penalty/](../experiments/stage1b-turn-direction-fix/b-lower-time-penalty/README.md)).
It warm-starts from the stage 1 policy and trains 1M steps, then is scored on stage 1's 50 fixed test starts.
Success is compared, not return, because the rewards differ.

| policy | reward | overall | < −15° | −15° to +15° | > +15° | turn before push (> +15°) | both ducks idle (> +15°) |
|---|---|---|---|---|---|---|---|
| stage 1 | v1.1 | 60% | 15/17 | 13/16 | 2/17 | 40° | 12% |
| experiment B | v1.3 | 68% | 17/17 | 16/16 | 1/17 | 37° | 34% |
| experiment A (for scale: v1.1, oversampled hard starts) | v1.1 | 72% | 16/17 | 16/16 | 4/17 | 44° | 15% |

- **It didn't help the long turn.** B turns slightly less before pushing, and wins 1 of 17 long-turn starts.
- The easy-side gain also shows up in experiment A, which kept v1.1, so it probably comes from the extra training,
  not from v1.3.
- **Standing still is partly back on hard starts.** Both ducks are idle for 34% of steps there, three times stage 1's
  rate, and the box drifts away. That's the behavior v1.1's higher time penalty was added to stop. No episode leaves the box
  where it started, and episodes aren't longer on average (54 against 57 steps).
- **Verdict:** don't adopt v1.3. v1.1 stays the default.

**Video:** `runs/stage1b-b-lower-time-penalty/videos/side_by_side/start44_stage1_vs_b_time_penalty.mp4`
(stage 1 left, B right). Both get within about 0.3 m of the target, then the box drifts off while the ducks wait.
