# scrcpy External API Documentation

This extension allows external processes to access the device display via a Triple-Buffered Shared Memory segment and control it via a JSON API over a Unix Domain Socket.

## Shared Memory (SHM) Access

Enable with `--shm-name=<name>`.

### Segment Layout

The segment is organized into a 4KB header followed by 3 page-aligned slots.

#### Header (at offset 0)
| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | `uint32_t` | `latest_index` | Index of the most recently completed frame (0, 1, or 2). |
| 4 | `uint32_t` | `num_slots` | Always `3`. |
| 8 | `uint32_t` | `slot_size` | Total size of one slot (header + data + padding), 4KB aligned. |

#### Slots (starting at offset 4096)
Each slot starts at `4096 + index * slot_size`.

| Offset from Slot Start | Type | Name | Description |
|---|---|---|---|
| 0 | `uint32_t` | `width` | Frame width. |
| 4 | `uint32_t` | `height` | Frame height. |
| 8 | `uint32_t` | `format` | Pixel format (usually `0` for YUV420P). |
| 12 | `uint32_t` | `size` | Size of the frame data in bytes. |
| 16 | `uint64_t` | `pts` | Presentation timestamp in microseconds. |
| 24 | `uint32_t` | `sequence` | Sequence number for this slot. |
| 4096 | `uint8_t[]` | `data` | Raw frame data (aligned to 4KB boundary from slot start). |

**Note**: `latest_index` is updated atomically only after a full frame copy. To read, check `latest_index` in the main header, then access the corresponding slot.

## JSON API Socket

Enable with `--api-socket=<path>`.

The socket listens for JSON-encoded commands. Multiple commands can be sent over a single connection.

### Commands

#### Input Injection

*   **`inject_touch`**: Send a touch event.
    ```json
    {"type": "inject_touch", "action": "down|up|move", "x": 0..10000, "y": 0..10000, "pointer_id": -1, "pressure": 1.0}
    ```
*   **`inject_keycode`**: Send a key event.
    ```json
    {"type": "inject_keycode", "action": "down|up", "keycode": <int>}
    ```
    (See `android/keycodes.h` for keycode values, e.g., HOME=3, BACK=4)
*   **`inject_text`**: Inject raw text.
    ```json
    {"type": "inject_text", "text": "Hello"}
    ```
*   **`block_input`**: Block/unblock physical user input (keyboard/mouse from the PC).
    ```json
    {"type": "block_input", "value": true|false}
    ```

#### Overlays

*   **`overlay_add`**: Add a primitive to the screen overlay.
    ```json
    {
      "type": "overlay_add",
      "item": {
        "type": "line|rect|circle|cross|text",
        "x": 0..10000, "y": 0..10000,
        "r": 0..255, "g": 0..255, "b": 0..255, "a": 0..255,
        "thickness": 1, "filled": false,
        ... (primitive specific fields)
      }
    }
    ```
    **Primitive fields**:
    - `line`: `x1`, `y1`, `x2`, `y2`
    - `rect`: `w`, `h`
    - `circle`: `radius`
    - `cross`: `size`
    - `text`: `text` (string), `size` (scale factor)

*   **`overlay_clear`**: Clear all current overlay items.
    ```json
    {"type": "overlay_clear"}
    ```

### Coordinates
All coordinates (`x`, `y`, `w`, `h`, etc.) are normalized in the range **[0, 10000]**, where (0,0) is the top-left and (10000, 10000) is the bottom-right of the visible device screen area.
