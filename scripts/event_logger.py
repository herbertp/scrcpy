
import socket
import json
import sys
import time

def main():
    socket_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/android.socket"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_path)

    print(f"Logging events from {socket_path}... Press Ctrl+C to stop.")

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

                mtype = msg.get("type")
                if mtype == "hello":
                    print(f"[HELLO] Version: {msg.get('version')}, Screen: {msg.get('width')}x{msg.get('height')}")
                elif mtype == "event_input":
                    evt = msg["event"]
                    intercepted = " [INTERCEPTED]" if msg.get("intercepted") else ""
                    etype = evt["type"]

                    if etype == "key":
                        print(f"[{time.time():.3f}] KEY: {evt['action'].upper()} code={evt['keycode']}{intercepted}")
                    elif etype == "mouse_motion":
                        print(f"[{time.time():.3f}] MOUSE: MOVE to ({evt['x']}, {evt['y']}) frame=({evt['frame_x']}, {evt['frame_y']}){intercepted}")
                    elif etype == "mouse_button":
                        print(f"[{time.time():.3f}] MOUSE: {evt['action'].upper()} button={evt['button']} at ({evt['x']}, {evt['y']}) frame=({evt['frame_x']}, {evt['frame_y']}){intercepted}")
                    elif etype == "mouse_wheel":
                        print(f"[{time.time():.3f}] WHEEL: h={evt['hscroll']} v={evt['vscroll']} at ({evt['x']}, {evt['y']}){intercepted}")
                else:
                    print(f"[OTHER] {line}")

    except KeyboardInterrupt:
        print("\nStopping logger.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
