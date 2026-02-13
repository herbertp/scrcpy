import socket
import json
import sys
import time

def main():
    socket_path = "/tmp/android.socket"
    if len(sys.argv) > 1:
        socket_path = sys.argv[1]

    print(f"Connecting to scrcpy API socket: {socket_path}")
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)
    except Exception as e:
        print(f"Error connecting to socket: {e}")
        return

    print("Connected! Listening for events... (Press Ctrl+C to stop)")
    print("TRY HOLDING RIGHT-ALT IN SCRCPY WINDOW TO TEST INTERCEPTION!")

    try:
        f = sock.makefile('r', encoding='utf-8')
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
                timestamp = time.strftime('%H:%M:%S')
                if msg.get("type") == "event_input":
                    evt = msg["event"]
                    intercepted = " [INTERCEPTED]" if msg.get("intercepted") else ""
                    if evt["type"] == "mouse_motion":
                        # Mouse motion can be very noisy, maybe uncomment if needed
                        # print(f"[{timestamp}] User Mouse Move: ({evt['x']}, {evt['y']}){intercepted}")
                        pass
                    elif evt["type"] == "mouse_button":
                        print(f"[{timestamp}] User Mouse {evt['action'].upper()}: Button {evt['button']} at ({evt['x']}, {evt['y']}){intercepted}")
                    elif evt["type"] == "mouse_wheel":
                        print(f"[{timestamp}] User Mouse Wheel: ({evt['x']}, {evt['y']}) Scroll: ({evt['hscroll']}, {evt['vscroll']}){intercepted}")
                    elif evt["type"] == "key":
                        print(f"[{timestamp}] User Key {evt['action'].upper()}: Code {evt['keycode']}{intercepted}")
                else:
                    print(f"[{timestamp}] Received: {msg}")

            except json.JSONDecodeError as e:
                print(f"[{time.strftime('%H:%M:%S')}] JSON Decode Error: {e} | Data: {line}")

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error during execution: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
