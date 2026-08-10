/*
 * Unit tests for the Shared String Manager (ssm.c).
 *
 * Build via tests/unit/Makefile (links ssm.o + stubs).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <time.h>
#include <sys/types.h>

#include "merc.h"
#include "ssm.h"

void init_string_space(void);
extern bool fBootDb;

static int failures = 0;

static void
expect(int cond, const char *msg)
{
    if (!cond) {
        fprintf(stderr, "FAIL: %s\n", msg);
        failures++;
    }
    else {
        printf("  ok: %s\n", msg);
    }
}

static void
test_empty_string(void)
{
    char *e1, *e2;

    e1 = str_dup("");
    e2 = str_dup(NULL);
    expect(e1 == &str_empty[0], "str_dup(\"\") returns str_empty");
    expect(e2 == &str_empty[0], "str_dup(NULL) returns str_empty");
    free_string(e1);
    free_string(e2);
    free_string(NULL);
    expect(1, "free_string empty/NULL is no-op");
}

static void
test_share_and_free(void)
{
    long before, mid, after;
    char *a, *b, *c;

    before = nAllocString;

    /*
     * Runtime SSM only shares when str_dup is given a pointer already in
     * string_space (usage++). Two equal C literals are separate allocs.
     * Boot-time content crunching uses temp_string_hash (not tested here).
     */
    a = str_dup("unit-test-shared-alpha");
    b = str_dup(a);             /* re-dup of heap pointer */
    expect(a != NULL && b != NULL, "str_dup non-null");
    expect(a == b, "re-dup of SSM pointer shares storage");
    mid = nAllocString;
    expect(mid == before + 1, "one SSM alloc when re-duping pointer");

    free_string(a);
    expect(nAllocString == mid, "first free keeps block (usage>0)");
    free_string(b);
    after = nAllocString;
    expect(after == before, "second free releases block");

    c = str_dup("unit-test-shared-alpha");
    expect(c != NULL, "re-dup after free works");
    free_string(c);
    expect(nAllocString == before, "cleanup after re-dup");
}

static void
test_distinct_strings(void)
{
    long before;
    char *a, *b;

    before = nAllocString;
    a = str_dup("unit-test-one");
    b = str_dup("unit-test-two");
    expect(a != b, "distinct strings differ");
    expect(nAllocString == before + 2, "two distinct allocs");
    free_string(a);
    free_string(b);
    expect(nAllocString == before, "both freed");
}

static void
test_defrag_callable(void)
{
    int merges;

    merges = defrag_heap();
    expect(merges >= 0, "defrag_heap returns non-negative");
}

int
main(void)
{
    printf("test_ssm:\n");
    init_string_space();
    fBootDb = FALSE;

    test_empty_string();
    test_share_and_free();
    test_distinct_strings();
    test_defrag_callable();

    if (failures) {
        fprintf(stderr, "test_ssm: %d failure(s)\n", failures);
        return 1;
    }
    printf("test_ssm: ALL PASSED\n");
    return 0;
}
