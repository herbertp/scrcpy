# scrcpy External API Documentation

This extension allows external processes to access the device display via a Triple-Buffered Shared Memory segment and control/monitor it via a JSON API over a Unix Domain Socket.

## Shared Memory (SHM) Access

Enable with `--shm-name=<name>`.

### Segment Layout

The segment is organized into a 4KB header (Page 0) containing all metadata, followed by 3 page-aligned data slots starting at Page 1 (offset 4096).

#### Page 0: Global Header & Metadata
| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | `uint32_t` | `latest_index` | Index of the most recently completed frame (0, 1, or 2). |
| 4 | `uint32_t` | `num_slots` | Always `3`. |
| 8 | `uint32_t` | `slot_data_size` | Size of raw data area in one slot, 4KB aligned. |
| 12 | `uint32_t` | `reserved` | Padding to ensure `slots` starts at offset 16. |
| 16 | `struct[]` | `slots` | Array of 3 `sc_shm_slot_meta` structures (32 bytes each). |

**`sc_shm_slot_meta` structure (32 bytes):**
| Offset from Meta | Type | Name | Description |
|---|---|---|---|
| 0 | `uint32_t` | `width` | Frame width. |
| 4 | `uint32_t` | `height` | Frame height. |
| 8 | `uint32_t` | `format` | Pixel format (usually `0` for YUV420P). |
| 12 | `uint32_t` | `size` | Size of the raw frame data in bytes. |
| 16 | `uint64_t` | `pts` | Presentation timestamp in microseconds. |
| 24 | `uint32_t` | `sequence` | Incremented every time this slot is updated. |
| 28 | `uint32_t` | `reserved` | Padding. |

#### Page 1+: Raw Frame Data
Raw image data for slot `i` starts at `4096 + i * slot_data_size`. Each raw data buffer is guaranteed to start on a 4KB page boundary.

## JSON API Socket

Enable with `--api-socket=<path>`.

The socket listens for JSON-encoded commands and broadcasts JSON-encoded user events. Multiple commands can be sent over a single connection, and it should be kept open to receive event streams.

### Outgoing Messages (Events from scrcpy)

Whenever the user interacts with the scrcpy window, a message is broadcast to all connected clients.

*   **`event_input`**: User key or mouse action.
    ```json
    {
      "type": "event_input",
      "intercepted": true|false,
      "event": {
        "type": "key|mouse_motion|mouse_button",
        "action": "down|up",
        "keycode": <int>,
        "x": <int>,
        "y": <int>,
        ...
      }
    }
    ```
    **Interception**: If the user holds **Right-Alt** while interacting, `intercepted` is `true`, and scrcpy will **NOT** forward the event to the Android device.

### Incoming Messages (Commands to scrcpy)

#### Input Injection
*   **`inject_touch`**: Send a touch event. action: `down`, `up`, or `move`. x/y: 0..10000.
*   **`inject_keycode`**: Send a key event. keycode: Android keycode.
*   **`inject_text`**: Inject raw text string.
*   **`block_input`**: Block/unblock all physical user input.

#### Overlays
*   **`overlay_add`**: Add/update a primitive. If `id` matches an existing item, it is replaced.
    - Types: `line`, `rect`, `circle`, `cross`, `text`.
    - Fields: `id`, `r`, `g`, `b`, `a`, `thickness`, `filled`, etc.
*   **`overlay_remove`**: Delete an item by `id`.
*   **`overlay_clear`**: Clear all items.

#### Rendering
*   **`render_refresh`**: Force a redraw of the scrcpy window immediately.

### Coordinates
Coordinates in JSON commands are normalized [0, 10000]. Events from scrcpy use window-relative pixel coordinates.
