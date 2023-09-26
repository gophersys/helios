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
 *                                                                             Iface Disonnection Event
 *---------------------------------------------------------------------------------------------------*/

void handle_iface_disconn_event(cipher_daemon_t *d) {
    cipher_iface_t *disconn_iface = k_fifo_get(&d->sd_iface_disconn_queue, K_FOREVER);

    __ASSERT(disconn_iface, "Null item on sd_iface_disconn_queue, daemon %d", d->id);
    __ASSERT(!disconn_iface->connected, "Expected iface %d for daemon %d to be disconencted", disconn_iface->id, d->id);

    DBG("iface %d disconnected!, advertising all services", disconn_iface->id);

    // For each registered service in our registry
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {
        // If the entry's iface is the one that just disconnected
        if (d->service_registry.entries[i].iface->id == disconn_iface->id) {
            // Create the service discovery payload
            cipher_payload_sd_t payload = {
                .alive = false,
                .id = d->service_registry.entries[i].service_id,
                .num_ops = 0,
            };

            // Tell every other uplink interface about it
            for (uint8_t i = 0; i < CONFIG_UP_LINK_IFACE_COUNT; i++) {
                cipher_iface_t *adv_iface = &d->uplink_t_g[i].iface;
                if (adv_iface->connected)
                    send_service_broadcast(d, adv_iface, &payload);
            }

            // Tell every other downlink interface about it
            for (uint8_t i = 0; i < CONFIG_DOWN_LINK_IFACE_COUNT; i++) {
                cipher_iface_t *adv_iface = &d->downlink_t_g[i].iface;
                if (adv_iface->connected) {
                    if (adv_iface->connected)
                        send_service_broadcast(d, adv_iface, &payload);
                }
            }
        }
    }

    // Update registry
}
