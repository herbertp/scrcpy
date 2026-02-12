# scrcpy External API Documentation

This extension allows external processes to access the device display via a Triple-Buffered Shared Memory segment and control it via a JSON API over a Unix Domain Socket.

## Shared Memory (SHM) Access

Enable with `--shm-name=<name>`.

### Segment Layout

The segment is organized into a 4KB header (Page 0) containing all metadata, followed by 3 page-aligned data slots starting at Page 1 (offset 4096).

#### Page 0: Global Header & Metadata
| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | `uint32_t` | `latest_index` | Index of the most recently completed frame (0, 1, or 2). |
| 4 | `uint32_t` | `num_slots` | Always `3`. |
| 8 | `uint32_t` | `slot_data_size` | Size of raw data in one slot, 4KB aligned. |
| 12 | `uint32_t` | `reserved` | Padding to ensure `slots` starts at offset 16. |
| 16 | `struct[]` | `slots` | Array of 3 `sc_shm_slot_meta` structures. |

**`sc_shm_slot_meta` structure (32 bytes each):**
| Offset from Meta | Type | Name | Description |
|---|---|---|---|
| 0 | `uint32_t` | `width` | Frame width. |
| 4 | `uint32_t` | `height` | Frame height. |
| 8 | `uint32_t` | `format` | Pixel format (usually `0` for YUV420P). |
| 12 | `uint32_t` | `size` | Size of the raw frame data in bytes. |
| 16 | `uint64_t` | `pts` | Presentation timestamp in microseconds. |
| 24 | `uint32_t` | `sequence` | Incremented every time this slot is updated. |
| 28 | `uint32_t` | `reserved` | Padding for alignment. |

#### Page 1+: Raw Frame Data
Raw image data for slot `i` starts at `4096 + i * slot_data_size`. Each raw data buffer is guaranteed to start on a 4KB page boundary.

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
*   **`block_input`**: Block/unblock physical user input.
    ```json
    {"type": "block_input", "value": true|false}
    ```

#### Overlays

*   **`overlay_add`**: Add or update a primitive. If `id` matches an existing item, it is replaced.
    ```json
    {
      "type": "overlay_add",
      "item": {
        "id": <uint32>,
        "type": "line|rect|circle|cross|text",
        "x": 0..10000, "y": 0..10000,
        "r": 0..255, "g": 0..255, "b": 0..255, "a": 0..255,
        "thickness": 1, "filled": false,
        ... (primitive specific fields)
      }
    }
    ```
*   **`overlay_remove`**: Delete a specific overlay item.
    ```json
    {"type": "overlay_remove", "id": <uint32>}
    ```
*   **`overlay_clear`**: Clear all current overlay items.
    ```json
    {"type": "overlay_clear"}
    ```

#### Rendering

*   **`render_refresh`**: Force scrcpy to redraw the current frame and overlays immediately. Use this if you update overlays while the device screen is static.
    ```json
    {"type": "render_refresh"}
    ```

### Coordinates
All coordinates are normalized in the range **[0, 10000]** mapped to the visible device screen area.
