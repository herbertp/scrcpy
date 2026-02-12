#include "shm_sink.h"

#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
#include <libavutil/imgutils.h>
#include "util/log.h"

#define DOWNCAST(SINK) container_of(SINK, struct sc_shm_sink, frame_sink)

#define PAGE_SIZE 4096
#define ALIGN_UP(s, a) (((s) + (a) - 1) & ~((a) - 1))

static bool
sc_shm_sink_open(struct sc_frame_sink *sink, const AVCodecContext *ctx) {
    (void) sink;
    (void) ctx;
    return true;
}

static void
sc_shm_sink_close(struct sc_frame_sink *sink) {
    (void) sink;
}

static bool
sc_shm_sink_push(struct sc_frame_sink *sink, const AVFrame *frame) {
    struct sc_shm_sink *shm = DOWNCAST(sink);

    int data_size = av_image_get_buffer_size(frame->format, frame->width,
                                            frame->height, 1);
    if (data_size < 0) {
        LOGE("Could not get image buffer size");
        return false;
    }

    // slot_data_size is aligned to 4k
    size_t aligned_slot_size = ALIGN_UP(data_size, PAGE_SIZE);
    // Page 0 for header, then slots
    size_t total_size = PAGE_SIZE + aligned_slot_size * SC_SHM_SLOTS;

    sc_mutex_lock(&shm->mutex);

    if (!shm->shm_ptr || shm->shm_size < total_size) {
        if (shm->shm_ptr) {
            munmap(shm->shm_ptr, shm->shm_size);
        }
        if (ftruncate(shm->shm_fd, total_size) == -1) {
            LOGE("Could not ftruncate SHM");
            sc_mutex_unlock(&shm->mutex);
            return false;
        }
        shm->shm_ptr = mmap(NULL, total_size, PROT_READ | PROT_WRITE,
                            MAP_SHARED, shm->shm_fd, 0);
        if (shm->shm_ptr == MAP_FAILED) {
            LOGE("Could not mmap SHM");
            shm->shm_ptr = NULL;
            sc_mutex_unlock(&shm->mutex);
            return false;
        }
        shm->shm_size = total_size;

        // Initialize header
        struct sc_shm_header *h = shm->shm_ptr;
        h->num_slots = SC_SHM_SLOTS;
        h->slot_data_size = aligned_slot_size;
        h->latest_index = 0;
        // Mark all slots as empty initially
        for (int i=0; i < SC_SHM_SLOTS; ++i) {
            h->slots[i].sequence = 0;
        }
    }

    struct sc_shm_header *h = shm->shm_ptr;
    // Choose next slot (round robin)
    uint32_t next_index = (h->latest_index + 1) % SC_SHM_SLOTS;

    // Slot data starts at Page 1 + index * aligned_slot_size
    uint8_t *dst = (uint8_t *)shm->shm_ptr + PAGE_SIZE + next_index * aligned_slot_size;

    av_image_copy_to_buffer(dst, data_size, (const uint8_t *const *)frame->data,
                            frame->linesize, frame->format, frame->width,
                            frame->height, 1);

    // Update slot metadata in Page 0
    struct sc_shm_slot_meta *meta = &h->slots[next_index];
    meta->width = frame->width;
    meta->height = frame->height;
    meta->format = frame->format;
    meta->size = data_size;
    meta->pts = frame->pts;
    meta->sequence = ++shm->sequence;

    // Update latest index last
    h->latest_index = next_index;

    sc_mutex_unlock(&shm->mutex);

    return true;
}

static const struct sc_frame_sink_ops ops = {
    .open = sc_shm_sink_open,
    .close = sc_shm_sink_close,
    .push = sc_shm_sink_push,
};

bool
sc_shm_sink_init(struct sc_shm_sink *shm, const char *shm_name) {
    shm->shm_name = strdup(shm_name);
    if (!shm->shm_name) {
        LOG_OOM();
        return false;
    }

    const char *actual_name = shm_name;
    char *allocated_name = NULL;
    if (shm_name[0] != '/') {
        size_t len = strlen(shm_name) + 2;
        allocated_name = malloc(len);
        if (!allocated_name) {
            LOG_OOM();
            free(shm->shm_name);
            return false;
        }
        snprintf(allocated_name, len, "/%s", shm_name);
        actual_name = allocated_name;
    }

    shm->shm_fd = shm_open(actual_name, O_RDWR | O_CREAT | O_TRUNC, 0666);
    if (shm->shm_fd == -1) {
        LOGE("Could not open SHM: %s (errno=%d)", actual_name, errno);
        free(allocated_name);
        free(shm->shm_name);
        return false;
    }
    free(allocated_name);

    shm->shm_ptr = NULL;
    shm->shm_size = 0;
    shm->sequence = 0;
    bool ok = sc_mutex_init(&shm->mutex);
    if (!ok) {
        close(shm->shm_fd);
        free(shm->shm_name);
        return false;
    }

    shm->frame_sink.ops = &ops;

    return true;
}

void
sc_shm_sink_destroy(struct sc_shm_sink *shm) {
    sc_mutex_lock(&shm->mutex);
    if (shm->shm_ptr) {
        munmap(shm->shm_ptr, shm->shm_size);
    }
    if (shm->shm_fd != -1) {
        close(shm->shm_fd);
        const char *actual_name = shm->shm_name;
        char *allocated_name = NULL;
        if (shm->shm_name[0] != '/') {
            size_t len = strlen(shm->shm_name) + 2;
            allocated_name = malloc(len);
            if (allocated_name) {
                snprintf(allocated_name, len, "/%s", shm->shm_name);
                actual_name = allocated_name;
            }
        }
        shm_unlink(actual_name);
        free(allocated_name);
    }
    sc_mutex_unlock(&shm->mutex);
    sc_mutex_destroy(&shm->mutex);
    free(shm->shm_name);
}
