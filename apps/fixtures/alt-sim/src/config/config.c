#include "config.h"

#define THIS_DEVICE_ID 124

#define TEST_SOCKET 5000  // Server listens on this port

static cipher_daemon_config_t cfg = {
    .device_id = THIS_DEVICE_ID,
    .server_ifaces[0] = {
        .type = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_SERVER,
        .host = NULL,  // Not needed for server
        .port = TEST_SOCKET,
    },
    .num_server_ifaces = 1,
    .num_client_ifaces = 0,
};

static cipher_daemon_t daemon = {0};

cipher_daemon_config_t* get_app_config(void) {
    return &cfg;
}

cipher_daemon_t* get_app_daemon(void) {
    return &daemon;
}