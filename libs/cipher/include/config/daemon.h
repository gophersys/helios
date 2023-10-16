#ifndef CONFIG_DAEMON_H
#define CONFIG_DAEMON_H

// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/kernel.h>

// Cipher includes
#include "config/default.h"
#include "transport/transport.h"

typedef struct {
    uint16_t device_id;
    tal_config_t client_ifaces[CONFIG_CLIENT_IFACE_COUNT];
    size_t num_client_ifaces;
    tal_config_t server_ifaces[CONFIG_SERVER_IFACE_COUNT];
    size_t num_server_ifaces;
} cipher_daemon_config_t;

#endif  // CONFIG_DAEMON_H