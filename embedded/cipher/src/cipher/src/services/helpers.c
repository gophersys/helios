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
void send_service_payload(cipher_daemon_t *d, cipher_iface_t *iface, cipher_payload_sd_t *sd_payload) {

    // Allocate memory for queue item
    cipher_packet_fifo_item_t *fifo_item = alloc_packet_fifo_item(d, sizeof(cipher_payload_sd_t));
    CHECK_MALLOC(fifo_item);

    cipher_packet_t *packet = &fifo_item->packet;

    // Set payload values
    cipher_payload_sd_t *payload = (cipher_payload_sd_t *)packet->payload;
    payload->alive = sd_payload->alive;
    strcpy(payload->name, sd_payload->name);
    payload->service_id = sd_payload->service_id;
    payload->num_ops = sd_payload->num_ops;
    payload->allowed_hops = sd_payload->allowed_hops;

    DBG("Sending SD payload, service %d, device %d, name %s to iface %d",
        payload->service_id, payload->device_id, payload->name, iface->id);

    k_fifo_put(&iface->decoded_packets_queue, packet);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                  Send Service Update
 *---------------------------------------------------------------------------------------------------*/
void send_service_update(cipher_daemon_t *d, cipher_service_entry_t *entry, cipher_iface_t *omit_iface, bool alive) {

    // Create service discovery payload
    cipher_payload_sd_t payload = {
        .alive = alive,
        .service_id = entry->service.service_id,
        .device_id = entry->service.device_id,
        .num_ops = entry->service.num_ops,
        .allowed_hops = entry->service.allowed_hops,
    };
    strcpy(payload.name, entry->service.name);

    // Send the broadcast on all interfaces
    for (uint8_t i = 0; i < ARRAY_SIZE(d->uplink_t_g); i++) {
        if (!d->uplink_t_g[i].iface.connected || (omit_iface && d->uplink_t_g[i].iface.id == omit_iface->id)) {
            continue;
        }
        send_service_payload(d, &d->uplink_t_g[i].iface, &payload);
    }

    for (uint8_t i = 0; i < ARRAY_SIZE(d->downlink_t_g); i++) {
        if (!d->downlink_t_g[i].iface.connected || (omit_iface && d->downlink_t_g[i].iface.id == omit_iface->id)) {
            continue;
        }
        send_service_payload(d, &d->downlink_t_g[i].iface, &payload);
    }
}
