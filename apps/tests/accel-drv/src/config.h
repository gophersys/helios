#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#include "daemon/daemon.h"
#include "transport/transport.h"

#define THIS_DEVICE_ID 123
#define REMOTE_HOST_IP "192.168.0.10"
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

static cipher_daemon_t d = {0};

#endif