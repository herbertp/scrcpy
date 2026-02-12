import socket
import json
import time
import sys
import struct
import os
from multiprocessing import shared_memory, resource_tracker

# Constants from android/keycodes.h
AKEYCODE_HOME = 3
AKEYCODE_BACK = 4

def save_ppm(width, height, yuv_data, filename):
    """Saves a YUV420P frame as a PPM file (RGB)."""
    y_size = width * height
    uv_size = (width // 2) * (height // 2)

    y_plane = yuv_data[:y_size]
    u_plane = yuv_data[y_size:y_size + uv_size]
    v_plane = yuv_data[y_size + uv_size:y_size + 2*uv_size]

    rgb = bytearray(width * height * 3)

    for j in range(height):
        for i in range(width):
            y = y_plane[j * width + i]
            u = u_plane[(j // 2) * (width // 2) + (i // 2)]
            v = v_plane[(j // 2) * (width // 2) + (i // 2)]

            c = y - 16
            d = u - 128
            e = v - 128

            r = (298 * c + 409 * e + 128) >> 8
            g = (298 * c - 100 * d - 208 * e + 128) >> 8
            b = (298 * c + 516 * d + 128) >> 8

            rgb[(j * width + i) * 3] = max(0, min(255, r))
            rgb[(j * width + i) * 3 + 1] = max(0, min(255, g))
            rgb[(j * width + i) * 3 + 2] = max(0, min(255, b))

    with open(filename, "wb") as f:
        f.write(f"P6\n{width} {height}\n255\n".encode())
        f.write(rgb)
    print(f"Saved frame to {filename}")

def main():
    shm_name = "scrcpy_shm"
    api_socket_path = "/tmp/scrcpy_api.sock"

    if len(sys.argv) > 1:
        shm_name = sys.argv[1]
    if len(sys.argv) > 2:
        api_socket_path = sys.argv[2]

    name_for_py = shm_name if not shm_name.startswith("/") else shm_name[1:]

    print(f"Connecting to SHM: {shm_name}")
    try:
        shm = shared_memory.SharedMemory(name=name_for_py)
        try:
            resource_tracker.unregister(shm._name, "shared_memory")
        except Exception as e:
            print(f"Note: Could not unregister SHM from resource tracker: {e}")
    except FileNotFoundError:
        print(f"SHM {shm_name} not found. Is scrcpy running with --shm-name={shm_name}?")
        return

    print(f"Connecting to API socket: {api_socket_path}")

    def send_cmd(cmd):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(api_socket_path)
                s.sendall(json.dumps(cmd).encode())
        except Exception as e:
            pass

    def swipe(start_x, start_y, end_x, end_y, steps=10, duration=0.2):
        send_cmd({"type": "inject_touch", "action": "down", "x": start_x, "y": start_y})
        for i in range(1, steps + 1):
            time.sleep(duration / steps)
            curr_x = start_x + (end_x - start_x) * i // steps
            curr_y = start_y + (end_y - start_y) * i // steps
            send_cmd({"type": "inject_touch", "action": "move", "x": curr_x, "y": curr_y})
        send_cmd({"type": "inject_touch", "action": "up", "x": end_x, "y": end_y})

    try:
        # Header is 4k, each slot is aligned to 4k
        PAGE_SIZE = 4096

        last_sequence = -1

        print("Starting main loop. Press Ctrl+C to stop.")

        # Test input injection
        print("Injecting HOME button...")
        send_cmd({"type": "inject_keycode", "action": "down", "keycode": AKEYCODE_HOME})
        send_cmd({"type": "inject_keycode", "action": "up", "keycode": AKEYCODE_HOME})

        time.sleep(1)

        print("Injecting swipe UP...")
        swipe(5000, 8000, 5000, 2000)

        time.sleep(1)

        print("Injecting swipe DOWN...")
        swipe(5000, 2000, 5000, 8000)

        time.sleep(1)

        print("Injecting text 'Hello Scrcpy'...")
        send_cmd({"type": "inject_text", "text": "Hello Scrcpy"})

        frame_saved = False
        start_time = time.time()
        while time.time() - start_time < 10:
            buf = shm.buf
            # Read header to find latest index
            header_data = bytes(buf[:12]) # latest_index, num_slots, slot_size
            latest_index, num_slots, slot_size = struct.unpack("III", header_data)

            # Slot header layout: width(4), height(4), format(4), size(4), pts(8), sequence(4) = 28 bytes
            slot_offset = PAGE_SIZE + latest_index * slot_size
            slot_header = bytes(buf[slot_offset:slot_offset + 28])
            width, height, fmt, data_size, pts, sequence = struct.unpack("IIIIQI", slot_header)

            if sequence != last_sequence:
                if not frame_saved and data_size > 0:
                    # Data is at 4k offset from slot start
                    data_offset = slot_offset + PAGE_SIZE
                    yuv_data = bytes(buf[data_offset:data_offset + data_size])
                    save_ppm(width, height, yuv_data, "frame.ppm")
                    frame_saved = True

                last_sequence = sequence

                send_cmd({"type": "overlay_clear"})

                # Filled background rectangle
                send_cmd({
                    "type": "overlay_add",
                    "item": {"type": "rect", "x": 500, "y": 500, "w": 9000, "h": 2000, "r": 50, "g": 50, "b": 50, "a": 180, "filled": True}
                })

                # Thick green line
                send_cmd({
                    "type": "overlay_add",
                    "item": {"type": "line", "x1": 1000, "y1": 1000, "x2": 9000, "y2": 1000, "r": 0, "g": 255, "b": 0, "a": 255, "thickness": 10}
                })

                # Better text rendering
                send_cmd({
                    "type": "overlay_add",
                    "item": {"type": "text", "x": 1000, "y": 1200, "size": 4, "text": f"BUFF: {latest_index} | SEQ: {sequence}", "r": 255, "g": 255, "b": 255, "a": 255}
                })

                # Filled red circle
                send_cmd({
                    "type": "overlay_add",
                    "item": {"type": "circle", "x": 5000, "y": 5000, "radius": 500, "r": 255, "g": 0, "b": 0, "a": 128, "filled": True}
                })

            time.sleep(0.02)

    except KeyboardInterrupt:
        pass
    finally:
        print("Cleaning up...")
        try:
            send_cmd({"type": "overlay_clear"})
        except:
            pass
        shm.close()

if __name__ == "__main__":
    main()
