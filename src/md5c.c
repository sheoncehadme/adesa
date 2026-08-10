/*
 * This is an OpenSSL-compatible implementation of the RSA Data Security,
 * Inc. MD5 Message-Digest Algorithm.
 *
 * Written by Solar Designer <solar@openwall.com> in 2001, and placed in
 * the public domain.
 *
 * This differs from Colin Plumb's older public domain implementation in
 * that no 32-bit integer data type is required, there's no compile-time
 * endianness configuration, and the function prototypes match OpenSSL's.
 * The primary goals are portability and ease of use.
 *
 * This implementation is meant to be fast, but not as fast as possible.
 * Some known optimizations are not included to reduce source code size
 * and avoid compile-time configuration.
 */

#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#include "md5.h"

/* Local bool so this unit does not depend on merc.h */
#ifndef TRUE
# define TRUE  1
# define FALSE 0
#endif
typedef unsigned char bool;

#if !defined(NOCRYPT)
extern char *crypt(const char *key, const char *salt);
#endif


IDSTRING(rcsid, "$Id: md5c.c,v 1.3 2003/02/09 18:48:34 dave Exp $");

/*
 * The basic MD5 functions.
 *
 * F is optimized compared to its RFC 1321 definition just like in Colin
 * Plumb's implementation.
 */
#define F(x, y, z)            ((z) ^ ((x) & ((y) ^ (z))))
#define G(x, y, z)            ((y) ^ ((z) & ((x) ^ (y))))
#define H(x, y, z)            ((x) ^ (y) ^ (z))
#define I(x, y, z)            ((y) ^ ((x) | ~(z)))

/*
 * The MD5 transformation for all four rounds.
 */
#define STEP(f, a, b, c, d, x, t, s) \
    (a) += f((b), (c), (d)) + (x) + (t); \
    (a) = (((a) << (s)) | (((a) & 0xffffffff) >> (32 - (s)))); \
    (a) += (b);

/*
 * SET reads 4 input bytes in little-endian byte order and stores them
 * in a properly aligned word in host byte order.
 *
 * The check for little-endian architectures which tolerate unaligned
 * memory accesses is just an optimization.  Nothing will break if it
 * doesn't work.
 */
#if defined(__i386__) || defined(__vax__)
#define SET(n) \
    (*(MD5_u32plus *)&ptr[(n) * 4])
#define GET(n) \
    SET(n)
#else
#define SET(n) \
    (ctx->block[(n)] = \
    (MD5_u32plus)ptr[(n) * 4] | \
    ((MD5_u32plus)ptr[(n) * 4 + 1] << 8) | \
    ((MD5_u32plus)ptr[(n) * 4 + 2] << 16) | \
    ((MD5_u32plus)ptr[(n) * 4 + 3] << 24))
#define GET(n) \
    (ctx->block[(n)])
#endif

/*
 * This processes one or more 64-byte data blocks, but does NOT update
 * the bit counters.  There're no alignment requirements.
 */
