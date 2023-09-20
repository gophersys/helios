#ifndef CONFIG_DAEMON_H
#define CONFIG_DAEMON_H

// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/kernel.h>

// Cipher includes
#include "config/default.h"
#include "transport/transport.h"

typedef struct
{
    tal_config_t uplink_ifaces[CONFIG_UP_LINK_INTERFACE_COUNT];
    tal_config_t downlink_ifaces[CONFIG_DOWN_LINK_INTERFACE_COUNT];
} cipher_daemon_config_t;

#endif // CONFIG_DAEMON_H