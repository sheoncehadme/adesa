# Adesa test suite

## Quick start

```sh
# From repo root — full suite
make test
```

## Layers

| Layer | Command | What it covers |
|-------|---------|----------------|
| Unit | `make unit-test` | SSM, freelist free-order, MD5 |
| Boot | `make test-boot` | Load all areas, exit cleanly |
| Selftest | `make test-self` | Boot + free_reset / note free / SSM / scheck |
| Logs | `tests/scripts/check_logs.sh` | Critical patterns in recent acklog |
| area_gen | `python3 tools/area_gen/test_gen_areas.py -v` | Generator output + determinism |
| ASan | `make asan-smoke` | AddressSanitizer build + selftest |
| Telnet | `python3 tests/scripts/smoke_telnet.py` | Live connect (server must be up) |
| Connectivity | `python3 tests/scripts/check_connectivity.py` | Temple walk graph covers player areas |

## Headless merc modes

Run from `area/` (paths use `../data` and relative area files):

```sh
cd area
../src/merc --boot-test
../src/merc --selftest
```

## Layout

```
tests/
  unit/           # pure C unit tests + Makefile
  scripts/        # boot, selftest, logs, asan, run_all, smoke_telnet
  README.md
tools/area_gen/test_gen_areas.py
```

## Notes

- Freelist UAF is best caught with ASan (`make asan-smoke`).
- SSM refcount issues are best caught with `scheck` / `--selftest` (not ASan leak detection).
- Telnet login/scheck requires `ADESA_USER` / `ADESA_PASS` (and imm trust for scheck).
