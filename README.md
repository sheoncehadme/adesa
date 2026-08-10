# adesa

Adesa, a heavily modified ACK!MUD 4.2. Development stopped in 2005. Source retains the original Merc/Diku/Ack licences where appropriate.

Ported to build and run on modern 64-bit hosts (macOS arm64/x86_64, Linux).

## Requirements

- A C compiler (`cc` / clang / gcc)
- zlib development headers (`-lz`) — used for MCCP compression
- On **Linux**: `libcrypt` / `libxcrypt` (`-lcrypt`) for password hashing  
  On **macOS**: crypt is in libc; no extra package

## To build

```sh
cd src && make
# or from repo root:
make
```

Optional:

```sh
make -C src NOCRYPT=1   # plain-text passwords (legacy export flag; not recommended)
make clean
make -C src asan        # AddressSanitizer binary: src/merc-asan
```

The resulting binary is `src/merc` (Mach-O arm64 on Apple Silicon, ELF on Linux).

## To run

```sh
cd area && ../src/startup.m
# or directly:
cd area && ../src/merc 6000
```

Default port is `6000` via `startup.m`, or `1234` if you run `merc` with no args.

### Security notes

- **Passwords** are stored as salted, iterated MD5 (`$s$…`). Legacy DES/`crypt` and plain 32-char MD5 still verify and are upgraded on successful login. Minimum length is **8**.
- **Login brute-force**: more than 10 failures from the same IP within 5 minutes are rejected temporarily.
- **Bind address**: set `MUD_BIND=127.0.0.1` (or another address) before start to avoid listening on all interfaces.
- Prefer TLS (stunnel/proxy) or a VPN; the game protocol itself is cleartext.
- Freelist corruption aborts via `hang()` instead of locking the process in an infinite loop.

## Testing

There was no historical unit-test suite; Adesa now has a layered harness under `tests/`.

```sh
# Full suite (unit + build + boot + selftest + log scan + area_gen pytest)
make test

# Pieces
make unit-test              # SSM / freelist / MD5 pure unit tests
make -C src test-boot       # load all areas, exit
make -C src test-self       # boot + memory lifecycle self-tests
make asan-smoke             # ASan build + --selftest (slower)
```

**Headless modes** (CWD must be `area/` so `../data` and area files resolve):

```sh
cd area && ../src/merc --boot-test   # load world, exit 0
cd area && ../src/merc --selftest    # load world, free_reset/note/SSM/scheck checks
```

**In-game oracles** (immortal): `memory`, `memory defrag`, `memory log`, `scheck` (writes `leaks.dmp`).

**Live socket smoke** (server must already be running):

```sh
python3 tests/scripts/smoke_telnet.py
ADESA_PORT=6000 ADESA_USER=Ogma ADESA_PASS=secret ADESA_RUN_SCHECK=1 \
  python3 tests/scripts/smoke_telnet.py
```

**area_gen** (stdlib `unittest`; pytest optional):

```sh
python3 tools/area_gen/test_gen_areas.py -v
# or, if pytest is installed:
python3 -m pytest -q tools/area_gen/test_gen_areas.py
```

See `tests/scripts/run_all.sh` for the CI entry point.

## Notes on the modern port

- **Makefile**: no longer uses pure `-ansi` or unconditional `-lcrypt` (macOS has no separate libcrypt).
- **DNS**: fixed a null-host crash when nameserver lookup fails; bind uses `inet_addr` instead of deprecated `gethostbyname("0.0.0.0")`.
- **mudsets**: null string settings are saved/loaded as empty rather than the literal `"(null)"`.
- **signals**: alarm handler uses `SA_RESTART` instead of a hardcoded flag value of `1`.

## Progression zones (Realm Road)

A generated D&D-inspired campaign chain covers levels **1–90** with full gear sets:

| Zone | Levels | Entry vnum | Theme |
|------|--------|------------|--------|
| `realmroad.are` | hub | 22500 | Crossroads / shops path |
| `borderkeep.are` | 1–10 | 22600 | Keep on the Borderlands |
| `caveschaos.are` | 5–15 | 22700 | Caves of Chaos |
| `hillgiant.are` | 15–25 | 22800 | Hill giant steading |
| `frosthold.are` | 25–35 | 22900 | Frost giants |
| `firepeak.are` | 35–45 | 23000 | Fire giants |
| `underdark.are` | 40–50 | 23100 | Underdark descent |
| `vaultshadow.are` | 50–60 | 23200 | Drow vault |
| `elementaltemple.are` | 55–65 | 23300 | Elemental temple |
| `tombwhispers.are` | 60–70 | 23400 | Tomb crawl |
| `demonweb.are` | 70–80 | 23500 | Demonweb |
| `dragonspire.are` | 75–85 | 23600 | Dragon lairs |
| `astralcourt.are` | 80–90 | 23700 | Astral endgame |

Zones are linked west/east in order, and the hub links **north to Midgaard west gate (3052)** so mortals can walk the whole campaign from the Temple. Immortals: `goto 22500`.

Regenerate zones with:

```sh
python3 tools/area_gen/gen_areas.py
# re-apply non-generated world links (school, ethereal, maze, etc.):
python3 tools/world_connect.py
```

Check walkability from the Temple (also required for auto-quests, which pathfind from vnum 3001):

```sh
python3 tests/scripts/check_connectivity.py
```
