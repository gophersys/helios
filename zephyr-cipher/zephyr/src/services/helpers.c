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
#include "utils/err.h"

// Private include
#include "interface.h"
#include "services.h"
#include "threads.h"

LOG_MODULE_DECLARE(sd, CONFIG_CK_CIPHER_SD_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                             Iface Disonnection Event
 *---------------------------------------------------------------------------------------------------*/
void send_service_payload(cipher_daemon_t *d, cipher_iface_t *iface, cipher_payload_sd_broadcast_t *sd_payload) {

    // Allocate memory for queue item
    cipher_packet_fifo_item_t *fifo_item = alloc_packet_fifo_item(d, sizeof(cipher_payload_sd_broadcast_t));
    CHECK_MALLOC(fifo_item);

    cipher_packet_t *packet = &fifo_item->packet;

    // Populate header
    packet->header.source_id = d->device_id;
    packet->header.destination_id = 0xFFFF;  // TODO: some common sense broadcast ID
    packet->header.service_id = 0;
    packet->header.operation_id = 0;
    packet->header.payload_len = sizeof(cipher_payload_sd_broadcast_t);
    packet->header.sequence_num = 0;
    packet->header.type = CIPHER_PACKET_TYPE_SD;
    packet->header.hop_count = 0;
    memset(&packet->header.flags, 0, sizeof(packet->header.flags));
    CIPHER_SET_FLAG(packet->header.flags, CIPHER_FLAG_SD_BROADCAST);

    // Set payload values
    memcpy(packet->payload, sd_payload, sizeof(cipher_payload_sd_broadcast_t));

    DBG("Sending SD payload, service %d, device %d, name %s to iface %d",
        sd_payload->service_id, sd_payload->device_id, sd_payload->name, iface->id);

    k_fifo_put(&iface->decoded_packets_queue, fifo_item);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                  Send Service Update
 *---------------------------------------------------------------------------------------------------*/
void send_service_update(cipher_daemon_t *d, cipher_service_entry_t *entry, cipher_iface_t *omit_iface, bool alive) {

    // Create service discovery payload
    cipher_payload_sd_broadcast_t payload = {
        .alive = alive,
        // .service_id = entry->service.service_id,
        // .device_id = entry->service.device_id, //TODO: me
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
