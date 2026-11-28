#!/bin/sh
# Memory watchdog for a job started through scripts/rl.sh. It runs next to the job (not inside Python, so it cannot
# interfere with fork or with worker pools) and every few seconds adds up the memory footprint of every process in the
# job's process group, as `top` reports it (compressed and swapped memory included; resident size alone hides a leak).
# If one process passes the per-process limit, or the whole job passes the total limit, it prints why, appends a line
# to runs/memguard.log and stops the whole job. It exists because a leaking measurement script grew to 32 GB on a
# 16 GB machine on 2026-11-27 and 28.
#
#   memwatch.sh PGID PER_PROCESS_GB TOTAL_GB ROOT [EVERY_S]
PGID="$1"; PER="$2"; TOTAL="$3"; ROOT="$4"; EVERY="${5:-5}"
# rl.sh starts this script in its OWN process group, so the job's group holds only the job.
TICK=0
while :; do
  sleep 1
  kill -0 -- "-$PGID" 2>/dev/null || exit 0                     # the job is gone: stop within a second
  TICK=$((TICK + 1))
  [ $((TICK % EVERY)) -eq 0 ] || continue
  OUT=$(top -l 1 -stats pid,pgrp,mem 2>/dev/null | awk -v g="$PGID" -v per="$PER" -v tot="$TOTAL" '
    function gb(s,  n, u) { sub(/[+-]$/, "", s); u = substr(s, length(s)); n = substr(s, 1, length(s) - 1) + 0
      if (u == "G") return n; if (u == "M") return n / 1024; if (u == "K") return n / 1048576; if (u == "B") return n / 1073741824
      return (s + 0) / 1073741824 }
    $1 ~ /^[0-9]+$/ && $2 == g { m = gb($3); sum += m; n++; if (m > big) { big = m; bigpid = $1 } }
    END { if (big > per) printf "process %s uses %.1f GB, over the %s GB per-process limit (COPUSH_MEM_LIMIT_GB)", bigpid, big, per
          else if (sum > tot) printf "the job (%d processes) uses %.1f GB, over the %s GB job limit (COPUSH_MEM_TOTAL_GB)", n, sum, tot }')
  [ -z "$OUT" ] && continue
  MSG="MEMORY GUARD: $OUT. Stopping the job. Find the leak before rerunning."
  echo "" >&2; echo "$MSG" >&2
  [ -d "$ROOT/runs" ] && echo "$(date '+%Y-%m-%d %H:%M:%S')  $MSG" >> "$ROOT/runs/memguard.log" 2>/dev/null
  kill -TERM -- "-$PGID" 2>/dev/null
  sleep 3
  kill -KILL -- "-$PGID" 2>/dev/null
  exit 0
done
