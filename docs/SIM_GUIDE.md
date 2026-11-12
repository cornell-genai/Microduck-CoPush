# Two-duck sim: quick guide

Two MicroDucks and a 28 × 10 × 9 cm box in one MuJoCo world, for CoPush. It uses the B0 harness
path (CPU MuJoCo, 200 Hz physics, 50 Hz ONNX policy, BAM servo model), not duck-sim/robotd. It runs
about 20× faster than real time headless. One-page reference: [CHEATSHEET.md](CHEATSHEET.md).

## Setup (once)

You need `microduck_rl` cloned next to this repo with its environment synced, and the policies
downloaded. Use the repo's existing scripts ([SETUP.md, Install](../SETUP.md#install)): `scripts/setup.sh`, then
`sh scripts/fetch_policies.sh`. *These were not re-run while writing this guide.* To check that
everything is in place:

```sh
uv run --project ../microduck_rl python -c "import mujoco, onnxruntime, bam, yaml, mediapy"
ls data/policies/velstand_v8/velstand.onnx data/policies/robert/shoe_push/forward/policy.onnx
```

## Launch

```sh
scripts/copush.sh --viewer                                        # window + drive from the terminal
scripts/copush.sh --headless --duration 15 --script push_forward  # scripted push, no window
scripts/copush.sh --headless --duration 15 --script push_forward --record   # + video.mp4
```

`copush.sh` runs `scripts/copush_sim.py` in microduck_rl's environment and switches to `mjpython`
for `--viewer` on macOS. In `--viewer` mode, click the **terminal** and type there. The viewer
window is only for watching, and letters typed into it trigger MuJoCo's own shortcuts.

| Key | Duck A | Duck B |
|---|---|---|
| forward / back (vx ± 0.05) | W / S | I / K |
| turn left / right (vyaw ± 0.3) | A / D | J / L |
| toggle policy velstand ↔ shoepush | 1 | 2 |
| stop this duck | X | M |

Space stops both ducks, R resets the scene, N writes a note marker to events.log, and Q quits.
Every 0.5 s a status line shows box→target distance, inside, each duck's policy, command and
contact, and the reward.

## Setting positions

Edit [configs/copush.yaml](../configs/copush.yaml) (metres; yaw in degrees; 0 = facing +x):

```yaml
duck_a: {x: 0.0, y: 0.10, yaw: 0, policy: velstand}
box:    {x: 0.35, y: 0.0, yaw: 90, mass: 0.15}     # yaw 90 = long face toward the ducks
target: {x: 1.20, y: 0.0, yaw: 90, size: [0.40, 0.20]}
```

Or override from the command line (negative numbers are fine):

```sh
scripts/copush.sh --headless --duck-a 0,0.1,0 --duck-b -0.05,-0.12,15 --box 0.4,0,90 --target 1.2,0,90 --box-mass 0.2
```

Ducks spawn already standing in the policy's default pose at exactly the yaw you set. There is no
stand-up phase, so the SIT-keyframe fix from Week 1 is only needed on the duck-sim path.

## Scripting in Python

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
in `CoPushSim.get_state` ([copush/sim.py](../copush/sim.py)). To try a different reward, write a
`(prev_state, state) -> float` function and add it to `REWARDS` in
[copush/rewards.py](../copush/rewards.py).

## Where output goes

Every run creates `runs/<timestamp>/` (gitignored):
- `config.yaml`: the resolved settings; rerun with `--config runs/<ts>/config.yaml`
- `state.csv`: one row per duck every 0.02 s, with reward next to box_to_target / inside
- `events.log`: policy switches, falls, resets, `SUSPECT` reward flags, `NOTE` markers
- `notes.md`: an automatic outcome summary plus questions for you to answer
- `video.mp4`: only with `--record`

## Tests

```sh
scripts/rl.sh -m pytest
```

A plain `uv run pytest` skips the simulation tests, because that environment has no MuJoCo, so it
can look like everything passed when the sim tests never ran.

## Common problems

| Symptom | Fix |
|---|---|
| `No module named 'yaml'` / `'mujoco'` | You ran this repo's venv (`uv run python ...`). Use `scripts/copush.sh`, or `uv run --project ../microduck_rl python ...`. |
| `` `launch_passive` requires ... `mjpython` on macOS `` | Launch the viewer with `scripts/copush.sh --viewer`, not plain `python`. |
| Keys do nothing / `stdin is not a TTY` | Type in the terminal that launched the sim, not the viewer window, and don't pipe its input. |
| `policy file(s) missing` | `sh scripts/fetch_policies.sh` |
| A duck falls soon after switching to shoepush | Shoe Push needs the box in front of it (it fell in 5 of 6 box-less tries). Switch back with 1 / 2 and walk up on velstand. |
| `No module named pytest`, or tests "pass" with many skipped | Run them with `scripts/rl.sh -m pytest` (adds pytest, gymnasium and stable-baselines3 on top of microduck_rl's environment). |
