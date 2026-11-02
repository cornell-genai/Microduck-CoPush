# Week 1 deliverable: what we built, tested and found

**Author:** Ashwin Aggarwal · **Week:** Oct 30 – Nov 5, 2026 · **Written:** Nov 2, 2026
**Tested against:** `microduck` main @ `997808c`, `microduck_rl` develop @ `bae39f5` (`upstream.lock`),
macOS / Apple Silicon, MuJoCo 3.10.0.

## Summary

- **Checkpoint M1 passed.** Two MicroDucks in one MuJoCo world are controlled independently and stay
  healthy. The automated check passed 4 of 4 fresh launches, and a manual run of the demo met every
  criterion in its CSV.
- **The project's infrastructure exists:**
  - the shared state/controller interface
  - a client that drives both ducks through the real `robotd`
  - a 10 Hz runner with CSV logging, metrics, plots and tests
  - a box scene whose pose we can read
  - one-command setup
- **The single-duck baseline (B0) is measured:**
  - Shoe Push forward pushes the box 0.65 m in 10 s; velstand manages 0.09–0.13 m.
  - A heading-hold controller keeps one duck's push straight over 1 m in 6/10 trials on the default
    robot and 10/10 without backlash.
- **The main risk for Week 2:**
  - Under the real controller (`robotd`), only velstand behaves. It barely pushes (about 0.1 m), and
    M2 needs 0.15 m.
  - Shoe Push forward pushes well in the policy harness but misbehaves under `robotd`.
  - Fixing that, or deciding to run the policies outside `robotd`, is the first decision of Week 2.

## 1. What we built

| Piece | What it does | Where |
|---|---|---|
| Setup | Clones and pins both Pollen repos, `uv sync`, builds the daemons, installs our scenes. Safe to rerun, and never touches local changes upstream | `scripts/setup.sh`, `upstream.lock` |
| Sim wrapper | One entry point over Pollen's `duck-sim`: 2 ducks, headless by default, `--viewer`, `--box` | `scripts/sim.sh` |
| Shared interface | The plan's `state` dict and `Controller.get_actions(state)` | `copush/state.py` |
| Two-duck client | `robot.move` to each duck's `robotd` at 10 Hz; ground-truth pose, trunk height and gravity from each body port; a clear error naming any duck that isn't running | `copush/sim_client.py` |
| Box pose and spawn placement | Runtime add-on to Pollen's body server, with no upstream edits: an `objects` read (box pose) and `COPUSH_PLACE` (spawn poses) | `copush/_bodyext/sitecustomize.py` |
| Runner and recorder | 10 Hz control loop, a CSV row per duck per tick, a JSON summary with the real-time factor | `copush/runner.py`, `copush/recorder.py` |
| Coordinator v0 | Fixed-command phases (A walks, B turns, stop) | `copush/controllers.py`, `scripts/two_duck_demo.py` |
| M1 check | Headless launch → health → demo → PASS/FAIL table, repeatable | `scripts/check_m1.py` |
| Box scene | Backlash floor scene plus a 28 × 10 × 9 cm, 150 g free-joint box | `scenes/scene_box.xml` |
| Metrics | Displacement, unwrapped yaw change, falls, box-to-goal position and yaw error, object progress | `copush/metrics.py` |
| Plots | x-y paths, yaw over time, trunk height over time, phases shaded | `scripts/plot_run.py` |
| Tests | 22 tests on mock data, no simulator needed | `tests/`, `data/sample/mock_run.csv` |
| B0 harness *(parallel workstream)* | Single-duck Shoe Push eval, steering sweep, heading-hold controller | `scripts/b0/`, `HeadingHoldPush`, `docs/results/` |

## 2. What we tested

### M1: two ducks, independent control, both healthy

Demo: A walks at vx 0.3 m/s for 8 s while B stands. Then B turns (vyaw 1.2 rad/s commanded) for 8 s
while A stands. Then both stop for 4 s.

| Criterion | Rule | Result across 3 fresh launches + manual run |
|---|---|---|
| `ctl health`, both ducks, before and after | healthy | healthy, 49.4–50.2 Hz control loop |
| Upright every tick | trunk ≥ 0.095 m and gravity_z ≤ −0.90 | lowest trunk 0.113 m, gravity_z at most −0.997 |
| A walks / B stays put (phase 1) | ≥ 50 cm / < 3 cm and < 8° | A 102–106 cm; B 0.2–0.3 cm, 0.1–1.5° |
| B turns / A stays put (phase 2) | ≥ 90° / < 3 cm and < 8° after a 1 s settle | B 247–271°; A 0.2–0.3 cm, 2–5° |
| Real-time factor | 0.95–1.05 | 1.00x headless, 1.00–1.01x with the viewer |

