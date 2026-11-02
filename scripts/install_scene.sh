#!/bin/sh
# Copy our scenes into microduck_rl's robot directory, where their relative <include>s resolve.
#
# scenes/scene_box.xml        ->  $DUCK_SIM_RL/src/mjlab_microduck/robot/microduck/scene_copush_box.xml
# scenes/scene_b0_<dir>.xml    ->  .../scene_copush_b0_<dir>.xml             (dir = forward, backward)
#                              +   .../scene_copush_b0_<dir>_nobacklash.xml  (same box, robot_groundcontact.xml)
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

# B0 scenes (one duck + box, scripts/b0/). The _nobacklash twin swaps only the robot include, so the
# two differ in nothing but the joint backlash.
for dir in forward backward; do
    install_one "scene_b0_$dir.xml" "scene_copush_b0_$dir.xml"
    nb="$DEST_DIR/scene_copush_b0_${dir}_nobacklash.xml"
    if git -C "$RL" ls-files --error-unmatch "$nb" >/dev/null 2>&1; then
        echo "error: $nb is tracked by microduck_rl; refusing to overwrite it" >&2
        exit 1
    fi
    sed -e 's|robot_groundcontact_backlash.xml|robot_groundcontact.xml|' \
        -e "s|model=\"scene_copush_b0_$dir\"|model=\"scene_copush_b0_${dir}_nobacklash\"|" \
        "$ROOT/scenes/scene_b0_$dir.xml" > "$nb"
    echo "installed $nb (untracked)"
done
