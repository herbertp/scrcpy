import socket
import json
import time
import sys
import struct
from multiprocessing import shared_memory

def main():
    shm_name = "scrcpy_shm"
    api_socket_path = "/tmp/scrcpy_api.sock"

    if len(sys.argv) > 1:
        shm_name = sys.argv[1]
    if len(sys.argv) > 2:
        api_socket_path = sys.argv[2]

    # POSIX SHM names in Python's shared_memory shouldn't have the leading slash
    # but the C code adds it if it's missing.
    name_for_py = shm_name if not shm_name.startswith("/") else shm_name[1:]

    print(f"Connecting to SHM: {shm_name}")
    try:
        shm = shared_memory.SharedMemory(name=name_for_py)
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
            print(f"Failed to send command: {e}")

    try:
        # Header format: 4u32 (width, height, format, size), 1u64 (pts), 1u32 (sequence)
        # Total size: 4*4 + 8 + 4 = 28 bytes
        header_size = 28

        last_sequence = -1

        print("Starting main loop. Press Ctrl+C to stop.")

        # Clear overlays at start
        send_cmd({"type": "overlay_clear"})

        # Block user input for a bit to demonstrate
        print("Blocking user input for 3 seconds...")
        send_cmd({"type": "block_input", "value": True})

        # Draw a big blue rectangle
        send_cmd({
            "type": "overlay_add",
            "item": {"type": "rect", "x": 1000, "y": 1000, "w": 8000, "h": 8000, "r": 0, "g": 0, "b": 255, "a": 128}
        })

        start_time = time.time()
        while time.time() - start_time < 10:
            header_data = shm.buf[:header_size]
            width, height, fmt, data_size, pts, sequence = struct.unpack("IIIIQI", header_data)

            if sequence != last_sequence:
                last_sequence = sequence
                print(f"Frame: {width}x{height}, format={fmt}, pts={pts}, seq={sequence}")

                # Move a red circle around
                angle = (time.time() * 2) % 6.28
                cx = 5000 + int(3000 * 0.5 * (1 + 0.5 * (angle))) # just some motion
                cx = 5000 + int(2000 * (angle / 6.28)) # linear motion for simplicity

                # Clear and add new circle and text
                send_cmd({"type": "overlay_clear"})
                send_cmd({
                    "type": "overlay_add",
                    "item": {"type": "circle", "x": 5000 + int(2000 * (time.time() % 2 - 1)), "y": 5000, "radius": 500, "r": 255, "g": 0, "b": 0, "a": 255}
                })
                send_cmd({
                    "type": "overlay_add",
                    "item": {"type": "text", "x": 100, "y": 100, "size": 2, "text": f"Seq: {sequence}", "r": 255, "g": 255, "b": 0, "a": 255}
                })

                if time.time() - start_time > 3:
                     # Unblock after 3 seconds
                     send_cmd({"type": "block_input", "value": False})

            time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        print("Cleaning up...")
        send_cmd({"type": "overlay_clear"})
        send_cmd({"type": "block_input", "value": False})
        shm.close()

if __name__ == "__main__":
    main()
