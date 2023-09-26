// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(app);

// Cipher includes
#include "daemon/api.h"
#include "daemon/registry.h"
#include "utils/err.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Daemon Config
 *---------------------------------------------------------------------------------------------------*/

#define THIS_DEVICE_ID (uint16_t)623

#define POSIX_HOST_IP "192.168.0.11"
#define UPLINK_SOCKET 5000
#define DOWNLINK_SOCKET 5001

static cipher_daemon_config_t config = {
    .device_id = THIS_DEVICE_ID,
    .uplink_ifaces[0] = {
        .type = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_UPLINK,
        .host = POSIX_HOST_IP,
        .port = UPLINK_SOCKET,
    },
    .downlink_ifaces[0] = {
        .type = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_DOWNLINK,
        .host = POSIX_HOST_IP,
        .port = DOWNLINK_SOCKET,
    },

};

static cipher_daemon_t daemon = {0};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       Local Services
 *---------------------------------------------------------------------------------------------------*/
static cipher_service_entry_t local_services[2] = {
    {
        .local = true,
        .iface = NULL,
        .service = {
            .name = "Test Service 1",
            .service_id = 6969,
            .device_id = THIS_DEVICE_ID,
            .num_ops = 2,
            .allowed_hops = 1,
        },
    },
    {
        .local = true,
        .iface = NULL,
        .service = {
            .name = "Test Service 2",
            .service_id = 6969,
            .device_id = THIS_DEVICE_ID,
            .num_ops = 2,
            .allowed_hops = 1,
        },
    },
};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  App
 *---------------------------------------------------------------------------------------------------*/

int main(void) {
    LOG_RAW("\n\n%s\n", "********** Cipher Protocol App **********");

    cipher_init_daemon(&config, &daemon);
    cipher_register_local_services(&daemon, local_services, ARRAY_SIZE(local_services));

    LOG("App Initialized OK");
    while (true)
        k_msleep(1000);
}