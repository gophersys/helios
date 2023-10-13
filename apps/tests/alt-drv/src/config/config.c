#include "config.h"

#define REMOTE_HOST_IP "192.168.0.70"
#define UPLINK_SOCKET 5000  // Client connects to this port

static cipher_daemon_config_t cfg = {
    .device_id = THIS_DEVICE_ID,
    .uplink_ifaces[0] = {
        .type = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_UPLINK,
        .host = REMOTE_HOST_IP,
        .port = UPLINK_SOCKET,
    },
    .num_uplink_ifaces = 1,
    .num_downlink_ifaces = 0,
};

static cipher_daemon_t daemon = {0};

cipher_daemon_config_t* get_app_config(void) {
    return &cfg;
}

cipher_daemon_t* get_app_daemon(void) {
    return &daemon;
}