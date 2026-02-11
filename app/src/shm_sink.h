#ifndef SC_SHM_SINK_H
#define SC_SHM_SINK_H

#include "common.h"

#include <stdbool.h>
#include <stdint.h>
#include <libavcodec/avcodec.h>

#include "trait/frame_sink.h"
#include "util/thread.h"

struct sc_shm_header {
    uint32_t width;
    uint32_t height;
    uint32_t format;
    uint32_t size;
    uint64_t pts;
    uint32_t sequence;
};

struct sc_shm_sink {
    struct sc_frame_sink frame_sink;

    char *shm_name;
    int shm_fd;
    void *shm_ptr;
    size_t shm_size;

    sc_mutex mutex;
    uint32_t sequence;
};

bool
sc_shm_sink_init(struct sc_shm_sink *shm, const char *shm_name);

void
sc_shm_sink_destroy(struct sc_shm_sink *shm);

#endif
