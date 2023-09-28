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
 * @brief Notify all affected interfaces of the new entry, expect for the one it was received on
 *
 * If the number of allowed hops in the service is more than 0, the daemon will notify all the connected
 * interfaces to it about the new service
 *
 * @param d The daemon
 * @param entry The entry to advertise
 * @param omit_iface The interface to omit the advertisement to
 */
void notify_interfaces(cipher_daemon_t *d, cipher_service_entry_t *entry, cipher_iface_t *omit_iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Packet Event
 *---------------------------------------------------------------------------------------------------*/
void handle_sd_packet_event(cipher_daemon_t *d) {

    cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&d->sd_packet_queue, K_FOREVER);
    __ASSERT(fifo_item, "Null item on sd_packet_queue, daemon %d", d->id);

    cipher_packet_t *packet = (cipher_packet_t *)&fifo_item->packet;
    cipher_payload_sd_t *sd_payload = (cipher_payload_sd_t *)packet->payload;

    // Crate a potential entry to enter to our registry
    cipher_service_entry_t potential_entry = {
        .local = false,
        .iface = fifo_item->iface,
        .service = {
            .service_id = sd_payload->service_id,
            .device_id = sd_payload->device_id,
            .num_ops = sd_payload->num_ops,
            .allowed_hops = sd_payload->allowed_hops,
        },
    };
    strcpy(potential_entry.service.name, sd_payload->name);

    // Update registry
    if (!cipher_service_exists(d, &potential_entry)) {

        // If the service is alive, register and update
        if (sd_payload->alive) {

            if (!cipher_service_register(d, &potential_entry)) {
                ERROR("Unable to register service %d, for daemon %d", potential_entry.service.service_id, d->id);
            }

            notify_interfaces(d, &potential_entry, fifo_item->iface);
        } else {
            if (!cipher_service_unregister(d, &potential_entry)) {
                ERROR("Unable to register service %d, for daemon %d", potential_entry.service.service_id, d->id);
            }
        }
    }

    free_packet_fifo_item(d, fifo_item);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Notify Interfaces
 *---------------------------------------------------------------------------------------------------*/

void notify_interfaces(cipher_daemon_t *d, cipher_service_entry_t *entry, cipher_iface_t *omit_iface) {

    if (entry->service.allowed_hops < 1) {
        DBG("Service %d, device %d, on iface %d, daemon %d num_hops is 0, omitting advertisement",
            entry->service.service_id, entry->service.device_id, omit_iface->id, d->id);

        return;
    }

    // Create service discovery payload
    cipher_payload_sd_t payload = {
        .alive = true,  // Indicates the service is available
        .service_id = entry->service.service_id,
        .device_id = entry->service.device_id,
        .num_ops = entry->service.num_ops,
        .allowed_hops = entry->service.allowed_hops,
    };
    strcpy(payload.name, entry->service.name);

    // Send the broadcast on all interfaces
    for (uint8_t i = 0; i < ARRAY_SIZE(d->uplink_t_g); i++) {
        if (d->uplink_t_g[i].iface.connected == false) {
            continue;
        }
        if (d->uplink_t_g[i].iface.id == omit_iface->id) {
            continue;
        }

        send_service_payload(d, &d->uplink_t_g[i].iface, &payload);
    }

    for (uint8_t i = 0; i < ARRAY_SIZE(d->downlink_t_g); i++) {
        if (d->downlink_t_g[i].iface.connected == false) {
            continue;
        }
        if (d->downlink_t_g[i].iface.id == omit_iface->id) {
            continue;
        }

        send_service_payload(d, &d->downlink_t_g[i].iface, &payload);
    }
}
