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
void send_service_broadcast(cipher_daemon_t *d, cipher_iface_t *iface, cipher_payload_sd_t *sd_payload) {
    // Allocate memory for queue item
    cipher_packet_fifo_t *fifo_item = k_heap_aligned_alloc(&d->local_packets_heap, 8, sizeof(cipher_packet_fifo_t), K_FOREVER);
    CHECK_MALLOC(fifo_item);

    // Allocate memory for packet payload
    cipher_packet_t *packet = &fifo_item->packet;
    packet->payload = k_heap_aligned_alloc(&d->local_packets_heap, 8, sizeof(cipher_payload_sd_t), K_FOREVER);
    CHECK_MALLOC(packet->payload);

    // Set payload values
    cipher_payload_sd_t *payload = (cipher_payload_sd_t *)packet->payload;
    payload->alive = sd_payload->alive;
    payload->id = sd_payload->id;
    payload->num_ops = sd_payload->num_ops;

    // Add to interface's send queue
    DBG("Sending service discovery payload to iface %d", iface->id);
    k_fifo_put(&iface->decoded_packets_queue, packet);
}