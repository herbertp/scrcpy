#ifndef SC_SHM_SINK_H
#define SC_SHM_SINK_H

#include "common.h"

#include <stdbool.h>
#include <stdint.h>
#include <libavcodec/avcodec.h>

#include "trait/frame_sink.h"
#include "util/thread.h"

#define SC_SHM_SLOTS 3

struct sc_shm_slot {
    uint32_t width;
    uint32_t height;
    uint32_t format;
    uint32_t size;
    uint64_t pts;
    uint32_t sequence;
    uint32_t padding; // Align data to 4k
};

struct sc_shm_header {
    uint32_t latest_index;
    uint32_t num_slots;
    uint32_t slot_size; // Includes slot header and data, aligned to 4k
    uint8_t padding[4084]; // Ensure header itself is 4k
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
