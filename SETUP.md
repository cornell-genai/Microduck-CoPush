# Setup and commands

- [Install](#install)
- [Get the trained policies](#get-the-trained-policies)
- [Run the two-duck simulator](#run-the-two-duck-simulator)
- [RL: checks, baselines and training](#rl-checks-baselines-and-training)
- [Tests](#tests)
- [Overnight queue](#overnight-queue)
- [Outputs and settings](#outputs-and-settings)
- [Troubleshooting](#troubleshooting)
- [Repo layout](#repo-layout)
- [The shared controller interface](#the-shared-controller-interface)
- [Week 1 path: duck-sim / robotd](#week-1-path-duck-sim--robotd)

Every command for running Microduck-CoPush lives here. Run them from the repo root unless a
section says otherwise. The plan is in [ROADMAP.md](ROADMAP.md); rules for AI agents are in
[AGENTS.md](AGENTS.md).

## Install

You need `git`, [`uv`](https://docs.astral.sh/uv/), and Rust (`cargo`, only for the Week 1 path).
Clone this repo next to Pollen's upstream repos (`scripts/setup.sh` clones them if they're
missing):

```
~/CS_Projects/GenAI/
├── Microduck-CoPush/   (this repo)
├── microduck/
└── microduck_rl/
```

```sh
cd Microduck-CoPush
scripts/setup.sh                 # clones/pins upstream repos, uv sync, builds daemons (safe to rerun)
sh scripts/fetch_policies.sh     # once: the ONNX walking/pushing policies
```

What `setup.sh` does:
- It clones both upstream repos and pins them to `upstream.lock`. It never overwrites local
  changes; set `COPUSH_NO_PIN=1` to skip pinning.
- It runs `uv sync` in microduck_rl and here.
- It builds the daemons.
- It installs our scene into microduck_rl as an untracked `scene_copush_box.xml`.

Check that the simulator's environment and policies are in place:

```sh
uv run --project ../microduck_rl python -c "import mujoco, onnxruntime, bam, yaml, mediapy"
ls data/policies/velstand_v8/velstand.onnx data/policies/robert/shoe_push/forward/policy.onnx
```

## Get the trained policies

To warm start from our trained controllers instead of training them again:

```sh
scripts/get_policies.sh     # needs gh, logged in (gh auth login)
```

It downloads the [policies-v1 release](https://github.com/cornell-genai/Microduck-CoPush/releases/tag/policies-v1),
checks each file's SHA-256 and puts it where the experiment configs expect it:

| policy | goes to | what it is | test set |
|---|---|---|---|
| stage1-central | `runs/stage1-random-box-pose/model.zip` | central controller, stage 1 random box starts | 60% |
| stage1-d2 | `runs/decentral-p2-d2/model.zip` | D2 (each duck: own view plus partner), stage 1 random box starts | 74% |
| 01_reference | `runs/overnight-20261112/runs/01_reference/model.zip` | central controller, fixed in-contact start | 50% |

Each file's run, branch, commit, config, steps and checksum are in
[policies/manifest.json](policies/manifest.json). The script never replaces a file of yours that
differs from the release unless you add `--force`.

## Run the two-duck simulator

Two MicroDucks and a 28 × 10 × 9 cm box in one MuJoCo world: CPU MuJoCo, 200 Hz physics, 50 Hz ONNX
walking/pushing policies, BAM servo model. Headless it runs about 20× faster than real time.

```sh
scripts/copush.sh --viewer                                        # watch + drive both ducks from the terminal
scripts/copush.sh --headless --duration 15 --script push_forward  # scripted push -> runs/<timestamp>/
scripts/copush.sh --headless --duration 15 --script push_forward --record   # + video.mp4
scripts/copush.sh --duck-a 0,0.1,0 --box 0.4,0,90 --target 1.2,0,90 --box-mass 0.2   # custom start
```

`copush.sh` runs `scripts/copush_sim.py` in microduck_rl's environment and switches to `mjpython`
for `--viewer` on macOS.

### Keys

In `--viewer` mode, click the **terminal** and type there. The viewer window is only for watching;
letters typed into it trigger MuJoCo's own shortcuts.

| Key | Duck A | Duck B |
|---|---|---|
| forward / back (vx ± 0.05) | W / S | I / K |
| turn left / right (vyaw ± 0.3) | A / D | J / L |
| toggle policy velstand ↔ shoepush | 1 | 2 |
| stop this duck | X | M |

**Space** stops both ducks, **R** resets, **N** writes a note marker to events.log, **Q** quits. A
movement key during `--script` takes over manually. Every 0.5 s a status line shows box→target
distance, inside, each duck's policy, command and contact, and the reward.

### Flags

| Flag | Meaning |
|---|---|
| `--viewer` / `--headless` | window + keys, real time / no window, ~20× real time (default) |
| `--duration S` | sim seconds (headless default 15; viewer runs until Q) |
| `--script push_forward` | velstand vx 0.2 to the box, shoepush vx 0.2 from first contact |
| `--script push_hold` | same, then steer with `HeadingHoldPush` toward the target |
| `--record` | `video.mp4` with overlay (~0.8× real time headless; slows the viewer to ~0.4×) |
| `--duck-a X,Y,YAW` `--duck-b ...` `--box ...` `--target ...` | start poses (m, m, deg; negative numbers are fine) |
| `--box-mass KG` `--target-size L,W` | box mass, target rectangle |
| `--policy-a` / `--policy-b velstand\|shoepush` | policy at reset |
| `--config FILE` | another YAML (e.g. `runs/<ts>/config.yaml`) |
| `--reward progress` · `--quiet` | reward function · no headless status lines |

### Start positions

Edit [configs/copush.yaml](configs/copush.yaml) (metres; yaw in degrees; 0 = facing +x), or use the
flags above:

```yaml
duck_a: {x: 0.0, y: 0.10, yaw: 0, policy: velstand}
box:    {x: 0.35, y: 0.0, yaw: 90, mass: 0.15}     # yaw 90 = long face toward the ducks
target: {x: 1.20, y: 0.0, yaw: 90, size: [0.40, 0.20]}
```

Ducks spawn already standing in the policy's default pose at exactly the yaw you set; there is no
stand-up phase.

### Scripting in Python

```python
import sys; sys.path.insert(0, ".")          # run from the repo root
from copush.config import load_config
from copush.sim import CoPushSim

sim = CoPushSim(load_config(overrides={"box": {"x": 0.40}}))   # configs/copush.yaml + a change
state = sim.reset()
while state["t"] < 10.0:
    for duck in ("duck_a", "duck_b"):        # walk up on velstand, push with Shoe Push
        if state[duck]["policy"] == "velstand" and state["contact"][duck]["in_contact"]:
            sim.set_policy(duck, "shoepush")
    state = sim.step({"A": (0.2, 0.0, 0.0), "B": (0.2, 0.0, 0.0)})   # one 0.02 s step
print(f"box to target {state['box_to_target']:.2f} m, inside {state['inside']}, "
      f"fallen {state['fallen']}, A contact {state['contact']['duck_a']['total_by_part']}")
```

Run it with `uv run --project ../microduck_rl python my_push.py`. `get_state()` keys are documented
in `CoPushSim.get_state` ([copush/sim.py](copush/sim.py)). To try a different reward, write a
`(prev_state, state) -> float` function and add it to `REWARDS` in
[copush/rewards.py](copush/rewards.py).

### Command recipes (measured in this sim)

| To | Do | What happens |
|---|---|---|
| Approach the box | velstand, vx 0.2 | ~0.075 m/s; reaches a box 0.35 m ahead in ~3.4 s |
| Push | switch to shoepush (1 / 2) at contact, vx 0.2 | pushes with the hips (90–95% of contact) |
| Steer while pushing | vyaw −1.5 … +1.5 | drifts **left** at 0; over 7 s the box turned +21° (−1.5), +30° (0), +75° (+1.5): right turns are weak |
| Turn in place | velstand, vyaw ≥ 1.2 | 1.2 → 1.26 rad/s (here it already turns from ~0.5) |
| Back up | velstand, vx −0.3 | ~0.07 m/s backward; −0.2 does not move |
| Avoid | shoepush with no box ahead | fell in 5 of 6 tries, after 3–8.5 s |

### Record a trial and check for reward hacking

1. `scripts/copush.sh --headless --duration 15 --script push_forward --record` (or `--viewer` and
   drive, pressing **N** whenever something odd happens).
2. Open `runs/<ts>/video.mp4` and `runs/<ts>/notes.md`. The Outcome section is already filled in.
3. In `events.log`, read the `SUSPECT` lines:
   - `contact_share`: one duck does more than 80% of the pushing
   - `bad_part_*`: the duck pushes with its trunk or head more than its hips
   - `spin`: the box turns but doesn't move
   - `reward_vs_dist`: the reward rises but the box gets no closer
   - `fall_*`: a duck fell
   - `edge`: the box keeps crossing the target edge
4. In `state.csv`, plot `cum_reward` against `box_to_target` and `inside`. Gaming looks like reward
   going up while the distance does not go down.
5. Answer the three questions in notes.md: what the ducks did, whether that was expected, and
   whether the reward was gamed. Describe each NOTE marker.

## RL: checks, baselines and training

RL commands go through `scripts/rl.sh`. It's Python with gymnasium and stable-baselines3 added as a
uv overlay, so microduck_rl's own environment is left alone.

```sh
scripts/rl.sh scripts/rl/check_env.py                                      # older env / reward checks
scripts/rl.sh scripts/rl/baselines.py                                      # baselines + gates per layout (~2 min)
scripts/rl.sh scripts/rl/reachability.py                                   # scripted success over target positions
scripts/rl.sh scripts/rl/train.py --layout close --steps 100000 --name A   # PPO, ~6 min on a laptop
scripts/rl.sh scripts/rl/train.py --layout close --steps 20000 --stand-still   # with the stand-still action
scripts/rl.sh -m tensorboard.main --logdir runs                            # training curves
```

Baseline controllers are `stand`, `random`, `push_forward`, `push_steer`, and `pivot_push`, all in
`copush/env.py`.

### Who decides: the controller setting

By default one learned controller sees the whole scene and picks the commands for both ducks
(central). The decentralized mode gives each duck its own copy of the controller, run on its own
view, with its partner's position in view (D2). That's `controller` in `configs/copush.yaml`:

```yaml
controller:
  mode: central             # or decentral: each duck runs the shared controller on its own view
  include_partner: true     # decentral only; true is D2, false is D1 (own view only)
```

`train.py` takes `--controller central`, `d1` or `d2` to override it. A stage config sets it under
`overrides` (stages built on `configs/overnight.yaml` are central, like 01_reference). With a
decentral controller, PPO counts each duck as its own environment, so `--steps` counts duck steps,
2 per simulator step. Code: `copush/decentral.py`.

```sh
scripts/rl.sh scripts/rl/train.py --layout steer --steps 100000 --name C                  # default: central
scripts/rl.sh scripts/rl/train.py --layout steer --steps 100000 --name D2 --controller d2   # each duck its own copy
```

## Tests

```sh
scripts/rl.sh -m pytest
```

Use `scripts/rl.sh -m pytest`, not plain `uv run pytest`. The plain version skips the simulation
tests, because that environment has no MuJoCo, so it can look like everything passed when the sim
tests never ran.

## Overnight queue

A queue of PPO runs you can restart (`scripts/rl/overnight.py`, wrapped by `scripts/rl/overnight.sh`
with `caffeinate` so the Mac stays awake). The runs are listed in `configs/overnight.yaml`, and
`configs/overnight_test.yaml` is a 3-run dry run.

Run it from its own git worktree, so a branch switch in the main checkout can't break it overnight.

```sh
# launch (also resumes after a stop, crash or reboot)
nohup scripts/rl/overnight.sh --config configs/overnight.yaml >> runs/overnight-<date>/queue.log 2>&1 &

# check
tail -n 20 runs/overnight-<date>/queue.log                  # which run, crashes, finishes
tail -n 5 runs/overnight-<date>/runs/*/train.log            # evals and checkpoints per run
ps -p "$(cat runs/overnight-<date>/queue.pid)" -o pid,etime,command   # alive? (no queue.pid = finished)

# rewrite SUMMARY.md by hand (safe while the queue runs)
scripts/rl.sh scripts/rl/overnight.py --config configs/overnight.yaml --summary

# stop (allow about 15 s; progress since the last checkpoint of the current run is lost)
kill "$(cat runs/overnight-<date>/queue.pid)"
```

How it behaves:
- **Restart:** the same launch command skips finished runs and resumes the interrupted one from its
  last checkpoint. A run that crashed twice is skipped.
- **Single copy:** a second copy refuses to start while one is running.
- **Hard kill:** if the queue is killed hard (`kill -9`, power loss), the trainer stops by itself
  within a second.
- **Output:** each round writes `SUMMARY.md`, `DECISIONS.md` and `queue.log`. Each run writes
  `runs/<run>/` with its config, `train.log`, checkpoints, TensorBoard logs, videos and
  `results.json`.

## Outputs and settings

Every run writes `runs/<run_id>/`, which is git-ignored. A simulator run holds:
- `config.yaml`: the resolved settings; rerun with `--config runs/<ts>/config.yaml`
- `state.csv`: one row per duck every 0.02 s, with reward next to box_to_target / inside
- `events.log`: policy switches, falls, resets, `SUSPECT` reward flags, `NOTE` markers
- `notes.md`: an automatic outcome summary plus questions for you to answer
- `video.mp4`: only with `--record`

A PPO run also holds TensorBoard logs, checkpoints, short videos with an `index.md`, `model.zip` and
`results.json`.

Settings live in [configs/copush.yaml](configs/copush.yaml):
- the start layout: `close`, `steer` or `hard`, plus `overnight` in `configs/overnight.yaml`
- the reward version (`reward.version`, applied on top of `reward` from `reward_versions`)
- PPO hyperparameters
- the video settings

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'yaml'` / `'mujoco'` | You ran this repo's venv (`uv run python ...`). Use `scripts/copush.sh`, or `uv run --project ../microduck_rl python ...`. |
| `` `launch_passive` requires ... `mjpython` on macOS `` | Launch the viewer with `scripts/copush.sh --viewer`, not plain `python`. |
| Keys do nothing / `stdin is not a TTY` | Type in the terminal that launched the sim, not the viewer window, and don't pipe its input. |
| `policy file(s) missing` | `sh scripts/fetch_policies.sh` |
| A duck falls soon after switching to shoepush | Shoe Push needs the box in front of it (it fell in 5 of 6 box-less tries). Switch back with 1 / 2 and walk up on velstand. |
| `No module named pytest`, or tests "pass" with many skipped | Run them with `scripts/rl.sh -m pytest` (adds pytest, gymnasium and stable-baselines3 on top of microduck_rl's environment). |

- **Overnight queue stopped:** read the end of `queue.log`, then run the same launch command again
  to resume.
- **Don't use `scripts/sim.sh drive` for duck B** on the Week 1 path. Upstream `drive` always
  commands and reads duck A ([docs/archive/WEEK1_STATUS.md](docs/archive/WEEK1_STATUS.md)). Use
  `copush.sim_client` instead.

## Repo layout

```
copush/         sim.py (two-duck MuJoCo world), duck_policy.py (per-duck ONNX runner),
                env.py (Gymnasium env + scripted baselines), rewards.py, rl_eval.py, rl_callbacks.py,
                video.py, config.py; plus the Week 1 duck-sim client (sim_client.py, runner.py, ...)
configs/        copush.yaml (scene, layouts, reward versions, PPO, video), overnight*.yaml (queues)
scripts/        copush.sh / copush_sim.py (sim), rl.sh + rl/ (checks, baselines, train, overnight),
                b0/ (B0 harness), sim.sh, check_m1.py, two_duck_demo.py (Week 1 duck-sim path)
scenes/         copush_base.xml (floor/lights for the two-duck world), B0 and Week 1 scenes
tests/          pytest; simulator tests skip outside microduck_rl's environment
docs/           REWARD_LOG.md, TIMELINE.md, DEMO.md, media/ (README GIFs + mp4s, < 1 MB each),
                archive/ (the October plan, week 1 and B0 reports, kept for reference)
policies/       manifest.json for the trained-policies release (scripts/get_policies.sh)
.claude/skills/ copush-progress (keeps the timeline, demo, README and reward log current)
```

## The shared controller interface

```python
state = {"duck_a": {"position": (x, y), "yaw": rad, "velocity": (vx, vy)},
         "duck_b": {...},
         "box": {...} or None,
         "goal": {"position": (x, y), "yaw": rad} or None}

class MyController(copush.state.Controller):
    def get_actions(self, state):
        return {"duck_a": (vx, vy, vyaw), "duck_b": (vx, vy, vyaw)}   # body frame, robot.move units
```

World frame, metres, radians; yaw wrapped to (-pi, pi]. The sim client adds `trunk_z`, `gravity`
and `time` for health checks; controllers ignore keys they don't use.

## Week 1 path: duck-sim / robotd

This repo is a **client** of Pollen's repos and never copies their code. The Week 1 setup ran each
duck as a real `robotd` driving a MuJoCo body:
- Each duck was commanded like a robot (`robot.move` JSON-RPC, 10 Hz).
- Its state was read back from the simulator's body port.

The two-duck sim above replaced it for CoPush experiments. It runs faster than real time, and Shoe
Push misbehaves under robotd ([docs/archive/WEEK1_STATUS.md](docs/archive/WEEK1_STATUS.md)).

| repo | role | pinned in |
|---|---|---|
| [pollen-robotics/microduck](https://github.com/pollen-robotics/microduck) | `robotd` (the real robot daemon, 50 Hz loop + ONNX policies) and `scripts/duck-sim` | `upstream.lock` |
| [pollen-robotics/microduck_rl](https://github.com/pollen-robotics/microduck_rl) | `duck-body` (MuJoCo body server), scenes, policy runtime | `upstream.lock` |

Setup is the same `scripts/setup.sh` as in [Install](#install). On this path, duck-sim fetches the
policies on the first launch.

All simulator commands go through `scripts/sim.sh`, a thin wrapper over `microduck/scripts/duck-sim`:
- It sets 2 ducks and runs headless by default.
- It loads our body-server extension for the box pose and spawn placement
  (`copush/_bodyext/sitecustomize.py`).
- It passes anything else straight to duck-sim.

**M1 check (headless):**

```sh
uv run python scripts/check_m1.py            # launch, run the 20 s demo, PASS/FAIL table, shut down
uv run python scripts/check_m1.py --runs 3   # three fresh launches
```

**Viewer demo (for watching or screen recording):**

```sh
scripts/sim.sh up --viewer                   # MuJoCo window with two ducks (~30 s to stand up)
uv run python scripts/two_duck_demo.py       # A walks 8 s, B turns 8 s, both stop; CSV in data/runs/
scripts/sim.sh down
```

**Box scene:**

```sh
scripts/sim.sh up --box                      # 2 ducks + 28x10x9 cm, 150 g box 0.6 m ahead of duck A
scripts/sim.sh up --box --viewer             # same, with the window
uv run python scripts/two_duck_demo.py       # CSV now also has box_x, box_y, box_z, box_yaw
```

`--box` is `DUCK_SIM_SCENE=<abs path to scene_copush_box.xml> DUCK_SIM_KEYFRAME=HOME`.

**Plot a run:**

```sh
uv run python scripts/plot_run.py --latest                 # -> data/plots/<run>.png
uv run python scripts/plot_run.py data/runs/<run>.csv
```

**Per-duck tools:**

```sh
DUCK_SIM_DUCK=duck-b scripts/sim.sh ctl health
scripts/sim.sh realtime                      # real-time factor of the shared world
COPUSH_PLACE=";0,0.20,0" scripts/sim.sh up   # spawn duck B at (0, 0.20) instead of (0, 0.5)
```
