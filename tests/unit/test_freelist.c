/*
 * Unit tests for freelist free-order patterns (GET_FREE / PUT_FREE style)
 * without linking the full MUD.
 *
 * Mirrors the note/message leak regressions: always release owned strings
 * before putting a block on the freelist.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

typedef unsigned char bool;
#ifndef TRUE
# define TRUE 1
#endif
#ifndef FALSE
# define FALSE 0
#endif

typedef struct item_type ITEM;

struct item_type {
    bool is_free;
    ITEM *next;
    char *from;
    char *to;
    char *subject;
    char *text;
};

static ITEM *item_free = NULL;
static int failures = 0;
static int alloc_count = 0;     /* live strdup-owned strings */

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

static char *
xstrdup(const char *s)
{
    char *p;

    if (!s)
        return NULL;
    p = malloc(strlen(s) + 1);
    if (!p) {
        perror("malloc");
        exit(2);
    }
    strcpy(p, s);
    alloc_count++;
    return p;
}

static void
xfree_string(char *s)
{
    if (!s)
        return;
    free(s);
    alloc_count--;
}

/* Same shape as lists.h GET_FREE / PUT_FREE */
#define GET_FREE(item, freelist) \
do { \
  if ( !(freelist) ) \
    (item) = calloc(1, sizeof(*(item))); \
  else { \
    if ( !(freelist)->is_free ) { \
      fprintf(stderr, "GET_FREE: freelist head is NOT FREE\n"); \
      exit(3); \
    } \
    (item) = (freelist); \
    (freelist) = (item)->next; \
    memset((item), 0, sizeof(*(item))); \
  } \
} while(0)

#define PUT_FREE(item, freelist) \
do { \
  if ( (item)->is_free ) { \
    fprintf(stderr, "PUT_FREE: item is ALREADY FREE\n"); \
    exit(3); \
  } \
  (item)->next = (freelist); \
  (item)->is_free = TRUE; \
  (freelist) = (item); \
} while(0)

static void
free_item_correct(ITEM *item)
{
    xfree_string(item->from);
    xfree_string(item->to);
    xfree_string(item->subject);
    xfree_string(item->text);
    item->from = item->to = item->subject = item->text = NULL;
    PUT_FREE(item, item_free);
}

static void
test_correct_order_no_leak(void)
{
    ITEM *n;
    int start = alloc_count;

    GET_FREE(n, item_free);
    n->from = xstrdup("From");
    n->to = xstrdup("To");
    n->subject = xstrdup("Subj");
    n->text = xstrdup("Body");
    free_item_correct(n);

    GET_FREE(n, item_free);     /* recycle */
    n->from = xstrdup("From2");
    n->to = xstrdup("To2");
    n->subject = xstrdup("Subj2");
    n->text = xstrdup("Body2");
    free_item_correct(n);

    expect(alloc_count == start, "correct free order leaves no string leaks");
    expect(item_free != NULL, "item returned to freelist");
}

static void
test_double_put_free_detected(void)
{
    ITEM *n;
    int caught = 0;

    GET_FREE(n, item_free);
    n->from = xstrdup("x");
    free_item_correct(n);

    /* Second PUT_FREE must trip is_free guard — we simulate detection */
    if (item_free && item_free->is_free)
        caught = 1;
    expect(caught, "freelist entry marked is_free after PUT_FREE");
}

static void
test_reset_like_helper(void)
{
    /* free_reset pattern: free notes/auto_message then PUT_FREE */
    typedef struct {
        bool is_free;
        void *next;
        char *notes;
        char *auto_message;
    } RESET;

    RESET *freelist = NULL;
    RESET *r;
    int start = alloc_count;

    r = calloc(1, sizeof(*r));
    r->notes = xstrdup("notes here");
    r->auto_message = xstrdup("auto here");

    xfree_string(r->notes);
    xfree_string(r->auto_message);
    r->notes = r->auto_message = NULL;
    r->next = freelist;
    r->is_free = TRUE;
    freelist = r;

    expect(alloc_count == start, "reset-like free helper no leak");
    free(freelist);
}

int
main(void)
{
    printf("test_freelist:\n");
    test_correct_order_no_leak();
    test_double_put_free_detected();
    test_reset_like_helper();

    /* drain freelist */
    while (item_free) {
        ITEM *n = item_free;
        item_free = n->next;
        free(n);
    }

    if (failures) {
        fprintf(stderr, "test_freelist: %d failure(s)\n", failures);
        return 1;
    }
    printf("test_freelist: ALL PASSED\n");
    return 0;
}
