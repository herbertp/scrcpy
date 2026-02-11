#include "api_server.h"

#include <sys/socket.h>
#include <sys/un.h>
#include <sys/select.h>
#include <sys/time.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "util/log.h"
#include "util/cJSON.h"
#include "screen.h"
#include "control_msg.h"

static bool
process_command(struct sc_api_server *api, const char *json_str) {
    cJSON *json = cJSON_Parse(json_str);
    if (!json) {
        LOGW("API: Could not parse JSON: %s", json_str);
        return false;
    }

    cJSON *type = cJSON_GetObjectItemCaseSensitive(json, "type");
    if (!cJSON_IsString(type)) {
        cJSON_Delete(json);
        return false;
    }

    bool ok = true;

    if (strcmp(type->valuestring, "inject_touch") == 0) {
        cJSON *action = cJSON_GetObjectItemCaseSensitive(json, "action");
        cJSON *x = cJSON_GetObjectItemCaseSensitive(json, "x");
        cJSON *y = cJSON_GetObjectItemCaseSensitive(json, "y");
        cJSON *id = cJSON_GetObjectItemCaseSensitive(json, "pointer_id");
        cJSON *pressure = cJSON_GetObjectItemCaseSensitive(json, "pressure");

        if (cJSON_IsString(action) && cJSON_IsNumber(x) && cJSON_IsNumber(y)) {
            struct sc_control_msg msg;
            msg.type = SC_CONTROL_MSG_TYPE_INJECT_TOUCH_EVENT;

            if (strcmp(action->valuestring, "down") == 0)
                msg.inject_touch_event.action = AMOTION_EVENT_ACTION_DOWN;
            else if (strcmp(action->valuestring, "up") == 0)
                msg.inject_touch_event.action = AMOTION_EVENT_ACTION_UP;
            else
                msg.inject_touch_event.action = AMOTION_EVENT_ACTION_MOVE;

            msg.inject_touch_event.pointer_id = cJSON_IsNumber(id) ? id->valuedouble : SC_POINTER_ID_MOUSE;
            msg.inject_touch_event.position.screen_size = api->screen->frame_size;
            msg.inject_touch_event.position.point.x = x->valuedouble * api->screen->frame_size.width / 10000;
            msg.inject_touch_event.position.point.y = y->valuedouble * api->screen->frame_size.height / 10000;
            msg.inject_touch_event.pressure = cJSON_IsNumber(pressure) ? pressure->valuedouble : 1.0f;
            msg.inject_touch_event.action_button = 0;
            msg.inject_touch_event.buttons = 0;

            ok = api->controller && sc_controller_push_msg(api->controller, &msg);
        }
    } else if (strcmp(type->valuestring, "inject_keycode") == 0) {
        cJSON *action = cJSON_GetObjectItemCaseSensitive(json, "action");
        cJSON *keycode = cJSON_GetObjectItemCaseSensitive(json, "keycode");

        if (cJSON_IsString(action) && cJSON_IsNumber(keycode)) {
            struct sc_control_msg msg;
            msg.type = SC_CONTROL_MSG_TYPE_INJECT_KEYCODE;
            msg.inject_keycode.action = (strcmp(action->valuestring, "down") == 0)
                                        ? AKEY_EVENT_ACTION_DOWN : AKEY_EVENT_ACTION_UP;
            msg.inject_keycode.keycode = keycode->valueint;
            msg.inject_keycode.repeat = 0;
            msg.inject_keycode.metastate = 0;

            ok = api->controller && sc_controller_push_msg(api->controller, &msg);
        }
    } else if (strcmp(type->valuestring, "overlay_add") == 0) {
        cJSON *item_json = cJSON_GetObjectItemCaseSensitive(json, "item");
        if (cJSON_IsObject(item_json)) {
            struct sc_overlay_item item;
            cJSON *itype = cJSON_GetObjectItemCaseSensitive(item_json, "type");
            cJSON *r = cJSON_GetObjectItemCaseSensitive(item_json, "r");
            cJSON *g = cJSON_GetObjectItemCaseSensitive(item_json, "g");
            cJSON *b = cJSON_GetObjectItemCaseSensitive(item_json, "b");
            cJSON *a = cJSON_GetObjectItemCaseSensitive(item_json, "a");

            item.r = cJSON_IsNumber(r) ? r->valueint : 255;
            item.g = cJSON_IsNumber(g) ? g->valueint : 255;
            item.b = cJSON_IsNumber(b) ? b->valueint : 255;
            item.a = cJSON_IsNumber(a) ? a->valueint : 255;

            if (strcmp(itype->valuestring, "line") == 0) {
                item.type = SC_OVERLAY_TYPE_LINE;
                item.line.x1 = cJSON_GetObjectItemCaseSensitive(item_json, "x1")->valueint;
                item.line.y1 = cJSON_GetObjectItemCaseSensitive(item_json, "y1")->valueint;
                item.line.x2 = cJSON_GetObjectItemCaseSensitive(item_json, "x2")->valueint;
                item.line.y2 = cJSON_GetObjectItemCaseSensitive(item_json, "y2")->valueint;
            } else if (strcmp(itype->valuestring, "rect") == 0) {
                item.type = SC_OVERLAY_TYPE_RECT;
                item.rect.x = cJSON_GetObjectItemCaseSensitive(item_json, "x")->valueint;
                item.rect.y = cJSON_GetObjectItemCaseSensitive(item_json, "y")->valueint;
                item.rect.w = cJSON_GetObjectItemCaseSensitive(item_json, "w")->valueint;
                item.rect.h = cJSON_GetObjectItemCaseSensitive(item_json, "h")->valueint;
            } else if (strcmp(itype->valuestring, "circle") == 0) {
                item.type = SC_OVERLAY_TYPE_CIRCLE;
                item.circle.x = cJSON_GetObjectItemCaseSensitive(item_json, "x")->valueint;
                item.circle.y = cJSON_GetObjectItemCaseSensitive(item_json, "y")->valueint;
                item.circle.r = cJSON_GetObjectItemCaseSensitive(item_json, "radius")->valueint;
            } else if (strcmp(itype->valuestring, "cross") == 0) {
                item.type = SC_OVERLAY_TYPE_CROSS;
                item.cross.x = cJSON_GetObjectItemCaseSensitive(item_json, "x")->valueint;
                item.cross.y = cJSON_GetObjectItemCaseSensitive(item_json, "y")->valueint;
                item.cross.size = cJSON_GetObjectItemCaseSensitive(item_json, "size")->valueint;
            } else if (strcmp(itype->valuestring, "text") == 0) {
                item.type = SC_OVERLAY_TYPE_TEXT;
                item.text.x = cJSON_GetObjectItemCaseSensitive(item_json, "x")->valueint;
                item.text.y = cJSON_GetObjectItemCaseSensitive(item_json, "y")->valueint;
                item.text.size = cJSON_GetObjectItemCaseSensitive(item_json, "size")->valueint;
                cJSON *text = cJSON_GetObjectItemCaseSensitive(item_json, "text");
                item.text.text = cJSON_IsString(text) ? strdup(text->valuestring) : strdup("");
            }
            sc_overlay_add(api->overlay, &item);
        }
    } else if (strcmp(type->valuestring, "overlay_clear") == 0) {
        sc_overlay_clear(api->overlay);
    } else if (strcmp(type->valuestring, "block_input") == 0) {
        cJSON *value = cJSON_GetObjectItemCaseSensitive(json, "value");
        if (cJSON_IsBool(value)) {
            api->screen->im.block_input = cJSON_IsTrue(value);
        }
    }

    cJSON_Delete(json);
    return ok;
}

