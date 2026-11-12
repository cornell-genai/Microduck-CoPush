# Setup and commands

Everything technical for running Microduck-CoPush: install, the two-duck simulator, RL checks,
training, tests, the overnight queue, troubleshooting, and the older duck-sim / robotd path.
Run all commands from the repo root unless a section says otherwise.

For the simulator, [docs/SIM_GUIDE.md](docs/SIM_GUIDE.md) is the detailed guide (keys, start
positions, the Python API, common problems) and [docs/CHEATSHEET.md](docs/CHEATSHEET.md) is a
one-page version. This file links to them instead of repeating them.

## Contents

- [Install](#install)
- [Run the two-duck simulator](#run-the-two-duck-simulator)
- [RL: checks, baselines and training](#rl-checks-baselines-and-training)
- [Tests](#tests)
- [Overnight queue](#overnight-queue)
- [Outputs and settings](#outputs-and-settings)
- [Troubleshooting](#troubleshooting)
- [Repo layout](#repo-layout)
- [The shared controller interface](#the-shared-controller-interface)
- [Week 1 path: duck-sim / robotd](#week-1-path-duck-sim--robotd)

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

More detail: [docs/SIM_GUIDE.md, Setup](docs/SIM_GUIDE.md#setup-once).

## Run the two-duck simulator

```sh
scripts/copush.sh --viewer                                        # watch + drive both ducks from the terminal
scripts/copush.sh --headless --duration 15 --script push_forward  # scripted push -> runs/<timestamp>/
scripts/copush.sh --duck-a 0,0.1,0 --box 0.4,0,90 --target 1.2,0,90 --box-mass 0.2   # custom start
```

- **Keyboard controls** for driving the ducks in the viewer:
  [docs/SIM_GUIDE.md, Launch](docs/SIM_GUIDE.md#launch) and
  [docs/CHEATSHEET.md](docs/CHEATSHEET.md).
- **Start positions:** [Setting positions](docs/SIM_GUIDE.md#setting-positions).
- **Scripting from Python:** [Scripting in Python](docs/SIM_GUIDE.md#scripting-in-python).

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

## Tests

```sh
scripts/rl.sh -m pytest
```

Use `scripts/rl.sh -m pytest`, not plain `uv run pytest`. The plain version skips the simulation
tests, because that environment has no MuJoCo, so it can look like everything passed when the sim
tests never ran. More: [docs/SIM_GUIDE.md, Tests](docs/SIM_GUIDE.md#tests).

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

Every run writes `runs/<run_id>/`, which is git-ignored. It holds:
- the config
- CSV logs and events
- short videos with an `index.md`
- for PPO, the TensorBoard logs and `model.zip`

More: [docs/SIM_GUIDE.md, Where output goes](docs/SIM_GUIDE.md#where-output-goes).

Settings live in [configs/copush.yaml](configs/copush.yaml):
- the start layout: `close`, `steer` or `hard`, plus `overnight` in `configs/overnight.yaml`
- the reward version (`reward.version`, applied on top of `reward` from `reward_versions`)
- PPO hyperparameters
- the video settings

## Troubleshooting

- **Tests "pass" but the sim tests didn't run:** use `scripts/rl.sh -m pytest` (see [Tests](#tests)).
- **Simulator problems** (policies missing, viewer, start positions):
  [docs/SIM_GUIDE.md, Common problems](docs/SIM_GUIDE.md#common-problems).
- **Overnight queue stopped:** read the end of `queue.log`, then run the same launch command again
  to resume.
- **Don't use `scripts/sim.sh drive` for duck B** on the Week 1 path. Upstream `drive` always
  commands and reads duck A ([docs/WEEK1_STATUS.md](docs/WEEK1_STATUS.md)). Use
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
docs/           guides, results, media/ (README GIFs + mp4s, < 1 MB each)
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
Push misbehaves under robotd ([docs/WEEK1_STATUS.md](docs/WEEK1_STATUS.md)).

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