static void        *
body(MD5_CTX * ctx, void *data, unsigned long size)
{
    unsigned char      *ptr;
    MD5_u32plus         a, b, c, d;
    MD5_u32plus         saved_a, saved_b, saved_c, saved_d;

    ptr = data;

    a = ctx->a;
    b = ctx->b;
    c = ctx->c;
    d = ctx->d;

    do {
        saved_a = a;
        saved_b = b;
        saved_c = c;
        saved_d = d;

        /* Round 1 */
        STEP(F, a, b, c, d, SET(0), 0xd76aa478, 7)
            STEP(F, d, a, b, c, SET(1), 0xe8c7b756, 12)
            STEP(F, c, d, a, b, SET(2), 0x242070db, 17)
            STEP(F, b, c, d, a, SET(3), 0xc1bdceee, 22)
            STEP(F, a, b, c, d, SET(4), 0xf57c0faf, 7)
            STEP(F, d, a, b, c, SET(5), 0x4787c62a, 12)
            STEP(F, c, d, a, b, SET(6), 0xa8304613, 17)
            STEP(F, b, c, d, a, SET(7), 0xfd469501, 22)
            STEP(F, a, b, c, d, SET(8), 0x698098d8, 7)
            STEP(F, d, a, b, c, SET(9), 0x8b44f7af, 12)
            STEP(F, c, d, a, b, SET(10), 0xffff5bb1, 17)
            STEP(F, b, c, d, a, SET(11), 0x895cd7be, 22)
            STEP(F, a, b, c, d, SET(12), 0x6b901122, 7)
            STEP(F, d, a, b, c, SET(13), 0xfd987193, 12)
            STEP(F, c, d, a, b, SET(14), 0xa679438e, 17)
            STEP(F, b, c, d, a, SET(15), 0x49b40821, 22)

            /* Round 2 */
            STEP(G, a, b, c, d, GET(1), 0xf61e2562, 5)
            STEP(G, d, a, b, c, GET(6), 0xc040b340, 9)
            STEP(G, c, d, a, b, GET(11), 0x265e5a51, 14)
            STEP(G, b, c, d, a, GET(0), 0xe9b6c7aa, 20)
            STEP(G, a, b, c, d, GET(5), 0xd62f105d, 5)
            STEP(G, d, a, b, c, GET(10), 0x02441453, 9)
            STEP(G, c, d, a, b, GET(15), 0xd8a1e681, 14)
            STEP(G, b, c, d, a, GET(4), 0xe7d3fbc8, 20)
            STEP(G, a, b, c, d, GET(9), 0x21e1cde6, 5)
            STEP(G, d, a, b, c, GET(14), 0xc33707d6, 9)
            STEP(G, c, d, a, b, GET(3), 0xf4d50d87, 14)
            STEP(G, b, c, d, a, GET(8), 0x455a14ed, 20)
            STEP(G, a, b, c, d, GET(13), 0xa9e3e905, 5)
            STEP(G, d, a, b, c, GET(2), 0xfcefa3f8, 9)
            STEP(G, c, d, a, b, GET(7), 0x676f02d9, 14)
            STEP(G, b, c, d, a, GET(12), 0x8d2a4c8a, 20)

            /* Round 3 */
            STEP(H, a, b, c, d, GET(5), 0xfffa3942, 4)
            STEP(H, d, a, b, c, GET(8), 0x8771f681, 11)
            STEP(H, c, d, a, b, GET(11), 0x6d9d6122, 16)
            STEP(H, b, c, d, a, GET(14), 0xfde5380c, 23)
            STEP(H, a, b, c, d, GET(1), 0xa4beea44, 4)
            STEP(H, d, a, b, c, GET(4), 0x4bdecfa9, 11)
            STEP(H, c, d, a, b, GET(7), 0xf6bb4b60, 16)
            STEP(H, b, c, d, a, GET(10), 0xbebfbc70, 23)
            STEP(H, a, b, c, d, GET(13), 0x289b7ec6, 4)
            STEP(H, d, a, b, c, GET(0), 0xeaa127fa, 11)
            STEP(H, c, d, a, b, GET(3), 0xd4ef3085, 16)
            STEP(H, b, c, d, a, GET(6), 0x04881d05, 23)
            STEP(H, a, b, c, d, GET(9), 0xd9d4d039, 4)
            STEP(H, d, a, b, c, GET(12), 0xe6db99e5, 11)
            STEP(H, c, d, a, b, GET(15), 0x1fa27cf8, 16)
            STEP(H, b, c, d, a, GET(2), 0xc4ac5665, 23)

            /* Round 4 */
            STEP(I, a, b, c, d, GET(0), 0xf4292244, 6)
            STEP(I, d, a, b, c, GET(7), 0x432aff97, 10)
            STEP(I, c, d, a, b, GET(14), 0xab9423a7, 15)
            STEP(I, b, c, d, a, GET(5), 0xfc93a039, 21)
            STEP(I, a, b, c, d, GET(12), 0x655b59c3, 6)
            STEP(I, d, a, b, c, GET(3), 0x8f0ccc92, 10)
            STEP(I, c, d, a, b, GET(10), 0xffeff47d, 15)
            STEP(I, b, c, d, a, GET(1), 0x85845dd1, 21)
            STEP(I, a, b, c, d, GET(8), 0x6fa87e4f, 6)
            STEP(I, d, a, b, c, GET(15), 0xfe2ce6e0, 10)
            STEP(I, c, d, a, b, GET(6), 0xa3014314, 15)
            STEP(I, b, c, d, a, GET(13), 0x4e0811a1, 21)
            STEP(I, a, b, c, d, GET(4), 0xf7537e82, 6)
            STEP(I, d, a, b, c, GET(11), 0xbd3af235, 10)
            STEP(I, c, d, a, b, GET(2), 0x2ad7d2bb, 15)
            STEP(I, b, c, d, a, GET(9), 0xeb86d391, 21)

            a += saved_a;
        b += saved_b;
        c += saved_c;
        d += saved_d;

        ptr += 64;
    } while (size -= 64);

    ctx->a = a;
    ctx->b = b;
    ctx->c = c;
    ctx->d = d;

    return ptr;
}

