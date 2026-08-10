#!/usr/bin/env bash
# Build with AddressSanitizer and run --selftest.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/src"

echo "==> building merc-asan"
make clean
make asan

if [[ ! -x ./merc-asan && ! -x ./merc ]]; then
  echo "error: asan binary missing" >&2
  exit 2
fi

BIN=./merc
if [[ -x ./merc-asan ]]; then
  BIN=./merc-asan
fi

export ASAN_OPTIONS="${ASAN_OPTIONS:-detect_leaks=0:halt_on_error=1}"
# detect_leaks=0: SSM intentionally holds long-lived strings; freelist UAF is the goal

cd "$ROOT/area"
echo "==> $BIN --selftest under ASan"
"$ROOT/src/$(basename "$BIN")" --selftest
echo "==> ASan smoke OK"

# Restore a normal (non-instrumented) merc for day-to-day use
cd "$ROOT/src"
echo "==> restoring normal merc build"
make clean
make
