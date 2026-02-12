#ifndef SC_OVERLAY_H
#define SC_OVERLAY_H

#include "common.h"
#include <SDL2/SDL.h>
#include "util/vector.h"
#include "util/thread.h"

enum sc_overlay_type {
    SC_OVERLAY_TYPE_LINE,
    SC_OVERLAY_TYPE_RECT,
    SC_OVERLAY_TYPE_CIRCLE,
    SC_OVERLAY_TYPE_CROSS,
    SC_OVERLAY_TYPE_TEXT,
};

struct sc_overlay_item {
    enum sc_overlay_type type;
    union {
        struct {
            int x1, y1, x2, y2;
        } line;
        struct {
            int x, y, w, h;
        } rect;
        struct {
            int x, y, r;
        } circle;
        struct {
            int x, y, size;
        } cross;
        struct {
            int x, y, size;
            char *text;
        } text;
    };
    uint8_t r, g, b, a;
    uint8_t thickness;
    bool filled;
};

struct sc_overlay {
    struct SC_VECTOR(struct sc_overlay_item) items;
    sc_mutex mutex;
};

bool
sc_overlay_init(struct sc_overlay *overlay);

void
sc_overlay_destroy(struct sc_overlay *overlay);

void
sc_overlay_add(struct sc_overlay *overlay, const struct sc_overlay_item *item);

void
sc_overlay_clear(struct sc_overlay *overlay);

void
sc_overlay_render(struct sc_overlay *overlay, SDL_Renderer *renderer,
                  const SDL_Rect *rect);

#endif
