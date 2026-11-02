#!/bin/sh
# Thin wrapper around Pollen's microduck/scripts/duck-sim with CoPush's defaults.
#
#   scripts/sim.sh up                 2 ducks, headless, default (backlash) floor scene
#   scripts/sim.sh up --viewer        same, with the MuJoCo window (for watching / recording)
#   scripts/sim.sh up --box           2 ducks + the free-joint box (scenes/scene_box.xml)
#   scripts/sim.sh up --box --viewer
#   scripts/sim.sh down
#   scripts/sim.sh <anything>         passed straight to duck-sim: ctl health, realtime, log, ...
#   DUCK_SIM_DUCK=duck-b scripts/sim.sh ctl health
#
# What it adds, without touching either upstream repo:
#   * DUCK_SIM_RL / DUCK_SIM_DUCKS set, and the upstream checkouts found next to this repo
#     (override with MICRODUCK=... DUCK_SIM_RL=...).
#   * PYTHONPATH=copush/_bodyext on `up`, so the body server answers {"op":"objects"} (box pose)
#     and honours COPUSH_PLACE (spawn poses). See copush/_bodyext/sitecustomize.py.
#   * --box selects our scene (installed by scripts/install_scene.sh) with DUCK_SIM_KEYFRAME=HOME,
#     since a scene with a free joint has no keyframes.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MICRODUCK="${MICRODUCK:-$(cd "$ROOT/.." && pwd)/microduck}"
export DUCK_SIM_RL="${DUCK_SIM_RL:-$(cd "$ROOT/.." && pwd)/microduck_rl}"
export DUCK_SIM_DUCKS="${DUCK_SIM_DUCKS:-2}"
DUCK_SIM="$MICRODUCK/scripts/duck-sim"
BOX_SCENE="$DUCK_SIM_RL/src/mjlab_microduck/robot/microduck/scene_copush_box.xml"

[ -x "$DUCK_SIM" ] || { echo "error: no duck-sim at $DUCK_SIM (set MICRODUCK=...)" >&2; exit 1; }
[ -d "$DUCK_SIM_RL" ] || { echo "error: no microduck_rl at $DUCK_SIM_RL (set DUCK_SIM_RL=...)" >&2; exit 1; }

if [ "${1:-}" = up ]; then
    shift
    export DUCK_SIM_VIEWER="${DUCK_SIM_VIEWER:-0}"
    for arg in "$@"; do
        case "$arg" in
            --viewer) export DUCK_SIM_VIEWER=1 ;;
            --headless) export DUCK_SIM_VIEWER=0 ;;
            --box)
                [ -f "$BOX_SCENE" ] || sh "$ROOT/scripts/install_scene.sh"
                export DUCK_SIM_SCENE="$BOX_SCENE"
                export DUCK_SIM_KEYFRAME=HOME ;;
            *) echo "error: unknown option $arg (use --viewer, --headless, --box)" >&2; exit 1 ;;
        esac
    done
    export PYTHONPATH="$ROOT/copush/_bodyext${PYTHONPATH:+:$PYTHONPATH}"
    exec "$DUCK_SIM" up
fi

exec "$DUCK_SIM" "$@"
