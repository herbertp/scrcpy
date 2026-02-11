#ifndef SC_API_SERVER_H
#define SC_API_SERVER_H

#include "common.h"
#include <stdbool.h>
#include "controller.h"
#include "overlay.h"
#include "util/thread.h"

struct sc_api_server {
    char *socket_path;
    struct sc_controller *controller;
    struct sc_overlay *overlay;
    struct sc_screen *screen;

    sc_thread thread;
    bool stopped;
};

bool
sc_api_server_init(struct sc_api_server *api, const char *socket_path,
                   struct sc_controller *controller,
                   struct sc_overlay *overlay,
                   struct sc_screen *screen);

void
sc_api_server_destroy(struct sc_api_server *api);

bool
sc_api_server_start(struct sc_api_server *api);

void
sc_api_server_stop(struct sc_api_server *api);

#endif
