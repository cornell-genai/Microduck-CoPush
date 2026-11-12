#!/bin/sh
# Python in microduck_rl's environment plus the RL packages, added as a uv --with overlay (cached
# by uv, nothing is installed into microduck_rl's venv). Versions pinned for reproducibility.
#
#   scripts/rl.sh scripts/rl/check_env.py
#   scripts/rl.sh -m pytest tests/test_env.py
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RL="${DUCK_SIM_RL:-$(cd "$ROOT/.." && pwd)/microduck_rl}"
cd "$ROOT"
exec uv run --project "$RL" --with "gymnasium==1.4.0" --with "stable-baselines3==2.9.2" --with "pytest" python "$@"
