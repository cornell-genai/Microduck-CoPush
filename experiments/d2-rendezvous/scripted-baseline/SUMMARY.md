# Scripted rendezvous baseline: ducks start apart, walk to their docking spots, then the L2-s2 push policy pushes

*Evaluation only, no training. 200 held-out starts, one deterministic episode each. Numbers from [results.json](results.json)
and [results.md](results.md) (full per-kind tables).*

## Question

The push policy (night 5 `l2-s2`, `runs/d2-steering-night5/l2-s2/model.zip`, sha256 `ab82e344...`) only works from the
spots it was trained on: a 3 cm shift costs it 11 to 22 points (docking sweep, branch `docking-sweep`). Can a simple
script bring two ducks from anywhere near the box to those spots precisely enough, and fast enough, for the push to
work? This is the reference a learned rendezvous coordinator (r1-delta-reward, `scripts/rl/run_r1_delta_reward.py`) has to beat.

## Setup

- **Starts:** [rendezvous_large.json](../../test_sets/rendezvous_large.json), 200 starts on stage1_large's 200 box poses
  (same Latin hypercube poses as the other eval sets), duck poses drawn with seed 20261122: each duck 0.2 to 0.8 m from
  the box centre, bearing and heading uniform over 360 degrees (160 starts); both ducks within 2 cm of the box's push
  axis, so both ways of pairing ducks with spots are about equally long (20 near-symmetric starts); both ducks on the
  target side of the box (20 wrong-side starts). Neither duck within 8 cm of the box, ducks at least 15 cm apart. In
  all, 150 starts have at least one duck on the target side and 58 have pairings within 5 cm of each other.
- **Docking spots:** the push policy's in-contact start poses, recomputed from the box's pose every step
  (`copush.env.docking_spots`, split out of `_place_in_contact`; the in-contact start is unchanged: 20 of 20 replayed
  night 5 episodes identical). Spot assignment once per episode: the shorter pairing; within 5 cm of a tie, duck A
  takes the spot farther from the target.
- **Scripted coordinator** (`copush.rendezvous.ScriptedRendezvous`), per duck: walk (0.3 m/s commanded, the action
  space's maximum) toward the line behind its spot, around the box via waypoints 15 cm off its corners when the straight
  line would cross it (8 cm clearance); rotate in place when more than 20 degrees off; then follow the line in, creeping
  at 0.12 m/s for the last 6 cm, and stop within 2 cm and 10 degrees or when the spot is reached. Both ducks stay on
  the walking policy (velstand) throughout; a duck yields to its partner when they are about to meet.
- **Pipeline:** hand off when both ducks are within 3 cm and 15 degrees of their spots and upright (checked every
  0.2 s step), or at 50 steps (10 s) regardless; then stand 0.3 s, switch to Shoe Push, and run the push policy for 100
  steps. Push success = box centre in the target, yaw within 15 degrees, both ducks up, held 1 s.

## Results (200 starts, 95% intervals)

| starts | n | docked within 50 steps | end-to-end push success | push success when docked | push success without docking |
|---|---|---|---|---|---|
| all | 200 | 48.0% (41.2 to 54.9) | **65.0% (58.2 to 71.3)** | 91 of 96 (95%) | 39 of 104 (38%) |
| uniform | 160 | 55.0% (47.3 to 62.5) | 70.0% (62.5 to 76.6) | 83 of 88 | 29 of 72 |
| near-symmetric | 20 | 30.0% (14.5 to 51.9) | 45.0% (25.8 to 65.8) | 6 of 6 | 3 of 14 |
| wrong-side | 20 | 10.0% (2.8 to 30.1) | 45.0% (25.8 to 65.8) | 2 of 2 | 7 of 18 |
| a duck on the target side | 150 | 32.7% (25.7 to 40.5) | 55.3% (47.3 to 63.1) | 46 of 49 | 37 of 101 |

- **Precision is good enough.** Docked ducks end 1.8 cm and 5.7 degrees from their spots on average, and the push then
  succeeds 95% of the time (91 of 96). That matches the push policy on its own trained starts (88 to 98% across the
  night 5 sets), so docking by script costs the push almost nothing.
- **Time is the bottleneck.** Docking takes 38.5 steps on average (18 to 49) when it happens. velstand covers only about
  2.5 cm per 0.2 s step at the maximum command, so a duck 0.8 m away needs more than 30 steps of straight walking.
  Ducks that must walk around the box rarely make it in 50 steps (wrong-side: 2 of 20). The ducks that did not dock
  were a median 12 cm from their spot at the handoff.
- **Contacts.** 494 duck-box contacts in 120 episodes and 150 duck-duck contacts in 21 episodes, counted once per 0.2 s
  step. Many are brushes, not crashes: 70 of the 96 docked episodes have one (often the feet touching the box face while
  docking), and 68 of those 70 still pushed successfully. Duck-duck contacts are mostly in the episodes that did not
  dock (118 of 150), where the two ducks are still sorting out who goes first.
- Falls: 1 during the rendezvous, 5 during the push. Push endings over all 200: 130 successes, 63 time-outs, 5 falls,
  2 boxes tipped.

## What it means

A script gets the ducks to the spots precisely; it is just slow, and slowest exactly where the ducks must walk around
the box or untangle a near-symmetric start. The learned rendezvous coordinator (r1-delta-reward) has the same action space and
walking policy, so it cannot walk faster; it can only win by choosing better routes (fewer in-place turns, no
stop-and-go at the box corners, less yielding). The 50-step handoff budget is also a choice: 104 of the 200 starts hand
off undocked, and those succeed only 38% of the time, so a longer budget would raise the baseline too.

Reproduce: `scripts/rl.sh scripts/rl/rendezvous_eval.py eval --rendezvous scripted --out experiments/d2-rendezvous/scripted-baseline`
(about 1 minute on 8 workers).
