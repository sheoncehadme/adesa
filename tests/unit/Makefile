# Pure unit tests (no full world boot).
# Run from repo root: make -C tests/unit
# Or: make unit-test (from src/)

ROOT    := ../..
SRC     := $(ROOT)/src
CC      ?= cc
UNAME_S := $(shell uname -s 2>/dev/null || echo Unknown)

C_FLAGS = -O2 -g -Wall -std=gnu89 -I$(SRC)
ifeq ($(UNAME_S),Darwin)
  C_FLAGS += -D_DARWIN_C_SOURCE
  # crypt(3) is in libc on macOS
  CRYPT_LIB =
else
  C_FLAGS += -D_DEFAULT_SOURCE -D_BSD_SOURCE
  # md5c.o pulls in check_password() -> crypt(); Linux needs libxcrypt
  CRYPT_LIB = -lcrypt
endif

.PHONY: all test clean

all: test_ssm test_freelist test_md5

# Rebuild ssm.o in src if needed, then link
$(SRC)/ssm.o:
	$(MAKE) -C $(SRC) ssm.o

$(SRC)/md5c.o:
	$(MAKE) -C $(SRC) md5c.o

stubs.o: stubs.c
	$(CC) $(C_FLAGS) -c stubs.c -o stubs.o

test_ssm: test_ssm.c stubs.o $(SRC)/ssm.o
	$(CC) $(C_FLAGS) -o test_ssm test_ssm.c stubs.o $(SRC)/ssm.o

test_freelist: test_freelist.c
	$(CC) $(C_FLAGS) -o test_freelist test_freelist.c

test_md5: test_md5.c $(SRC)/md5c.o
	$(CC) $(C_FLAGS) -o test_md5 test_md5.c $(SRC)/md5c.o $(CRYPT_LIB)

test: all
	@echo "=== unit: test_ssm ==="
	./test_ssm
	@echo "=== unit: test_freelist ==="
	./test_freelist
	@echo "=== unit: test_md5 ==="
	./test_md5
	@echo "=== unit tests: ALL PASSED ==="

clean:
	rm -f test_ssm test_freelist test_md5 stubs.o
