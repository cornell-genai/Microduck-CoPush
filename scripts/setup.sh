#!/bin/sh
# One-time (and safe-to-rerun) setup for CoPush.
#
#   scripts/setup.sh                 clone/pin upstream, uv sync, build daemons, install scene
#   COPUSH_NO_PIN=1 scripts/setup.sh leave the upstream checkouts on whatever they are on
#
# Upstream repos are expected next to this one (override with MICRODUCK=... DUCK_SIM_RL=...):
#   ../microduck      Pollen's daemons + scripts/duck-sim
#   ../microduck_rl   Pollen's simulator (duck-body), scenes, policy runtime
#
# They are read-only dependencies: this script clones them if missing and checks out the commit
# in upstream.lock, but never touches a working tree with uncommitted changes to tracked files,
# and never commits or pushes anything there.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PARENT="$(cd "$ROOT/.." && pwd)"
MICRODUCK="${MICRODUCK:-$PARENT/microduck}"
RL="${DUCK_SIM_RL:-$PARENT/microduck_rl}"

say() { printf '\033[36m==\033[0m %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

for tool in git uv cargo; do
    command -v "$tool" >/dev/null 2>&1 || die "$tool is not installed (uv: https://docs.astral.sh/uv/, cargo: https://rustup.rs)"
done

lock_field() {  # lock_field <name> <column 2..4>
    awk -v n="$1" -v c="$2" '$1 == n { print $c }' "$ROOT/upstream.lock"
}

pin() {  # pin <name> <dir>
    name="$1"; dir="$2"
    url="$(lock_field "$name" 2)"; branch="$(lock_field "$name" 3)"; commit="$(lock_field "$name" 4)"
    [ -n "$commit" ] || die "no $name entry in upstream.lock"
    if [ ! -d "$dir/.git" ]; then
        say "cloning $name into $dir"
        git clone --branch "$branch" "$url" "$dir"
    fi
    head="$(git -C "$dir" rev-parse HEAD)"
    if [ "$head" = "$commit" ]; then
        say "$name already at $(echo "$commit" | cut -c1-9)"
        return 0
    fi
    if [ "${COPUSH_NO_PIN:-0}" = 1 ]; then
        say "$name is at $(echo "$head" | cut -c1-9), lock says $(echo "$commit" | cut -c1-9) — left alone (COPUSH_NO_PIN=1)"
        return 0
    fi
    if [ -n "$(git -C "$dir" status --porcelain --untracked-files=no)" ]; then
        say "WARNING: $name has uncommitted changes to tracked files; not checking out $(echo "$commit" | cut -c1-9)."
        say "         Commit/stash them yourself, or rerun with COPUSH_NO_PIN=1."
        return 0
    fi
    git -C "$dir" cat-file -e "$commit^{commit}" 2>/dev/null || git -C "$dir" fetch --quiet origin
    # If the locked branch's tip *is* the commit, stay on the branch; otherwise detach at it.
    if [ "$(git -C "$dir" rev-parse "origin/$branch" 2>/dev/null)" = "$commit" ]; then
        git -C "$dir" checkout --quiet "$branch" && git -C "$dir" merge --quiet --ff-only "origin/$branch"
    else
        git -C "$dir" checkout --quiet --detach "$commit"
    fi
    say "$name now at $(git -C "$dir" rev-parse --short HEAD)"
}

pin microduck "$MICRODUCK"
pin microduck_rl "$RL"

say "uv sync in microduck_rl (the simulator's venv, which also provides onnxruntime)"
(cd "$RL" && uv sync --quiet)

say "building the daemons (cargo; the first build takes a few minutes)"
(cd "$MICRODUCK" && cargo build --quiet -p robotd -p robotctl -p tof -p sounds -p configd -p updater -p duck-ether)

say "installing our scenes into microduck_rl (untracked copies)"
DUCK_SIM_RL="$RL" sh "$ROOT/scripts/install_scene.sh"

say "uv sync in Microduck-CoPush"
(cd "$ROOT" && uv sync --quiet)

say "done. Next:"
cat <<'NEXT'
    scripts/sim.sh up                       # two ducks, headless (fetches policies on first run)
    uv run python scripts/check_m1.py       # the M1 checkpoint
NEXT
