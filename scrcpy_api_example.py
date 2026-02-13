import socket
import json
import time
import sys
import struct
import os
import threading
from multiprocessing import shared_memory, resource_tracker

# Constants from android/keycodes.h
AKEYCODE_HOME = 3
AKEYCODE_BACK = 4
AKEYCODE_APP_SWITCH = 187

def save_ppm(width, height, yuv_data, filename):
    """Saves a YUV420P frame as a PPM file (RGB)."""
    uv_width = (width + 1) // 2
    uv_height = (height + 1) // 2
    y_size = width * height
    uv_size = uv_width * uv_height
    expected_size = y_size + 2 * uv_size

    if len(yuv_data) < expected_size:
        return

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
            u = u_plane[uv_j * uv_width + uv_i]
            v = v_plane[uv_j * uv_width + uv_i]
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

class ScrcpyClient:
    def __init__(self, shm_name, socket_path):
        self.shm_name = shm_name
        self.socket_path = socket_path
        self.shm = None
        self.sock = None
        self.running = True

    def connect(self):
        name_for_py = self.shm_name if not self.shm_name.startswith("/") else self.shm_name[1:]
        print(f"Connecting to SHM: {self.shm_name}")
        self.shm = shared_memory.SharedMemory(name=name_for_py)
        resource_tracker.unregister(self.shm._name, "shared_memory")

        print(f"Connecting to API socket: {self.socket_path}")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)
        self.sock.setblocking(False)

    def send(self, cmd):
        data = json.dumps(cmd).encode()
        self.sock.setblocking(True)
        self.sock.sendall(data)
        self.sock.setblocking(False)

    def receive_loop(self):
        buffer = ""
        while self.running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                buffer += data.decode()
                # Use a better JSON split logic
                while "{" in buffer and "}" in buffer:
                    # Find matching braces
                    start = buffer.find("{")
                    count = 0
                    end = -1
                    for i in range(start, len(buffer)):
                        if buffer[i] == "{": count += 1
                        elif buffer[i] == "}": count -= 1
                        if count == 0:
                            end = i + 1
                            break
                    if end != -1:
                        msg_str = buffer[start:end]
                        buffer = buffer[end:]
                        try:
                            msg = json.loads(msg_str)
                            if msg.get("type") == "event_input":
                                evt = msg["event"]
                                intercepted = " [INTERCEPTED]" if msg.get("intercepted") else ""
                                if evt["type"] == "mouse_motion":
                                    # print(f"User Mouse Move: ({evt['x']}, {evt['y']}){intercepted}")
                                    pass
                                elif evt["type"] == "mouse_button":
                                    print(f"User Mouse {evt['action'].upper()}: Button {evt['button']} at ({evt['x']}, {evt['y']}){intercepted}")
                                elif evt["type"] == "key":
                                    print(f"User Key {evt['action'].upper()}: Code {evt['keycode']}{intercepted}")
                        except json.JSONDecodeError:
                            pass
                    else:
                        break
            except BlockingIOError:
                time.sleep(0.01)
            except Exception as e:
                print(f"Receiver error: {e}")
                break

    def run(self):
        self.connect()
        recv_thread = threading.Thread(target=self.receive_loop)
        recv_thread.start()

        try:
            PAGE_SIZE = 4096
            last_sequence = -1
            print("Starting main loop. Press Ctrl+C to stop.")
            print("TRY HOLDING RIGHT-ALT IN SCRCPY WINDOW TO TEST INTERCEPTION!")

            frame_saved = False
            start_time = time.time()
            while time.time() - start_time < 30:
                buf = self.shm.buf
                header_data = bytes(buf[:12])
                latest_index, num_slots, slot_data_size = struct.unpack("III", header_data)

                meta_offset = 16 + latest_index * 32
                meta_data = bytes(buf[meta_offset:meta_offset + 28])
                width, height, fmt, data_size, pts, sequence = struct.unpack("IIIIQI", meta_data)

                if sequence != last_sequence:
                    if not frame_saved and data_size > 0:
                        data_offset = PAGE_SIZE + latest_index * slot_data_size
                        save_ppm(width, height, bytes(buf[data_offset:data_offset + data_size]), "frame.ppm")
                        frame_saved = True

                    last_sequence = sequence

                    self.send({"type": "overlay_add", "item": {"id": 1, "type": "rect", "x": 100, "y": 100, "w": 3500, "h": 500, "r": 0, "g": 0, "b": 150, "a": 200, "filled": True}})
                    self.send({"type": "overlay_add", "item": {"id": 2, "type": "text", "x": 200, "y": 200, "size": 3, "text": f"EVENT MONITOR ACTIVE", "r": 255, "g": 255, "b": 255, "a": 255}})
                    self.send({"type": "render_refresh"})

                time.sleep(0.05)

        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            # Break receive loop
            try: self.sock.shutdown(socket.SHUT_RDWR)
            except: pass
            recv_thread.join()
            self.send({"type": "overlay_clear"})
            self.send({"type": "render_refresh"})
            self.shm.close()
            self.sock.close()

if __name__ == "__main__":
    shm_n = sys.argv[1] if len(sys.argv) > 1 else "android"
    sock_p = sys.argv[2] if len(sys.argv) > 2 else "/tmp/android.socket"
    client = ScrcpyClient(shm_n, sock_p)
    client.run()
