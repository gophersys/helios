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
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Broadcast to all connected interfaces service discovery updates from disconencted iface
 *
 * This function loops through each service in the registry, and for each connected interface of the
 * daemon, it will send a service discovery update for the services offered by the disconnected iface
 *
 * @param d The daemon
 * @param disconn_iface The disconnected interface
 */
static void update_affected_interfaces(cipher_daemon_t *d, cipher_iface_t *disconn_iface);

/**
 * @brief Remove all services in the registry who's interface is the one that disconnected
 *
 * @param d The daemon
 * @param disconn_iface The disconnected interface
 */
static void update_registry(cipher_daemon_t *d, cipher_iface_t *disconn_iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                             Iface Disonnection Event
 *---------------------------------------------------------------------------------------------------*/

void handle_iface_disconn_event(cipher_daemon_t *d) {

    cipher_iface_t *disconn_iface = k_fifo_get(&d->sd_iface_disconn_queue, K_FOREVER);
    __ASSERT(disconn_iface, "Null item on sd_iface_disconn_queue, daemon %d", d->id);
    __ASSERT(!disconn_iface->connected, "Expected iface %d for daemon %d to be disconencted", disconn_iface->id, d->id);

    DBG("Iface %d disconnected!, advertising updates", disconn_iface->id);

    update_affected_interfaces(d, disconn_iface);
    update_registry(d, disconn_iface);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                  Affected Interfaces
 *---------------------------------------------------------------------------------------------------*/

static void update_affected_interfaces(cipher_daemon_t *d, cipher_iface_t *disconn_iface) {

    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *entry = &d->service_registry.entries[i];

        // Skip entry if it does NOT belong to the disconnected interface
        if (entry->iface->id != disconn_iface->id) {
            continue;
        }

        // Skip entry if it cannot be routed to other devices
        if (entry->service.allowed_hops < 1) {
            continue;
        }

        // Create service discovery payload
        cipher_payload_sd_t payload = {
            .alive = false,  // Indicates the service is no longer available
            .service_id = entry->service.service_id,
            .device_id = entry->service.device_id,
            .num_ops = entry->service.num_ops,
            .allowed_hops = entry->service.allowed_hops,
        };
        strcpy(payload.name, entry->service.name);

        // Send the broadcast on all interfaces
        for (uint8_t i = 0; i < ARRAY_SIZE(d->uplink_t_g); i++) {
            if (d->uplink_t_g[i].iface.connected) {
                send_service_payload(d, &d->uplink_t_g[i].iface, &payload);
            }
        }

        for (uint8_t i = 0; i < ARRAY_SIZE(d->downlink_t_g); i++) {
            if (d->downlink_t_g[i].iface.connected) {
                send_service_payload(d, &d->downlink_t_g[i].iface, &payload);
            }
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Registry Update
 *---------------------------------------------------------------------------------------------------*/
static void update_registry(cipher_daemon_t *d, cipher_iface_t *disconn_iface) {

    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *entry = &d->service_registry.entries[i];

        // Skip entry if it does NOT belong to the disconnected interface
        if (entry->iface->id != disconn_iface->id) {
            continue;
        }

        if (!service_unregister(d, entry)) {
            ERROR("Service should have been in registry");
        }
    }
}