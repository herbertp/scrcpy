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
AKEYCODE_APP_SWITCH = 187

def save_ppm(width, height, yuv_data, filename):
    """Saves a YUV420P frame as a PPM file (RGB)."""
    # YUV420P: Y plane (W*H), then U plane (W/2 * H/2), then V plane (W/2 * H/2)
    # Handle odd dimensions correctly
    uv_width = (width + 1) // 2
    uv_height = (height + 1) // 2

    y_size = width * height
    uv_size = uv_width * uv_height
    expected_size = y_size + 2 * uv_size

    if len(yuv_data) < expected_size:
        print(f"Warning: YUV data too short ({len(yuv_data)} < {expected_size})")
        return

    y_plane = yuv_data[:y_size]
    u_plane = yuv_data[y_size:y_size + uv_size]
    v_plane = yuv_data[y_size + uv_size:y_size + 2*uv_size]

    rgb = bytearray(width * height * 3)

    # Pre-calculate UV indices for speed
    for j in range(height):
        uv_j = j // 2
        y_offset = j * width
        rgb_offset = j * width * 3
        for i in range(width):
            uv_i = i // 2

            y = y_plane[y_offset + i]
            u = u_plane[uv_j * uv_width + uv_i]
            v = v_plane[uv_j * uv_width + uv_i]

            # Integer conversion
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

    def swipe(start_x, start_y, end_x, end_y, steps=15, duration=0.3):
        send_cmd({"type": "inject_touch", "action": "down", "x": start_x, "y": start_y})
        for i in range(1, steps + 1):
            time.sleep(duration / steps)
            curr_x = start_x + (end_x - start_x) * i // steps
            curr_y = start_y + (end_y - start_y) * i // steps
            send_cmd({"type": "inject_touch", "action": "move", "x": curr_x, "y": curr_y})
        send_cmd({"type": "inject_touch", "action": "up", "x": end_x, "y": end_y})

    try:
        PAGE_SIZE = 4096

        last_sequence = -1

        print("Starting main loop. Press Ctrl+C to stop.")

        # Test input injection sequence
        print("Injecting HOME button...")
        send_cmd({"type": "inject_keycode", "action": "down", "keycode": AKEYCODE_HOME})
        send_cmd({"type": "inject_keycode", "action": "up", "keycode": AKEYCODE_HOME})
        time.sleep(1)

        print("Injecting swipe UP (Notification panel)...")
        swipe(5000, 100, 5000, 5000) # Swipe down from top to open notifications
        time.sleep(1)

        print("Injecting BACK button...")
        send_cmd({"type": "inject_keycode", "action": "down", "keycode": AKEYCODE_BACK})
        send_cmd({"type": "inject_keycode", "action": "up", "keycode": AKEYCODE_BACK})
        time.sleep(1)

        print("Injecting APP_SWITCH...")
        send_cmd({"type": "inject_keycode", "action": "down", "keycode": AKEYCODE_APP_SWITCH})
        send_cmd({"type": "inject_keycode", "action": "up", "keycode": AKEYCODE_APP_SWITCH})
        time.sleep(1)

        print("Returning HOME...")
        send_cmd({"type": "inject_keycode", "action": "down", "keycode": AKEYCODE_HOME})
        send_cmd({"type": "inject_keycode", "action": "up", "keycode": AKEYCODE_HOME})
        time.sleep(1)

        print("Injecting text 'Hello Scrcpy'...")
        send_cmd({"type": "inject_text", "text": "Hello Scrcpy"})

        frame_saved = False
        start_time = time.time()
        # Run for 30 seconds
        while time.time() - start_time < 30:
            buf = shm.buf
            # Header layout (Page 0):
            # latest_index(0), num_slots(4), slot_data_size(8), reserved(12)
            header_data = bytes(buf[:12])
            latest_index, num_slots, slot_data_size = struct.unpack("III", header_data)

            # Slot meta array starts at offset 16 in Page 0.
            # Stride is 32 bytes per slot.
            # struct sc_shm_slot_meta (offset 16+i*32):
            # width(0), height(4), format(8), size(12), pts(16), seq(24), res(28)
            slot_meta_offset = 16 + latest_index * 32
            meta_data = bytes(buf[slot_meta_offset:slot_meta_offset + 28])
            width, height, fmt, data_size, pts, sequence = struct.unpack("IIIIQI", meta_data)

            if sequence != last_sequence:
                if not frame_saved and data_size > 0:
                    # Slot data starts at Page 1 + index * slot_data_size
                    data_offset = PAGE_SIZE + latest_index * slot_data_size
                    yuv_data = bytes(buf[data_offset:data_offset + data_size])
                    save_ppm(width, height, yuv_data, "frame.ppm")
                    frame_saved = True

                last_sequence = sequence

                # Update moving tracker overlay (ID 3)
                # Fixed status bar (ID 1)
                send_cmd({
                    "type": "overlay_add",
                    "item": {"id": 1, "type": "rect", "x": 500, "y": 500, "w": 9000, "h": 800, "r": 0, "g": 0, "b": 100, "a": 200, "filled": True}
                })

                # Dynamic text (ID 2)
                send_cmd({
                    "type": "overlay_add",
                    "item": {"id": 2, "type": "text", "x": 1000, "y": 650, "size": 3, "text": f"BUF:{latest_index} SEQ:{sequence} PTS:{pts}", "r": 255, "g": 255, "b": 255, "a": 255}
                })

                # Moving circle (ID 3)
                cx = 5000 + int(3000 * (time.time() % 2 - 1))
                send_cmd({
                    "type": "overlay_add",
                    "item": {"id": 3, "type": "circle", "x": cx, "y": 5000, "radius": 400, "r": 255, "g": 255, "b": 0, "a": 200, "filled": True}
                })

                # Force refresh to see overlays even if screen doesn't update
                send_cmd({"type": "render_refresh"})

            time.sleep(0.01) # Poll faster

    except KeyboardInterrupt:
        pass
    finally:
        print("Cleaning up...")
        try:
            send_cmd({"type": "overlay_clear"})
            send_cmd({"type": "render_refresh"})
        except:
            pass
        shm.close()

if __name__ == "__main__":
    main()
