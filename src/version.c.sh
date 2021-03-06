#!/bin/sh

if test -r version.c.last
then
        generation=`sed -n 's/^int build_no = \(.*\);/\1/p' < version.c.last`
if test ! "$generation" ; then generation=0; fi
else
        generation=0
fi

generation=`expr $generation + 1`

creation=`date "+%s"`

cat >version.c <<!SUB!THIS!
/*
 * This file is automatically generated by version.c.sh.
 * Any changes made will NOT save.
 */

#include <time.h>

int build_no = $generation;
time_t creation_time = $creation;
!SUB!THIS!