static int
run_api_server(void *data) {
    struct sc_api_server *api = data;

    int server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server_fd == -1) {
        LOGE("API: Could not create socket");
        return -1;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, api->socket_path, sizeof(addr.sun_path) - 1);

    unlink(api->socket_path);
    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) == -1) {
        LOGE("API: Could not bind socket %s", api->socket_path);
        close(server_fd);
        return -1;
    }

    if (listen(server_fd, 5) == -1) {
        LOGE("API: Could not listen on socket");
        close(server_fd);
        return -1;
    }

    LOGI("API: Listening on %s", api->socket_path);

    char buffer[4096];
    while (!api->stopped) {
        struct timeval tv = {1, 0};
        fd_set fds;
        FD_ZERO(&fds);
        FD_SET(server_fd, &fds);

        int ret = select(server_fd + 1, &fds, NULL, NULL, &tv);
        if (ret > 0) {
            int client_fd = accept(server_fd, NULL, NULL);
            if (client_fd != -1) {
                for (;;) {
                    ssize_t n = read(client_fd, buffer, sizeof(buffer) - 1);
                    if (n <= 0) {
                        break;
                    }
                    buffer[n] = '\0';

                    char *ptr = buffer;
                    while (*ptr) {
                        const char *end;
                        // Process one JSON object at a time from the buffer
                        cJSON *json = cJSON_ParseWithOpts(ptr, &end, false);
                        if (json) {
                            cJSON_Delete(json); // we already have process_command but it parses again
                            // Let's optimize: change process_command to accept cJSON*
                            // For now, I'll just pass the string slice
                            size_t len = end - ptr;
                            char *cmd = malloc(len + 1);
                            if (cmd) {
                                memcpy(cmd, ptr, len);
                                cmd[len] = '\0';
                                process_command(api, cmd);
                                free(cmd);
                            }
                            ptr = (char *)end;
                        } else {
                            break;
                        }
                    }
                }
                close(client_fd);
            }
        }
    }

    close(server_fd);
    unlink(api->socket_path);
    return 0;
}

bool
sc_api_server_init(struct sc_api_server *api, const char *socket_path,
                   struct sc_controller *controller,
                   struct sc_overlay *overlay,
                   struct sc_screen *screen) {
    api->socket_path = strdup(socket_path);
    if (!api->socket_path) {
        return false;
    }
    api->controller = controller;
    api->overlay = overlay;
    api->screen = screen;
    api->stopped = false;
    return true;
}

void
sc_api_server_destroy(struct sc_api_server *api) {
    free(api->socket_path);
}

bool
sc_api_server_start(struct sc_api_server *api) {
    return sc_thread_create(&api->thread, run_api_server, "scrcpy-api", api);
}

void
sc_api_server_stop(struct sc_api_server *api) {
    api->stopped = true;
    sc_thread_join(&api->thread, NULL);
}