void
MD5_Init(MD5_CTX * ctx)
{
    ctx->a = 0x67452301;
    ctx->b = 0xefcdab89;
    ctx->c = 0x98badcfe;
    ctx->d = 0x10325476;

    ctx->lo = 0;
    ctx->hi = 0;
}

void
MD5_Update(MD5_CTX * ctx, void *data, unsigned long size)
{
    MD5_u32plus         saved_lo;
    unsigned long       used, free;

    saved_lo = ctx->lo;
    if ((ctx->lo = (saved_lo + size) & 0x1fffffff) < saved_lo)
        ctx->hi++;
    ctx->hi += size >> 29;

    used = saved_lo & 0x3f;

    if (used) {
        free = 64 - used;

        if (size < free) {
            memcpy(&ctx->buffer[used], data, size);
            return;
        }

        memcpy(&ctx->buffer[used], data, free);
        data = (unsigned char *) data + free;
        size -= free;
        body(ctx, ctx->buffer, 64);
    }

    if (size >= 64) {
        data = body(ctx, data, size & ~(unsigned long) 0x3f);
        size &= 0x3f;
    }

    memcpy(ctx->buffer, data, size);
}

void
MD5_Final(unsigned char *result, MD5_CTX * ctx)
{
    unsigned long       used, free;

    used = ctx->lo & 0x3f;

    ctx->buffer[used++] = 0x80;

    free = 64 - used;

    if (free < 8) {
        memset(&ctx->buffer[used], 0, free);
        body(ctx, ctx->buffer, 64);
        used = 0;
        free = 64;
    }

    memset(&ctx->buffer[used], 0, free - 8);

    ctx->lo <<= 3;
    ctx->buffer[56] = ctx->lo;
    ctx->buffer[57] = ctx->lo >> 8;
    ctx->buffer[58] = ctx->lo >> 16;
    ctx->buffer[59] = ctx->lo >> 24;
    ctx->buffer[60] = ctx->hi;
    ctx->buffer[61] = ctx->hi >> 8;
    ctx->buffer[62] = ctx->hi >> 16;
    ctx->buffer[63] = ctx->hi >> 24;

    body(ctx, ctx->buffer, 64);

    result[0] = ctx->a;
    result[1] = ctx->a >> 8;
    result[2] = ctx->a >> 16;
    result[3] = ctx->a >> 24;
    result[4] = ctx->b;
    result[5] = ctx->b >> 8;
    result[6] = ctx->b >> 16;
    result[7] = ctx->b >> 24;
    result[8] = ctx->c;
    result[9] = ctx->c >> 8;
    result[10] = ctx->c >> 16;
    result[11] = ctx->c >> 24;
    result[12] = ctx->d;
    result[13] = ctx->d >> 8;
    result[14] = ctx->d >> 16;
    result[15] = ctx->d >> 24;

    memset(ctx, 0, sizeof(*ctx));
}

char               *
md5string(char *text, char *out)
{
    MD5_CTX             context;
    unsigned char       digest[16];
    int                 i;

    MD5_Init(&context);
    MD5_Update(&context, (unsigned char *) text, strlen(text));
    MD5_Final(digest, &context);

    for (i = 0; i < 16; i++)
        sprintf(out + (i * 2), "%.2x", digest[i]);

    return out;
}

/*
 * Salted, iterated password storage.
 *
 * Format:  $s$<16 hex salt>$<32 hex md5>
 * Algorithm: dig0 = MD5(salt || plain); dig_{n+1} = MD5(dig_n || salt || plain)
 * for PWD_ROUNDS iterations (constant below).
 *
 * Still not Argon2/bcrypt, but far harder than unsalted MD5 for offline attack,
 * with no new library dependency. Legacy DES (crypt) and plain 32-char MD5
 * continue to verify; successful login should re-hash to $s$.
 */
#define PWD_SALT_HEX_LEN  16
#define PWD_ROUNDS        5000
#define PWD_HASH_BUF      64    /* $s$ + 16 + $ + 32 + NUL */

