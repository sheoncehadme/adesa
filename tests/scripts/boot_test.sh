#!/usr/bin/env bash
# Boot the world and exit. Must run with repo-relative paths.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MERC="${MERC:-$ROOT/src/merc}"
MODE="${1:---boot-test}"

if [[ ! -x "$MERC" ]]; then
  echo "error: merc not found at $MERC (build with: make -C src)" >&2
  exit 2
fi

if [[ "$MODE" != "--boot-test" && "$MODE" != "--selftest" ]]; then
  echo "usage: $0 [--boot-test|--selftest]" >&2
  exit 2
fi

cd "$ROOT/area"
echo "==> running: $MERC $MODE (cwd=$PWD)"
# stderr carries BOOT-TEST/SELFTEST OK lines; game logs go to ../log/
"$MERC" "$MODE"
echo "==> $MODE completed successfully"
