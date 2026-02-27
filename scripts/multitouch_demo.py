
import socket
import json
import time
import sys

def main():
    socket_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/android.socket"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_path)

    def send_cmd(cmd):
        sock.sendall((json.dumps(cmd) + "\n").encode())

    print("Starting Multi-touch Demo...")

    # 1. Pan (single finger)
    print("Step 1: Panning...")
    send_cmd({"type": "inject_touch", "action": "down", "x": 5000, "y": 5000, "pointer_id": 10})
    for i in range(20):
        send_cmd({"type": "inject_touch", "action": "move", "x": 5000 + i*50, "y": 5000 + i*50, "pointer_id": 10})
        time.sleep(0.02)
    send_cmd({"type": "inject_touch", "action": "up", "x": 6000, "y": 6000, "pointer_id": 10})
    time.sleep(0.5)

    # 2. Pinch-Zoom IN (two fingers moving apart)
    print("Step 2: Zooming In...")
    # Fingers start close together in the center
    send_cmd({"type": "inject_touch", "action": "down", "x": 4800, "y": 5000, "pointer_id": 100})
    send_cmd({"type": "inject_touch", "action": "down", "x": 5200, "y": 5000, "pointer_id": 101})
    time.sleep(0.1)
    for i in range(30):
        send_cmd({"type": "inject_touch", "action": "move", "x": 4800 - i*50, "y": 5000, "pointer_id": 100})
        send_cmd({"type": "inject_touch", "action": "move", "x": 5200 + i*50, "y": 5000, "pointer_id": 101})
        time.sleep(0.02)
    send_cmd({"type": "inject_touch", "action": "up", "x": 4800 - 1500, "y": 5000, "pointer_id": 100})
    send_cmd({"type": "inject_touch", "action": "up", "x": 5200 + 1500, "y": 5000, "pointer_id": 101})
    time.sleep(0.5)

    # 3. Pan again
    print("Step 3: Panning again...")
    send_cmd({"type": "inject_touch", "action": "down", "x": 3000, "y": 3000, "pointer_id": 10})
    for i in range(20):
        send_cmd({"type": "inject_touch", "action": "move", "x": 3000 - i*50, "y": 3000, "pointer_id": 10})
        time.sleep(0.02)
    send_cmd({"type": "inject_touch", "action": "up", "x": 2000, "y": 3000, "pointer_id": 10})
    time.sleep(0.5)

    # 4. Pinch-Zoom OUT (two fingers moving together)
    print("Step 4: Zooming Out...")
    send_cmd({"type": "inject_touch", "action": "down", "x": 2000, "y": 5000, "pointer_id": 100})
    send_cmd({"type": "inject_touch", "action": "down", "x": 8000, "y": 5000, "pointer_id": 101})
    time.sleep(0.1)
    for i in range(30):
        send_cmd({"type": "inject_touch", "action": "move", "x": 2000 + i*80, "y": 5000, "pointer_id": 100})
        send_cmd({"type": "inject_touch", "action": "move", "x": 8000 - i*80, "y": 5000, "pointer_id": 101})
        time.sleep(0.02)
    send_cmd({"type": "inject_touch", "action": "up", "x": 4400, "y": 5000, "pointer_id": 100})
    send_cmd({"type": "inject_touch", "action": "up", "x": 5600, "y": 5000, "pointer_id": 101})

    print("Demo Complete.")
    sock.close()

if __name__ == "__main__":
    main()
