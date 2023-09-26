// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "protocol/protocol.h"
#include "protocol/serdes.h"
#include "transport/transport.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "packet.h"
#include "services.h"
#include "threads.h"

LOG_MODULE_DECLARE(sd, SD_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                               Iface Connection Event
 *---------------------------------------------------------------------------------------------------*/

void handle_iface_conn_event(cipher_daemon_t *d) {
    cipher_iface_t *conn_iface = k_fifo_get(&d->sd_iface_conn_queue, K_FOREVER);
    if (conn_iface == NULL)
        ERROR("Null item on sd_iface_conn_queue, daemon %d", d->id);

    LOG("iface %d connected!, advertising all services", conn_iface->id);

    // For each registered service in our registry
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {
        // If the interface is still connected
        if (d->service_registry.entries[i].iface->connected) {
            // If the entry's iface is NOT the one that just connected
            if (d->service_registry.entries[i].iface->id != conn_iface->id) {
                // Create the service discovery payload
                cipher_payload_sd_t payload = {
                    .alive = true,
                    .id = d->service_registry.entries[i].service_id,
                    .num_ops = 0,
                };

                send_service_broadcast(d, conn_iface, &payload);
            }
        }
    }
}