
import os
import sys
import time
import struct
import numpy as np
import pygame
from multiprocessing import shared_memory, resource_tracker

# YUV420P to RGB conversion using NumPy
def yuv_to_rgb(y, u, v, w, h):
    # Upsample U and V
    u = np.repeat(np.repeat(u, 2, axis=0), 2, axis=1)
    v = np.repeat(np.repeat(v, 2, axis=0), 2, axis=1)

    # Crop to match Y if needed (due to rounding)
    u = u[:h, :w]
    v = v[:h, :w]

    y = y.astype(np.float32) - 16
    u = u.astype(np.float32) - 128
    v = v.astype(np.float32) - 128

    r = (1.164 * y + 1.596 * v)
    g = (1.164 * y - 0.392 * u - 0.813 * v)
    b = (1.164 * y + 2.017 * u)

    rgb = np.stack([r, g, b], axis=-1)
    return np.clip(rgb, 0, 255).astype(np.uint8)

def main():
    shm_name = sys.argv[1] if len(sys.argv) > 1 else "android"
    scale_factor = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    name_for_py = shm_name if not shm_name.startswith("/") else shm_name[1:]

    print(f"Connecting to SHM: {shm_name}")
    try:
        shm = shared_memory.SharedMemory(name=name_for_py)
        # Prevent resource_tracker from unlinking the SHM when this process exits
        # since it's owned by scrcpy
        resource_tracker.unregister(shm._name, "shared_memory")
    except FileNotFoundError:
        print(f"Error: Shared memory '{shm_name}' not found. Is scrcpy running with --shm-name={shm_name}?")
        return

    pygame.init()

    PAGE_SIZE = 4096
    last_sequence = -1

    screen = None
    running = True

    print(f"SHM Viewer Active. Scaling factor: {scale_factor}. Press 'Q' or close window to exit.")

    # Pre-declare variables to clear them in finally block
    raw_data = None
    y_plane = None
    u_plane = None
    v_plane = None
    buf = None

    try:
        # Get a single view of the buffer to avoid repeated export increments
        buf = shm.buf
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                    running = False

            # Read Global Header
            header_data = bytes(buf[:12])
            latest_index, num_slots, slot_data_size = struct.unpack("III", header_data)

            # Read Slot Metadata
            meta_offset = 16 + latest_index * 32
            meta_data = bytes(buf[meta_offset:meta_offset + 28])
            width, height, fmt, data_size, pts, sequence = struct.unpack("IIIIQI", meta_data)

            if sequence != last_sequence and data_size > 0:
                last_sequence = sequence

                # Extract YUV planes
                data_offset = PAGE_SIZE + latest_index * slot_data_size
                raw_data = buf[data_offset:data_offset + data_size]

                y_size = width * height
                uv_w, uv_h = (width + 1) // 2, (height + 1) // 2
                uv_size = uv_w * uv_h

                y_plane = np.frombuffer(raw_data[:y_size], dtype=np.uint8).reshape((height, width))
                u_plane = np.frombuffer(raw_data[y_size:y_size+uv_size], dtype=np.uint8).reshape((uv_h, uv_w))
                v_plane = np.frombuffer(raw_data[y_size+uv_size:y_size+2*uv_size], dtype=np.uint8).reshape((uv_h, uv_w))

                rgb = yuv_to_rgb(y_plane, u_plane, v_plane, width, height)

                # Scale down
                view_w, view_h = width // scale_factor, height // scale_factor
                surface = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
                scaled_surface = pygame.transform.scale(surface, (view_w, view_h))

                if screen is None:
                    screen = pygame.display.set_mode((view_w, view_h))
                    pygame.display.set_caption(f"scrcpy SHM Viewer - {width}x{height}")

                screen.blit(scaled_surface, (0, 0))
                pygame.display.flip()

                # We can't easily clear these here as they are needed for the loop,
                # but they will be cleared in finally.

            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        # CRITICAL: Clear all references to the SHM buffer before closing it,
        # otherwise Python will raise "BufferError: cannot close exported pointers exist"
        raw_data = None
        y_plane = None
        u_plane = None
        v_plane = None
        buf = None
        pygame.quit()
        shm.close()

if __name__ == "__main__":
    main()
