#!/bin/sh
# One-command launcher for scripts/copush_sim.py in microduck_rl's environment
# (mujoco, onnxruntime, bam). With --viewer on macOS it runs under MuJoCo's mjpython, which the
# passive viewer needs; everything else runs under plain python.
#
#   scripts/copush.sh --viewer
#   scripts/copush.sh --headless --duration 15 --script push_forward [--record]
#
# microduck_rl is $DUCK_SIM_RL or ../microduck_rl, as scripts/sim.sh.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RL="${DUCK_SIM_RL:-$(cd "$ROOT/.." && pwd)/microduck_rl}"
PY=python
for arg in "$@"; do
    if [ "$arg" = "--viewer" ] && [ "$(uname)" = "Darwin" ]; then PY=mjpython; fi
done
exec uv run --project "$RL" "$PY" "$ROOT/scripts/copush_sim.py" "$@"
