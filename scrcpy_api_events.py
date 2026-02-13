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

    try:
        # Use makefile for robust line-by-line reading (handles fragmentation and multiple JSONs per packet)
        f = sock.makefile('r', encoding='utf-8')
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
                timestamp = time.strftime('%H:%M:%S')
                print(f"[{timestamp}] {msg}")
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
