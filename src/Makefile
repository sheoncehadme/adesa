# Adesa MUD — Makefile for modern Unix (macOS arm64/x86_64, Linux)
#
# Historically this used -ansi and -lcrypt unconditionally. Modern macOS has
# crypt(3) in libc (no -lcrypt), and clang's default ABI is 64-bit arm64/x86_64.

CC      ?= cc
PROF    =
NOCRYPT =

# Detect OS for library differences
UNAME_S := $(shell uname -s 2>/dev/null || echo Unknown)

# Prefer a slightly modern dialect with GNU extensions (inline, etc.) while
# remaining close to the original C89-era code. Avoid pure -ansi: it hides
# POSIX prototypes (crypt, strncasecmp, socklen_t helpers, etc.).
C_FLAGS = -O2 -g -Wall -std=gnu89 $(PROF)
L_FLAGS = -O2 -g $(PROF)

# Feature-test macros: expose POSIX / platform APIs without inventing symbols.
ifeq ($(UNAME_S),Darwin)
  C_FLAGS += -D_DARWIN_C_SOURCE
  # crypt(3) lives in libc on macOS; there is no -lcrypt
  CRYPT_LIB =
else
  C_FLAGS += -D_DEFAULT_SOURCE -D_BSD_SOURCE
  # Linux / most Unix still need libxcrypt or libcrypt
  CRYPT_LIB = -lcrypt
endif

# Optional: make NOCRYPT=1 to store passwords in plain text (legacy US export flag)
ifneq ($(NOCRYPT),)
  C_FLAGS += -DNOCRYPT
  CRYPT_LIB =
endif

LIBS = -lm -lz $(CRYPT_LIB)

O_FILES = auction.o dns.o treasury.o act_comm.o act_info.o act_move.o act_obj.o act_wiz.o comm.o const.o \
          db.o fight.o handler.o interp.o magic.o magic2.o mob_commands.o mob_prog.o \
	  save.o special.o update.o board.o areasave.o buildtab.o build.o \
          write.o act_clan.o buildare.o hunt.o clutch.o \
          obj_fun.o macros.o trigger.o magic3.o quest.o lists.o \
          social-edit.o mount.o pdelete.o wizutil.o ssm.o \
	  scheck.o rulers.o spendqp.o enchant.o mccp.o trade.o md5c.o duel.o magic4.o version.o


all: merc

build: all

merc: $(O_FILES)
	rm -f merc
	$(CC) $(L_FLAGS) -o merc $(O_FILES) $(LIBS)
	@mv version.c version.c.last 2>/dev/null || true

# AddressSanitizer build (freelist UAF / invalid free). Binary: merc-asan
# Usage: make asan && cd ../area && ../src/merc-asan --selftest
# Always cleans first so instrumented .o files are not mixed with a normal link.
asan:
	$(MAKE) clean
	$(MAKE) C_FLAGS="$(C_FLAGS) -fsanitize=address -fno-omit-frame-pointer -O1" \
	        L_FLAGS="$(L_FLAGS) -fsanitize=address" \
	        merc-asan
	@echo "Built merc-asan (ASAN). Example: cd ../area && ../src/merc-asan --selftest"
	@echo "Note: object files are ASan-instrumented; run 'make clean && make' for a normal merc."

merc-asan: $(O_FILES)
	$(CC) $(L_FLAGS) -o merc-asan $(O_FILES) $(LIBS)
	@mv version.c version.c.last 2>/dev/null || true

.c.o: merc.h
	$(CC) -c $(C_FLAGS) $<

version.c: version.c.sh
	@/bin/sh ./version.c.sh

# --- tests (see tests/ and README) ---
unit-test:
	$(MAKE) -C ../tests/unit test

test-boot: merc
	@bash ../tests/scripts/boot_test.sh --boot-test

test-self: merc
	@bash ../tests/scripts/boot_test.sh --selftest

test: merc unit-test test-boot test-self
	@bash ../tests/scripts/check_logs.sh
	@echo "src make test: OK (for full suite including pytest: bash ../tests/scripts/run_all.sh)"

clean:
	rm -f $(O_FILES) merc merc-asan version.c merc.save ../area/core*

.PHONY: all build clean asan unit-test test-boot test-self test
