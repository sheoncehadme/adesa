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