A control run (B idle in phase 2 too) gave the same small motion for A after it stops. So A's
post-walk settling is its own stopping turn, not B affecting it.

### Box scene

The box settles at z = 0.0449 m (half-height 0.045) and stays at (0.60, 0.00) with yaw 90°. Both ducks
stand. The box pose is logged as `box_x, box_y, box_z, box_yaw`.

### Week 2 feasibility checks

| Question | Answer |
|---|---|
| Can the ducks spawn closer than 0.5 m? | Not with any upstream setting. With our `COPUSH_PLACE`, both ducks stand at 0.25 m and 0.20 m apart, and 0.20 m is what two ducks sharing a 28 cm face need. |
| Can one duck run a different policy? | Yes, live: `DUCK_SIM_DUCK=duck-b scripts/sim.sh ctl policy load walk <onnx>`. Duck A keeps velstand. |
| Does the viewer break real time? | No, for 2 ducks on this Mac: 1.00x either way. |

### B0: one duck pushing (parallel workstream)

Full report: `docs/results/b0_single_duck_push.md`. It uses the policy harness (MuJoCo + BAM actuators,
not `robotd`), with 10 paired trials of 10 s each.

| Test | Backlash robot (duck-sim default) | No-backlash robot |
|---|---|---|
| Shoe Push forward, box travel | **0.65 ± 0.10 m**, 0 falls, 91% of contact on the hips | 0.69 ± 0.11 m |
| velstand, box travel | 0.09–0.13 m (stalls, pushes with its feet) | 0.13–0.14 m |
| Shoe Push backward | **fails**: turns around, −0.13 m | works: 0.57 m |
| Steering while pushing | gain ≈ 0.15, left bias +0.1 rad/s, range −0.13…+0.32 rad/s | similar |
| Heading hold, 1 m straight within 10 cm | **6/10** (open loop 0/10) | **10/10** (open loop 0/10) |

## 3. What we found

### How the ducks actually move

1. **Turning in place has a dead zone.**
   - velstand barely turns below ~0.95 rad/s commanded: 0.6 gives 3–5° in 6 s.
   - Commanding 1.2 gives about 0.6 rad/s.
   - `robotd` does no clamping, so this comes from the policy itself.
2. **Walking is slower than commanded and curves.**
   - vx 0.3 gives about 0.13 m/s, and the duck drifts 15–29° per 8 s.
   - Under `robotd`, velstand starts walking forward from rest at 0.15 m/s and backward only at −0.3.
3. **Shoe Push steering is weak and biased.**
   - Each rad/s commanded adds only about 0.15 rad/s of turning, and the duck always drifts left at
     zero command.
   - A proportional-only controller will settle with a steady error, so the controller needs an
     integral term.
   - Big turns rotate the box instead of pushing it.

### The two ducks are not identical

4. **Duck B is a different robot model.** Duck A comes from the scene (`robot_groundcontact_backlash`),
   and duck B is attached from `robot_allcollisions`.

   | | Duck A | Duck B |
   |---|---|---|
   | Parts that collide with the box | 10 (feet, legs, hip brackets, rear trunk, jaw) | 69 (essentially the whole body) |
   | Front trunk | passes through the box | collides with the box |
   | Joint backlash | yes | no |

   - They will push the box with different body parts.
   - Duck A matches what Shoe Push was trained on; duck B does not.
5. **Open discrepancy.** The B0 harness says velstand needs the backlash robot to walk. Yet in duck-sim,
   duck B (no backlash) walked 70 cm in 6 s at vx 0.3. The likely difference is `robotd`'s position
   actuators vs the harness's BAM actuators, or B's all-collision model. This is not yet explained.

### Start pose and scene

6. **The start keyframe sets the initial heading.**
   - Starting from `SIT` (the M1 default), ducks finish standing up within ±7° of yaw 0.
   - Starting from `HOME`, which box scenes currently need because they have no keyframes, ducks end
     29–44° off, by a different amount each launch.
   - A `SIT` keyframe sized for the box scene (35 robot values + 7 box values) works: 2.6° / 9.3°.

### Shoe Push under the real controller

7. **Shoe Push forward misbehaves under `robotd`.** Loaded on duck B, it:
   - moved about 1.4 m before any command was sent
   - ran about 0.47 m/s at vx 0.15 (the harness gives 0.14–0.16)
   - spun 68° in 6 s at zero command

   Likely causes:
   - duck-sim sets `stand = "none"`, so the walk network also runs at zero command, which Shoe Push
     never trained on.
   - The command/observation encoding may differ between `robotd` and the harness.
   - The actuators differ (position vs BAM).
