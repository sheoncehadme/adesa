/*
 * Unit tests for md5c.c
 */
#include <stdio.h>
#include <string.h>
#include "md5.h"

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

/* RFC 1321 test vector: MD5("") = d41d8cd98f00b204e9800998ecf8427e */
static void
test_empty(void)
{
    MD5_CTX ctx;
    unsigned char dig[16];
    static const unsigned char expect_dig[16] = {
        0xd4, 0x1d, 0x8c, 0xd9, 0x8f, 0x00, 0xb2, 0x04,
        0xe9, 0x80, 0x09, 0x98, 0xec, 0xf8, 0x42, 0x7e
    };

    MD5_Init(&ctx);
    MD5_Update(&ctx, (void *) "", 0);
    MD5_Final(dig, &ctx);
    expect(memcmp(dig, expect_dig, 16) == 0, "MD5(\"\") RFC1321 vector");
}

/* MD5("abc") = 900150983cd24fb0d6963f7d28e17f72 */
static void
test_abc(void)
{
    MD5_CTX ctx;
    unsigned char dig[16];
    static const unsigned char expect_dig[16] = {
        0x90, 0x01, 0x50, 0x98, 0x3c, 0xd2, 0x4f, 0xb0,
        0xd6, 0x96, 0x3f, 0x7d, 0x28, 0xe1, 0x7f, 0x72
    };

    MD5_Init(&ctx);
    MD5_Update(&ctx, (void *) "abc", 3);
    MD5_Final(dig, &ctx);
    expect(memcmp(dig, expect_dig, 16) == 0, "MD5(\"abc\") RFC1321 vector");
}

int
main(void)
{
    printf("test_md5:\n");
    test_empty();
    test_abc();
    if (failures) {
        fprintf(stderr, "test_md5: %d failure(s)\n", failures);
        return 1;
    }
    printf("test_md5: ALL PASSED\n");
    return 0;
}
