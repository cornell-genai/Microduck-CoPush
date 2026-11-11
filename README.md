# Microduck-CoPush

Two simulated Pollen MicroDucks cooperatively pushing a box in MuJoCo: first with scripted
coordination, later with a learned high-level controller. Plan: [docs/COPUSH_PLAN.md](docs/COPUSH_PLAN.md).
Week 1 status: [docs/WEEK1_STATUS.md](docs/WEEK1_STATUS.md).

This repo is a **client** of Pollen's repos and never copies their code:

| repo | role | pinned in |
|---|---|---|
| [pollen-robotics/microduck](https://github.com/pollen-robotics/microduck) | `robotd` (the real robot daemon, 50 Hz loop + ONNX policies) and `scripts/duck-sim` | `upstream.lock` |
| [pollen-robotics/microduck_rl](https://github.com/pollen-robotics/microduck_rl) | `duck-body` (MuJoCo body server), scenes, policy runtime | `upstream.lock` |

Each duck is a real `robotd` driving a MuJoCo body. We command it like a robot (`robot.move`
JSON-RPC on its socket, resent at 10 Hz) and read ground truth from the simulator's body port.

## Setup (macOS / Linux)

Needs `git`, [`uv`](https://docs.astral.sh/uv/) and Rust (`cargo`). Clone this repo next to the
upstream ones (setup clones them if missing):

```
~/CS_Projects/GenAI/
├── Microduck-CoPush/   (this repo)
├── microduck/
└── microduck_rl/
```

```sh
cd Microduck-CoPush
scripts/setup.sh
```

`setup.sh` is safe to rerun. It clones/pins both upstream repos to `upstream.lock` (never over
local changes; `COPUSH_NO_PIN=1` to skip pinning), runs `uv sync` in microduck_rl and here, builds
the daemons, and installs our scene into microduck_rl as an untracked `scene_copush_box.xml`.
Policies are fetched by duck-sim on the first launch.

## Two-duck sim (B0 harness path, faster than real time)

Two backlash ducks + box + target on the B0 harness (BAM actuators, ONNX policies), without
duck-sim/robotd. Quick guide: [docs/SIM_GUIDE.md](docs/SIM_GUIDE.md), one page:
[docs/CHEATSHEET.md](docs/CHEATSHEET.md).

```sh
scripts/copush.sh --viewer                                        # drive both ducks from the terminal
scripts/copush.sh --headless --duration 15 --script push_forward  # -> runs/<timestamp>/
```

## Commands

All simulator commands go through `scripts/sim.sh`, a thin wrapper over `microduck/scripts/duck-sim`
that sets 2 ducks, headless by default, and loads our body-server extension (box pose, spawn
placement; see `copush/_bodyext/sitecustomize.py`). Anything else is passed straight to duck-sim.

**M1 check (headless):**

```sh
uv run python scripts/check_m1.py            # launch, run the 20 s demo, PASS/FAIL table, shut down
uv run python scripts/check_m1.py --runs 3   # three fresh launches
```

**Viewer demo (for watching / screen recording):**

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

Do not use `scripts/sim.sh drive` for duck B: upstream `drive` always commands and reads duck A
(see docs/WEEK1_STATUS.md). Use `copush.sim_client` instead.

**Tests (no simulator needed):**

```sh
uv run pytest
```

## Layout

```
copush/            library: state.py (shared state + Controller), sim_client.py, controllers.py,
                   runner.py (10 Hz loop), recorder.py (CSV), metrics.py, _bodyext/ (body-server extension)
scripts/           setup.sh, sim.sh, install_scene.sh, two_duck_demo.py, check_m1.py, plot_run.py
scenes/            scene_box.xml
tests/             tests on data/sample/mock_run.csv
docs/              COPUSH_PLAN.md, WEEK1_STATUS.md, results
data/sample/       mock CSV for tests (data/runs/ and data/plots/ are gitignored)
```

## The shared interface

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
