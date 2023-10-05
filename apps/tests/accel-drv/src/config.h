#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#include "daemon/daemon.h"
#include "transport/transport.h"

#define THIS_DEVICE_ID 123
#define POSIX_HOST_IP "127.0.0.1"
#define UPLINK_SOCKET 5000    // Client connects to this port
#define DOWNLINK_SOCKET 5000  // Server listens on this port

static cipher_daemon_config_t cfg = {
    .device_id = THIS_DEVICE_ID,
    .uplink_ifaces[0] = {
        .type = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_UPLINK,
        .host = POSIX_HOST_IP,
        .port = UPLINK_SOCKET,
    },
};

static cipher_daemon_t d = {0};

#endif