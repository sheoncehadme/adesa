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
```

Optional:

```sh
make NOCRYPT=1   # plain-text passwords (legacy export flag; not recommended)
make clean
```

The resulting binary is `src/merc` (Mach-O arm64 on Apple Silicon, ELF on Linux).

## To run

```sh
cd area && ../src/startup.m
# or directly:
cd area && ../src/merc 6000
```

Default port is `6000` via `startup.m`, or `1234` if you run `merc` with no args.

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

Zones are linked west/east in order. Immortals: `goto 22500`. Regenerate with:

```sh
python3 tools/area_gen/gen_areas.py
```
