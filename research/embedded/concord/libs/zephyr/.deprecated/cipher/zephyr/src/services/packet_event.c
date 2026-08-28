// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/tal.h>

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

    cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&d->sd.packets_event_queue, K_FOREVER);
    __ASSERT(fifo_item, "Null item on packets_event_queue, daemon %d", d->id);

    cipher_packet_t *packet = (cipher_packet_t *)&fifo_item->packet;
    cipher_payload_sd_broadcast_t *sd_payload = (cipher_payload_sd_broadcast_t *)packet->payload;

    cipher_service_entry_t service = {
        .local = false,
        .service = {
            .id = sd_payload->service_id,
            .allowed_hops = sd_payload->allowed_hops,
            .num_ops = sd_payload->num_ops,
        },
    };
    strcpy(service.service.name, sd_payload->name);

    cipher_service_end_point_t entry = {
        .device_id = packet->header.source_id,
        .iface = fifo_item->iface,
    };

    if (sd_payload->alive) {
        if (!registry_end_point_add_to_service(d, &service, &entry)) {
            ERROR("Unable to add end point to service for daemon %d", d->id);
        }

        // notify_interfaces(d, &service, fifo_item->iface);
    } else {
        registry_end_point_rm_from_service(d, &service, &entry);
    }

    free_packet_fifo_item(d, fifo_item);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Notify Interfaces
 *---------------------------------------------------------------------------------------------------*/

void notify_interfaces(cipher_daemon_t *d, cipher_service_entry_t *entry, cipher_iface_t *omit_iface) {

    if (entry->service.allowed_hops < 1) {
        // DBG("Service %d, device %d, on iface %d, daemon %d num_hops is 0, omitting advertisement",
        //     entry->service.id, entry->service.device_id, omit_iface->id, d->id);
        // TODO: fix me
        return;
    }

    send_service_update(d, entry, omit_iface, true);
}