static void
pwd_digest(const char *plain, const char *salt16, char *out33)
{
    char                buf[1024];
    char                dig[33];
    int                 r;
    size_t              plen, slen;

    if (!plain)
        plain = "";
    if (!salt16)
        salt16 = "0000000000000000";

    plen = strlen(plain);
    slen = strlen(salt16);
    if (slen > PWD_SALT_HEX_LEN)
        slen = PWD_SALT_HEX_LEN;

    if (slen + plen + 1 >= sizeof(buf))
        plen = sizeof(buf) - slen - 1;

    memcpy(buf, salt16, slen);
    memcpy(buf + slen, plain, plen);
    buf[slen + plen] = '\0';
    md5string(buf, dig);

    for (r = 1; r < PWD_ROUNDS; r++) {
        /* dig (32) + salt + plain */
        if (32 + slen + plen + 1 >= sizeof(buf))
            break;
        memcpy(buf, dig, 32);
        memcpy(buf + 32, salt16, slen);
        memcpy(buf + 32 + slen, plain, plen);
        buf[32 + slen + plen] = '\0';
        md5string(buf, dig);
    }
    memcpy(out33, dig, 33);
}

static void
pwd_random_salt(char *salt17)
{
    static unsigned long rng;
    unsigned int        i;
    unsigned char       b;
    FILE               *ur;

    /* Prefer OS entropy when available */
    ur = fopen("/dev/urandom", "rb");
    if (ur) {
        unsigned char       raw[8];

        if (fread(raw, 1, 8, ur) == 8) {
            fclose(ur);
            for (i = 0; i < 8; i++)
                sprintf(salt17 + i * 2, "%02x", raw[i]);
            salt17[16] = '\0';
            return;
        }
        fclose(ur);
    }

    if (rng == 0)
        rng = (unsigned long) time(NULL) ^ (unsigned long) getpid() ^ 0xA5A5u;
    for (i = 0; i < 8; i++) {
        rng = rng * 1103515245UL + 12345UL;
        b = (unsigned char) ((rng >> 16) & 0xFF);
        sprintf(salt17 + i * 2, "%02x", b);
    }
    salt17[16] = '\0';
}

char               *
hash_password(const char *plain, char *out, int outlen)
{
    char                salt[PWD_SALT_HEX_LEN + 1];
    char                dig[33];

    if (!out || outlen < PWD_HASH_BUF) {
        if (out && outlen > 0)
            out[0] = '\0';
        return out;
    }

    pwd_random_salt(salt);
    pwd_digest(plain, salt, dig);
    sprintf(out, "$s$%s$%s", salt, dig);
    return out;
}

bool
check_password(const char *plain, const char *stored)
{
    char                dig[33];
    char                salt[PWD_SALT_HEX_LEN + 1];
    const char         *p;
    int                 i;

    if (!plain || !stored || stored[0] == '\0')
        return FALSE;

#ifdef NOCRYPT
    return !strcmp(plain, stored);
#else
    /* New salted format: $s$<16 hex>$<32 hex> */
    if (stored[0] == '$' && stored[1] == 's' && stored[2] == '$') {
        p = stored + 3;
        for (i = 0; i < PWD_SALT_HEX_LEN; i++) {
            if (!p[i] || p[i] == '$')
                return FALSE;
            salt[i] = p[i];
        }
        salt[PWD_SALT_HEX_LEN] = '\0';
        if (p[PWD_SALT_HEX_LEN] != '$')
            return FALSE;
        p += PWD_SALT_HEX_LEN + 1;
        if (strlen(p) != 32)
            return FALSE;
        pwd_digest(plain, salt, dig);
        return strcmp(dig, p) == 0;
    }

    /* Unsalted MD5 (legacy 32 hex chars) */
    if (strlen(stored) == 32) {
        md5string((char *) plain, dig);
        return strcmp(dig, stored) == 0;
    }

    /* Ancient DES crypt() storage */
    {
        char               *crypted;

        crypted = crypt(plain, stored);
        if (!crypted)
            return FALSE;
        return strcmp(crypted, stored) == 0;
    }
#endif
}

bool
password_needs_rehash(const char *stored)
{
    if (!stored || !*stored)
        return TRUE;
    if (stored[0] == '$' && stored[1] == 's' && stored[2] == '$')
        return FALSE;
    return TRUE;                /* DES or plain MD5 */
}
