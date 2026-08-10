#!/usr/bin/env bash
# Scan recent MUD logs for fatal / SSM / hang patterns.
# Exit 1 if critical patterns are found in the scan window.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOGDIR="${LOGDIR:-$ROOT/log}"
# How many lines of the newest acklog to scan
LINES="${LINES:-500}"

shopt -s nullglob
acklogs=("$LOGDIR"/acklog.*)
if [[ ${#acklogs[@]} -eq 0 ]]; then
  echo "check_logs: no acklog.* in $LOGDIR (skip)"
  exit 0
fi

# Newest by mtime
newest="$(ls -t "${acklogs[@]}" | head -1)"
echo "==> scanning last $LINES lines of $newest"

# Patterns that indicate serious problems during boot/selftest.
# Note: historical "bug(" noise exists; focus on fatal/SSM/abort markers.
if tail -n "$LINES" "$newest" | grep -E \
  -e 'SELFTEST: FAILED' \
  -e 'BOOT-TEST: FAILED' \
  -e 'SSM: free_string: multiple free' \
  -e 'SSM: Can.t allocate' \
  -e 'GET_FREE: freelist head is NOT FREE' \
  -e 'PUT_FREE: item is ALREADY FREE' \
  -e 'Alarm clock' \
  -e 'Abort trap' \
  -e 'Segmentation fault' \
  ; then
  echo "check_logs: CRITICAL patterns found" >&2
  exit 1
fi

echo "check_logs: OK (no critical patterns in last $LINES lines)"
