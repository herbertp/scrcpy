
import socket
import json
import sys
import os

def main():
    socket_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/android.socket"

    if not os.path.exists(socket_path):
        print(f"Socket {socket_path} not found.")
        return

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_path)
    print(f"Connected to {socket_path}")
    print("Instructions: Move mouse in scrcpy window. Hold Right-Alt to intercept and change colors.")
    print("  Yellow: Normal Move")
    print("  Red: Intercepted Down")
    print("  Green: Intercepted Up")

    width = 1080 # default
    height = 1920

    def send_cmd(cmd):
        sock.sendall((json.dumps(cmd) + "\n").encode())

    # Keep track of circle color
    # Yellow: (255, 255, 0)
    # Red: (255, 0, 0)
    # Green: (0, 255, 0)
    current_color = (255, 255, 0)

    buffer = ""
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data.decode()
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line: continue
                msg = json.loads(line)

                if msg.get("type") == "hello":
                    width = msg.get("width", width)
                    height = msg.get("height", height)
                    print(f"Device Resolution: {width}x{height}")

                elif msg.get("type") == "event_input":
                    evt = msg["event"]
                    intercepted = msg.get("intercepted", False)

                    if evt["type"] in ["mouse_motion", "mouse_button"]:
                        fx = evt.get("frame_x")
                        fy = evt.get("frame_y")

                        if fx is not None and fy is not None:
                            # Map frame coords to normalized 0-10000
                            nx = int(fx * 10000 / width)
                            ny = int(fy * 10000 / height)

                            if evt["type"] == "mouse_button":
                                action = evt["action"]
                                if intercepted:
                                    if action == "down":
                                        current_color = (255, 0, 0) # Red
                                    else:
                                        current_color = (0, 255, 0) # Green
                                else:
                                    current_color = (255, 255, 0) # Yellow

                            # Update overlay
                            send_cmd({
                                "type": "overlay_add",
                                "item": {
                                    "id": 99,
                                    "type": "circle",
                                    "x": nx,
                                    "y": ny,
                                    "radius": 50,
                                    "r": current_color[0],
                                    "g": current_color[1],
                                    "b": current_color[2],
                                    "a": 128,
                                    "filled": True
                                }
                            })
                            # Refresh screen to show it immediately
                            send_cmd({"type": "render_refresh"})

    except KeyboardInterrupt:
        pass
    finally:
        send_cmd({"type": "overlay_remove", "id": 99})
        send_cmd({"type": "render_refresh"})
        sock.close()

if __name__ == "__main__":
    main()
