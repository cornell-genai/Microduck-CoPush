#!/bin/sh
# Copy our scenes into microduck_rl's robot directory, where their relative <include>s resolve.
#
# scenes/scene_box.xml  ->  $DUCK_SIM_RL/src/mjlab_microduck/robot/microduck/scene_copush_box.xml
#
# Installed under a `scene_copush_*` name so it can never collide with an upstream scene, and it
# stays an *untracked* file there: this script refuses to overwrite anything git tracks. Safe to
# rerun (it just refreshes the copy). Then `DUCK_SIM_SCENE=copush_box` also works as a bare name.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RL="${DUCK_SIM_RL:-$(cd "$ROOT/.." && pwd)/microduck_rl}"
DEST_DIR="$RL/src/mjlab_microduck/robot/microduck"
[ -d "$DEST_DIR" ] || { echo "error: no $DEST_DIR (set DUCK_SIM_RL=...)" >&2; exit 1; }

install_one() {
    src="$ROOT/scenes/$1"; dest="$DEST_DIR/$2"
    if git -C "$RL" ls-files --error-unmatch "$dest" >/dev/null 2>&1; then
        echo "error: $dest is tracked by microduck_rl; refusing to overwrite it" >&2
        exit 1
    fi
    cp "$src" "$dest"
    echo "installed $dest (untracked)"
}

install_one scene_box.xml scene_copush_box.xml
