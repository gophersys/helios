// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "protocol/protocol.h"
#include "protocol/serdes.h"
#include "transport/transport.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "rpc.h"
#include "threads.h"

LOG_MODULE_DECLARE(rpc);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Assert
 *---------------------------------------------------------------------------------------------------*/
void handle_rpc_timeout_event(struct k_timer* timer_id) {
    // If timer expires we have to:
    // Signal the remote host to cancel the RPC
    // Unblock the semaphore of the waiting function and chekc that it was taken to unallocate packet
    // Remove this rpc request from the active list
}

void handle_local_rpc_request_event(cipher_daemon_t* d) {
    cipher_local_rpc_request_fifo_item_t* fifo_item = k_fifo_get(&d->localhost_rpc_queue, K_NO_WAIT);
    __ASSERT(fifo_item, "Null item on localhost_rpc_queue, daemon %d", d->id);

    cipher_rpc_entry_t* entry = fifo_item->entry;
    cipher_rpc_user_info_t* info = entry->user_info;

    // Find remote service with RPC
    cipher_iface_t* rpc_iface = cipher_get_iface_by_device_id(d, info->device_id);
    if (!rpc_iface) {
        info->error = CIPHER_RPC_ERR_NOT_FOUND;
        k_sem_give(&entry->await_sem);
        return;
    }

    // Add entry to the RPC registry
    for (size_t i = 0; i < ARRAY_SIZE(d->rpc_registry.entries); i++) {
        entry = d->rpc_registry.entries[i];

        if (entry->_used) {
            continue;
        }
        // TODO: Add entry to the list of RPC entries
    }

    // Allocate a fifo packet
    cipher_packet_fifo_item_t* packet_fifo_item = alloc_packet_fifo_item(d, entry->request_size);
    CHECK_MALLOC(packet_fifo_item);

    // Populate header
    cipher_packet_t* req_packet = &packet_fifo_item->packet;
    req_packet->header.source_id = d->device_id;
    req_packet->header.destination_id = entry->user_info->device_id;
    req_packet->header.service_id = entry->service_id;
    req_packet->header.operation_id = entry->op_id;
    req_packet->header.payload_len = entry->request_size;
    req_packet->header.sequence_num = 0;
    req_packet->header.type = CIPHER_PACKET_TYPE_RPC;
    req_packet->header.hop_count = 0;
    CIPHER_SET_FLAG(req_packet->header.flags, CIPHER_FLAG_RPC_REQUEST);

    // Send decoded packet to the right interface
    cipher_iface_t* iface = cipher_get_iface_by_device_id(d, req_packet->header.destination_id);
    k_fifo_put(&iface->decoded_packets_queue, fifo_item);

    // Set a timeout event for this RPC
    k_timer_init(&entry->timer, handle_rpc_timeout_event, NULL);
    k_timer_start(&entry->timer, K_MSEC(info->timeout_ms), K_NO_WAIT);
}