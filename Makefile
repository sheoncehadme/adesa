# Top-level convenience targets for Adesa.
# Game binary still builds in src/; tests live under tests/.

.PHONY: all merc clean test unit-test test-boot test-self asan asan-smoke

all merc:
	$(MAKE) -C src

clean:
	$(MAKE) -C src clean
	$(MAKE) -C tests/unit clean

unit-test:
	$(MAKE) -C tests/unit test

test-boot:
	$(MAKE) -C src test-boot

test-self:
	$(MAKE) -C src test-self

test:
	@bash tests/scripts/run_all.sh

asan:
	$(MAKE) -C src asan

asan-smoke:
	@bash tests/scripts/run_asan_smoke.sh
