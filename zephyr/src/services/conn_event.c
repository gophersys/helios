// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/iface/iface.h>

#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "services.h"
#include "threads.h"

LOG_MODULE_DECLARE(sd, CONFIG_CK_CIPHER_SD_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                               Iface Connection Event
 *---------------------------------------------------------------------------------------------------*/

void handle_iface_conn_event(cipher_daemon_t *d) {

    cipher_iface_t *conn_iface = k_fifo_get(&d->sd.iface_conn_queue, K_NO_WAIT);
    __ASSERT(conn_iface, "Null item on iface_conn_queue, daemon %d", d->id);
    __ASSERT(conn_iface->connected, "Expected iface %d for daemon %d to be conencted", conn_iface->id, d->id);

    DBG("Iface %d, daemon %d connected!, advertising all services", conn_iface->id, d->id);

    // For each service in our registry
    cipher_service_entry_t *current_entry = NULL;
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {
        current_entry = &d->service_registry.entries[i];

        // Skip service if it cannot be routed to other devices
        if (current_entry->service.allowed_hops < 1) {
            continue;
        }

        // TODO: If we only check for local then how do we advertise remote?
        // if (!current_entry->local) {
        //     continue;
        // }

        // Create payload and send it on the newly connected interface
        cipher_payload_sd_broadcast_t payload = {
            .alive = true,
            .service_id = current_entry->service.id,
            .device_id = current_entry->local ? d->device_id : current_entry->end_points[0].device_id,
            .num_ops = current_entry->service.num_ops,
            .allowed_hops = current_entry->service.allowed_hops,
        };
        strcpy(payload.name, current_entry->service.name);

        send_service_payload(d, conn_iface, &payload);

        // // For each end point in that service
        // cipher_service_end_point_t *end_point_entry = NULL;
        // for (size_t j = 0; j < ARRAY_SIZE(current_entry->end_points); j++) {

        //     end_point_entry = &current_entry->end_points[j];

        //     if (!end_point_entry->_used) {
        //         continue;
        //     }

        //     // Skip the interface that just connected
        //     if (end_point_entry->iface == conn_iface) {
        //         continue;
        //     }
        // }
    }
}