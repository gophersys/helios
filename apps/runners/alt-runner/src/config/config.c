#include "config.h"

#define ICLE_IP "192.168.0.70"
#define RUNNER_SOCKET 5000  // Client iface connects to this port

static cipher_daemon_config_t cfg = {
    .device_id = THIS_DEVICE_ID,
    // Connection to ICLE
    .client_ifaces[0] = {
        .type = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_CLIENT,
        .host = ICLE_IP,
        .port = RUNNER_SOCKET,
    },
    .num_client_ifaces = 1,
    .num_server_ifaces = 0,
};

static cipher_daemon_t daemon = {0};

cipher_daemon_config_t* get_app_config(void) {
    return &cfg;
}

cipher_daemon_t* get_app_daemon(void) {
    return &daemon;
}