8. **Shoe Push has two more hazards on the backlash robot.**
   - It falls in free walking without a box in front of it.
   - The backward policy ignores the sign of the command.

### Tooling problems in Pollen's code

9. **`duck-sim drive` ignores `DUCK_SIM_DUCK`.** `DUCK_SIM_DUCK=duck-b duck-sim drive` moves **duck A**
   and reports duck A's pose. Use our client instead.
10. **`ctl policy reset` breaks a simulated duck.**
    - It falls back to a robot path (`/opt/robot/...`) that doesn't exist on a laptop, and the duck goes
      `degraded`.
    - To recover, run `scripts/sim.sh up`. That relaunch also discards any `policy load`, so re-apply it
      after every launch.
11. **The body server only reports each duck's own sensors.** Reading the box needed our runtime add-on.
    The clean fix is about 15 lines upstream.

### Things we corrected along the way

- "velstand never walks backward" was withdrawn. It came from running on the no-backlash robot.
  velstand v8 on the backlash robot walks backward at −0.3 m/s, both in the harness and under `robotd`.
- "Turn at 0.6 rad/s" doesn't turn at all. The demo commands 1.2 rad/s to get about 0.6 rad/s.

## 4. What this means for Week 2

The Week 2 goals are M2 (one duck moves the box ≥ 0.15 m) and M3 (two ducks push it ≥ 0.30 m together).

**Decision needed first: which locomotion path do two-duck pushing experiments use?**

- **Option A: stay on `robotd` (duck-sim).** This is the real controller with real health and safety.
  It needs Shoe Push forward fixed under `robotd` (finding 7) before it can push. velstand alone reaches
  only about 0.1 m, which falls short of M2.
- **Option B: run both policies in our own two-duck MuJoCo loop.** This would extend the `scripts/b0`
  harness to two ducks. Shoe Push forward already pushes 0.65 m there, and runs are deterministic and
  faster than real time, which suits RL later. The cost is losing `robotd` fidelity.

*Recommendation:* spend at most a day on Option A's diagnosis. Start with `stand = "none"`: give Shoe
Push a standing network for zero commands. If that doesn't fix it, build the two-duck version of the
harness for M2/M3. Keep `robotd` for the demo and as a final check.

**Concrete next steps**

1. **Make the ducks identical,** or record which is which: same robot file and backlash setting.
   Options:
   - our add-on swaps the attached robot file (untested)
   - in Option B we control both models directly
2. **Add the `SIT` keyframe to `scene_box.xml`** so ducks start facing the box.
3. **Two-duck push layout:**
   - ducks 0.20 m apart (`COPUSH_PLACE`), box about 0.2 m ahead with its long face toward them
   - approach with velstand at ≥ 0.15 m/s, then switch to Shoe Push forward at contact
4. **Controller design (B1/B2):**
   - treat turning as a biased, low-gain, saturating actuator
   - use an integral term (as in `HeadingHoldPush`)
   - give velstand ≥ 0.15 m/s forward and a ≥ 1.0 rad/s turn-in-place dead zone
   - expect two ducks steering independently to twist the box: that is B1's first experiment
5. **Evaluation:**
   - box travel along the push line, box cross-track, falls, and box lost (> 40 cm from the trunk)
   - 5–10 repeatable trials per configuration (Week 2 Person 3 task)
   - record the robot model and policy versions in every run's JSON
6. **Upstream fixes to propose to Pollen** (small, low-risk):
   - `drive` honouring `DUCK_SIM_DUCK`
   - an `objects` read in the body server
   - a `--spacing` option
   - attaching extra ducks from the scene's own robot
   - `policy reset` working in simulation

## 5. Open questions

- Why does duck B (no backlash) walk under `robotd` when the harness says velstand needs backlash
  (finding 5)?
- Does Shoe Push forward behave under `robotd` once zero commands go to a standing policy?
- How much of the 2-duck push will be duck B's extra collision geometry vs coordination?
- Can two ducks at 0.20 m spacing walk side by side without stepping on each other? They stand at
  that spacing, but walking it is untested.

## 6. Reproduce

```sh
scripts/setup.sh                                  # once
uv run python scripts/check_m1.py --runs 3        # M1, headless
scripts/sim.sh up --viewer && uv run python scripts/two_duck_demo.py   # watch / record
uv run python scripts/plot_run.py --latest        # plot the last run
uv run pytest                                     # 22 tests, no simulator
```

**More detail:**
- `docs/WEEK1_STATUS.md`: M1 table per run, threshold rationale, all measurements
- `docs/results/b0_single_duck_push.md`: B0 report
- `docs/results/b0_runbook.md`: B0 runbook
- `docs/COPUSH_PLAN.md`: the plan
