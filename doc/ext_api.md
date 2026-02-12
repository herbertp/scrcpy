# scrcpy External API Documentation

This extension allows external processes to access the device display via Shared Memory and control it via a JSON API over a Unix Domain Socket.

## Shared Memory (SHM) Access

Enable with `--shm-name=<name>`.

### Segment Layout

The shared memory segment contains a fixed-size header followed by the raw decoded frame data.

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | `uint32_t` | `width` | Frame width in pixels. |
| 4 | `uint32_t` | `height` | Frame height in pixels. |
| 8 | `uint32_t` | `format` | Pixel format (usually `0` for YUV420P). |
| 12 | `uint32_t` | `size` | Size of the frame data in bytes. |
| 16 | `uint64_t` | `pts` | Presentation timestamp in microseconds. |
| 24 | `uint32_t` | `sequence` | Incremented every time a new frame is copied. |
| 28 | `uint8_t[]` | `data` | Raw frame data. |

**Note**: To avoid race conditions, the `sequence` number is updated *after* the `data` has been copied into the segment.

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
    - `line`: `x1`, `y1`, `x2`, `y2` (coordinates)
    - `rect`: `w`, `h` (width and height)
    - `circle`: `radius`
    - `cross`: `size`
    - `text`: `text` (string), `size` (scale factor)

*   **`overlay_clear`**: Clear all current overlay items.
    ```json
    {"type": "overlay_clear"}
    ```

### Coordinates
All coordinates (`x`, `y`, `w`, `h`, etc.) are normalized in the range **[0, 10000]**, where (0,0) is the top-left and (10000, 10000) is the bottom-right of the visible device screen area.
