#!/bin/sh
# Overnight PPO queue (scripts/rl/overnight.py), kept awake by caffeinate. Launch detached:
#
#   nohup scripts/rl/overnight.sh --config configs/overnight.yaml >> runs/overnight-<date>/queue.log 2>&1 &
#
# Restarting it with the same command resumes: finished runs are skipped, the interrupted run
# continues from its last checkpoint. Stop: kill $(cat runs/overnight-<date>/queue.pid)
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec caffeinate -ims "$ROOT/scripts/rl.sh" "$ROOT/scripts/rl/overnight.py" "$@"
