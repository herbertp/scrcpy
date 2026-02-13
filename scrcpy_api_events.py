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

    buffer = ""
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                print("Connection closed by server.")
                break

            buffer += data.decode()

            # Streaming JSON parser: find complete { ... } blocks
            while "{" in buffer and "}" in buffer:
                start = buffer.find("{")
                count = 0
                end = -1
                for i in range(start, len(buffer)):
                    if buffer[i] == "{":
                        count += 1
                    elif buffer[i] == "}":
                        count -= 1
                        if count == 0:
                            end = i + 1
                            break

                if end != -1:
                    msg_str = buffer[start:end]
                    buffer = buffer[end:]
                    try:
                        msg = json.loads(msg_str)
                        print(f"[{time.strftime('%H:%M:%S')}] {msg}")
                    except json.JSONDecodeError as e:
                        print(f"JSON Decode Error: {e}")
                else:
                    # Incomplete JSON object in buffer
                    break

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
