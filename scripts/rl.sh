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
# Memory guard (scripts/guard/memwatch.sh): a watchdog next to the job stops the whole job if one of its processes
# passes COPUSH_MEM_LIMIT_GB (default 3) or all of them together pass COPUSH_MEM_TOTAL_GB (default 12), so a leak
# cannot fill the swap. COPUSH_MEM_LIMIT_GB=0 turns it off. One watchdog per job: nested rl.sh calls reuse it.
PGID="$(ps -o pgid= -p $$ | tr -d ' ')"
if [ "${COPUSH_MEM_LIMIT_GB:-3}" != "0" ] && [ "${COPUSH_MEM_WATCH:-}" != "$PGID" ]; then
  export COPUSH_MEM_WATCH="$PGID"
  if command -v perl >/dev/null 2>&1; then                      # perl only puts the watchdog in its own process group
    perl -e 'setpgrp(0, 0); exec @ARGV' sh "$ROOT/scripts/guard/memwatch.sh" "$PGID" "${COPUSH_MEM_LIMIT_GB:-3}" \
      "${COPUSH_MEM_TOTAL_GB:-12}" "$ROOT" "${COPUSH_MEM_GUARD_EVERY_S:-5}" </dev/null >/dev/null &
  else
    echo "rl.sh: perl not found, the memory guard is OFF for this job" >&2
  fi
fi
exec uv run --project "$RL" --with "gymnasium==1.4.0" --with "stable-baselines3==2.9.2" --with "pytest" python "$@"
