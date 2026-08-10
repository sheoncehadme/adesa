#!/usr/bin/env bash
# Full test suite entry point (CI-friendly).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "############################################"
echo "# Adesa test suite"
echo "############################################"

echo ""
echo ">>> 1/5 unit tests"
make -C tests/unit test

echo ""
echo ">>> 2/5 build merc"
make -C src

echo ""
echo ">>> 3/5 boot-test + selftest"
bash tests/scripts/boot_test.sh --boot-test
bash tests/scripts/boot_test.sh --selftest

echo ""
echo ">>> 4/5 log scan"
bash tests/scripts/check_logs.sh

echo ""
echo ">>> 5/6 area_gen tests"
if command -v python3 >/dev/null 2>&1; then
  # stdlib unittest (no pytest required); pytest also works if installed
  if python3 -c "import pytest" 2>/dev/null; then
    python3 -m pytest -q tools/area_gen/test_gen_areas.py
  else
    python3 tools/area_gen/test_gen_areas.py -v
  fi
else
  echo "python3 missing; skip area_gen tests" >&2
  exit 2
fi

echo ""
echo ">>> 6/6 world connectivity (Temple -> player areas)"
python3 tests/scripts/check_connectivity.py

echo ""
echo "############################################"
echo "# ALL TESTS PASSED"
echo "############################################"
echo ""
echo "Optional (not in default suite):"
echo "  make -C src asan && bash tests/scripts/run_asan_smoke.sh"
echo "  ADESA_PORT=6000 python3 tests/scripts/smoke_telnet.py"
