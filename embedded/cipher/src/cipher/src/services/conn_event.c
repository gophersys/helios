// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/registry.h"
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

    cipher_iface_t *conn_iface = k_fifo_get(&d->sd_iface_conn_queue, K_NO_WAIT);
    __ASSERT(conn_iface, "Null item on sd_iface_conn_queue, daemon %d", d->id);
    __ASSERT(!conn_iface->connected, "Expected iface %d for daemon %d to be conencted", conn_iface->id, d->id);

    DBG("Iface %d, daemon %d connected!, advertising all services", conn_iface->id, d->id);

    // For each registered service in our registry, send it to the new interface
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *entry = &d->service_registry.entries[i];

        // Skip entry if it belongs to this same interface
        if (entry->iface->id == conn_iface->id) {
            continue;
        }

        // Skip entry if it cannot be routed to other devices
        if (entry->service.allowed_hops < 1) {
            continue;
        }

        // Create payload and send it on the newly connected interface
        cipher_payload_sd_t payload = {
            .alive = true,
            .service_id = entry->service.service_id,
            .device_id = entry->service.device_id,
            .num_ops = entry->service.num_ops,
            .allowed_hops = entry->service.allowed_hops,
        };
        strcpy(payload.name, entry->service.name);

        send_service_payload(d, conn_iface, &payload);
    }
}