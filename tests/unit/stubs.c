/*
 * Minimal stubs so pure unit tests can link against ssm.o / md5c.o
 * without the full MUD binary.
 */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>

/* Match merc.h bool */
typedef unsigned char bool;

bool fBootDb = 0;

void
bugf(char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    fprintf(stderr, "bugf: ");
    vfprintf(stderr, fmt, args);
    fprintf(stderr, "\n");
    va_end(args);
}

void
xlogf(char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    fprintf(stderr, "xlogf: ");
    vfprintf(stderr, fmt, args);
    fprintf(stderr, "\n");
    va_end(args);
}

void
tail_chain(void)
{
}
