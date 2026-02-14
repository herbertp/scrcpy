
import socket
import struct
import sys
from multiprocessing import shared_memory, resource_tracker

def save_ppm(width, height, yuv_data, filename):
    y_size = width * height
    uv_w, uv_h = (width + 1) // 2, (height + 1) // 2
    uv_size = uv_w * uv_h

    y_plane = yuv_data[:y_size]
    u_plane = yuv_data[y_size:y_size + uv_size]
    v_plane = yuv_data[y_size + uv_size:y_size + 2*uv_size]

    rgb = bytearray(width * height * 3)
    for j in range(height):
        uv_j = j // 2
        y_offset = j * width
        rgb_offset = j * width * 3
        for i in range(width):
            uv_i = i // 2
            y = y_plane[y_offset + i]
            u = u_plane[uv_j * uv_w + uv_i]
            v = v_plane[uv_j * uv_w + uv_i]

            c = y - 16
            d = u - 128
            e = v - 128

            r = (298 * c + 409 * e + 128) >> 8
            g = (298 * c - 100 * d - 208 * e + 128) >> 8
            b = (298 * c + 516 * d + 128) >> 8

            idx = rgb_offset + i * 3
            rgb[idx] = max(0, min(255, r))
            rgb[idx+1] = max(0, min(255, g))
            rgb[idx+2] = max(0, min(255, b))

    with open(filename, "wb") as f:
        f.write(f"P6\n{width} {height}\n255\n".encode())
        f.write(rgb)
    print(f"Saved {filename}")

def main():
    shm_name = sys.argv[1] if len(sys.argv) > 1 else "android"
    name_for_py = shm_name if not shm_name.startswith("/") else shm_name[1:]

    shm = shared_memory.SharedMemory(name=name_for_py)
    resource_tracker.unregister(shm._name, "shared_memory")

    buf = shm.buf
    latest_index, num_slots, slot_data_size = struct.unpack("III", bytes(buf[:12]))
    meta_offset = 16 + latest_index * 32
    width, height, fmt, data_size = struct.unpack("IIII", bytes(buf[meta_offset:meta_offset + 16]))

    data_offset = 4096 + latest_index * slot_data_size
    save_ppm(width, height, bytes(buf[data_offset:data_offset+data_size]), "snapshot.ppm")

    shm.close()

if __name__ == "__main__":
    main()
