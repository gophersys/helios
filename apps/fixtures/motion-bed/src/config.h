#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#include <zephyr/kernel.h>

#include "daemon/daemon.h"
#include "transport/transport.h"

#define THIS_DEVICE_ID 124
#define DOWNLINK_SOCKET 5000  // Server listens on this port

static cipher_daemon_config_t cfg = {
    .device_id = THIS_DEVICE_ID,
    .downlink_ifaces[0] = {
        .type = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_DOWNLINK,
        .host = NULL,  // Not needed for downlink
        .port = DOWNLINK_SOCKET,
    },
    .num_uplink_ifaces = 0,
    .num_downlink_ifaces = 1,
};

static cipher_daemon_t d = {0};

#endif