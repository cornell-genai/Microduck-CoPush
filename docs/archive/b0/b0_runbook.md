# B0 runbook: Shoe Push policies in MuJoCo

How to run and watch the single-duck Shoe Push baseline. Results are in
[b0_single_duck_push.md](b0_single_duck_push.md).

## What they are

`pisdeburra/robert-policies` holds two PPO policies, warm-started from Pollen's velstand (Hub v5/v6), that
push a 28 × 10 × 9 cm box (50–300 g) with the body:
- **forward** walks into a box 20 cm ahead and pushes it with the hip brackets;
- **backward** backs into a box 20 cm behind and pushes it with the trunk (battery).

They keep the standard 61D obs → 14D action, 50 Hz contract, so they run unchanged in
`microduck_rl/scripts/infer_policy.py --new-cmd-obs`. The actor never sees the box.

## Setup (once)

This repo, `microduck_rl` (`develop`, `uv sync` done) and `microduck` sit side by side, as
`scripts/sim.sh` expects. Override the path with `DUCK_SIM_RL=...`.

```bash
sh scripts/install_scene.sh     # scene_copush_b0_{forward,backward}[_nobacklash].xml into microduck_rl (untracked)
sh scripts/fetch_policies.sh    # data/policies/{robert,velstand_v6,velstand_v8} (gitignored)
```

**Which robot.** `scene_copush_b0_<dir>.xml` uses `robot_groundcontact_backlash.xml`: duck-sim's robot, and
the one velstand was trained on. The `_nobacklash` twin uses `robot_groundcontact.xml`.
- Shoe Push **backward** works only without backlash.
- Shoe Push **forward** works on both, but falls in free walking (no box) with backlash.
- velstand needs backlash to walk.

## Watch it (viewer)

On macOS the viewer needs **`mjpython`**; plain `python` refuses `launch_passive`. Run from `microduck_rl`,
and type keys **in the terminal**, not the viewer window.

```bash
cd ../microduck_rl
P=../Microduck-CoPush/data/policies
S=src/mjlab_microduck/robot/microduck

# forward push (box ahead, +0.2 m/s), backlash robot
uv run mjpython scripts/infer_policy.py --new-cmd-obs --walking $P/robert/shoe_push/forward/policy.onnx \
    --scene $S/scene_copush_b0_forward.xml --lin-vel-x 0.2
# backward push (box behind, -0.2 m/s): use the no-backlash robot
uv run mjpython scripts/infer_policy.py --new-cmd-obs --walking $P/robert/shoe_push/backward/policy.onnx \
    --scene $S/scene_copush_b0_backward_nobacklash.xml --lin-vel-x -0.2
# baseline: velstand v6 (warm-start source), or velstand_v8 for today's set
uv run mjpython scripts/infer_policy.py --new-cmd-obs --walking $P/velstand_v6/velstand.onnx \
    --scene $S/scene_copush_b0_forward.xml --lin-vel-x 0.2
```

Keep the default BAM actuator; don't add `--no-bam`. velstand often won't start from standstill at ±0.2
m/s. Press UP or DOWN (±0.3) to see it walk into the box.

### Keys (terminal)

| key | effect |
|---|---|
| UP / DOWN | lin_vel_x = **+0.3 / −0.3** (jumps to the limit) |
| LEFT / RIGHT | lin_vel_y = +0.2 / −0.2 |
| A / E | ang_vel_z = **+1.5 / −1.5 rad/s**, keeps vx |
| SPACE | zero all commands |
| P | random 1 m/s push · T pause policy · Q quit |
| H / B | head mode / body-pose mode |

### What to watch for

- **Contact:** forward pushes with the hip brackets; backward (no backlash) with the trunk.
- **Drift:** heading drifts with a fixed sign. Forward curves left at about +40–50° per 10 s. Backward
  without backlash curves right at about −80°; with backlash it turns all the way around.
- **Steering:** correcting by keyboard is coarse. While pushing, the duck turns at only about 0.15 × the
  commanded rate, so even E (−1.5) gives about −0.13 rad/s. Tap A or E, then SPACE, then UP to resume.
  For a straight push, use the heading hold below.

## Headless scripts (repo root)

```bash
b0() { uv run --project ../microduck_rl python "$@"; }   # works in zsh and bash
b0 scripts/b0/eval_push.py [--robot backlash|nobacklash] [--quick] [--json out.json]   # B0 table
b0 scripts/b0/steering.py  [--robot ...] [--wz -0.5 0 0.5]          # yaw response while pushing
b0 scripts/b0/heading_hold.py [--robot ...]                          # 1 m straight push, PI heading hold
b0 scripts/b0/make_plots.py                                          # docs/archive/b0/figures/
python3 scripts/b0/duck_sim_drive.py --state <DUCK_SIM_STATE> --port <port> -- vx vyaw [...]   # signed duck-sim drive
```

These share `scripts/b0/b0lib.py`, which imports infer_policy's obs builder and BAM actuator, so headless
runs and the viewer match. That is **not** the robotd path duck-sim uses; check anything that matters
there with `duck_sim_drive.py`. The heading controller is `copush.controllers.HeadingHoldPush`, on the same
`get_actions(state)` interface as the two-duck controllers.

## Caveats (model card + ours)

- No heading hold is built in: ±30–50° per 10 s on the card; fixed-sign and larger here.
- The front trunk and thigh servos have no collision geometry in this model (in `robot_groundcontact.xml`
  the front trunk piece is `self_collision_only`), so real forward contacts will differ.
- Backward trained with a bug (20% of its commands became "walk forward"). It also ignores the command
  sign: it walks backward even for +0.2.
- Head-pose commands were trained up to ±80°: keep them small while pushing. It's a box, not a shoe, and
  sim only.
- The ONNX metadata's `joint_stiffness 1.0` / `joint_damping 0.0` are placeholders that infer_policy ignores.
