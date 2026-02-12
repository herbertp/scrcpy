import socket
import json
import time
import sys
import struct
import os
from multiprocessing import shared_memory, resource_tracker

def save_ppm(width, height, yuv_data, filename):
    """Saves a YUV420P frame as a PPM file (RGB)."""
    # Simple YUV420P to RGB conversion
    # YUV420P: Y plane (W*H), then U plane (W/2 * H/2), then V plane (W/2 * H/2)
    y_size = width * height
    uv_size = (width // 2) * (height // 2)

    y_plane = yuv_data[:y_size]
    u_plane = yuv_data[y_size:y_size + uv_size]
    v_plane = yuv_data[y_size + uv_size:y_size + 2*uv_size]

    rgb = bytearray(width * height * 3)

    for j in range(height):
        for i in range(width):
            y = y_plane[j * width + i]
            # U and V are subsampled
            u = u_plane[(j // 2) * (width // 2) + (i // 2)]
            v = v_plane[(j // 2) * (width // 2) + (i // 2)]

            # Integer conversion (standard SDTV coefficients)
            # C = Y - 16, D = U - 128, E = V - 128
            c = y - 16
            d = u - 128
            e = v - 128

            r = (298 * c + 409 * e + 128) >> 8
            g = (298 * c - 100 * d - 208 * e + 128) >> 8
            b = (298 * c + 516 * d + 128) >> 8

            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))

            idx = (j * width + i) * 3
            rgb[idx] = r
            rgb[idx+1] = g
            rgb[idx+2] = b

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
            pass # print(f"Failed to send command: {e}")

    try:
        header_size = 28
        last_sequence = -1

        print("Starting main loop. Press Ctrl+C to stop.")

        send_cmd({"type": "overlay_clear"})

        # Block user input for a bit to demonstrate
        print("Blocking user input for 3 seconds...")
        send_cmd({"type": "block_input", "value": True})

        # Draw a big blue rectangle (semi-transparent)
        send_cmd({
            "type": "overlay_add",
            "item": {"type": "rect", "x": 1000, "y": 1000, "w": 8000, "h": 8000, "r": 0, "g": 0, "b": 255, "a": 128}
        })

        frame_saved = False
        start_time = time.time()
        while time.time() - start_time < 10:
            width, height, fmt, data_size, pts, sequence = struct.unpack_from("IIIIQI", shm.buf, 0)

            if sequence != last_sequence:
                if last_sequence != -1:
                    print(f"Frame: {width}x{height}, format={fmt}, pts={pts}, seq={sequence}")

                # Save first valid frame to verify SHM content
                if not frame_saved and data_size > 0:
                    yuv_data = shm.buf[header_size:header_size + data_size]
                    save_ppm(width, height, yuv_data, "frame.ppm")
                    frame_saved = True

                last_sequence = sequence

                # Clear and add new circle and text
                send_cmd({"type": "overlay_clear"})
                # Re-add background rect because we cleared all
                send_cmd({
                    "type": "overlay_add",
                    "item": {"type": "rect", "x": 1000, "y": 1000, "w": 8000, "h": 8000, "r": 0, "g": 0, "b": 255, "a": 64}
                })
                send_cmd({
                    "type": "overlay_add",
                    "item": {"type": "circle", "x": 5000 + int(2000 * (time.time() % 2 - 1)), "y": 5000, "radius": 500, "r": 255, "g": 0, "b": 0, "a": 255}
                })
                send_cmd({
                    "type": "overlay_add",
                    "item": {"type": "text", "x": 100, "y": 100, "size": 3, "text": f"Seq: {sequence} PTS: {pts}", "r": 255, "g": 255, "b": 0, "a": 255}
                })

                if time.time() - start_time > 3:
                     send_cmd({"type": "block_input", "value": False})

            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        print("Cleaning up...")
        send_cmd({"type": "overlay_clear"})
        send_cmd({"type": "block_input", "value": False})
        shm.close()

if __name__ == "__main__":
    main()
