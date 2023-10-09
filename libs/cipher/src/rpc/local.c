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
#include "controller.h"
#include "interface.h"
#include "rpc.h"
#include "threads.h"

LOG_MODULE_DECLARE(rpc);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Assert
 *---------------------------------------------------------------------------------------------------*/
void handle_rpc_timeout_event(struct k_timer* timer) {

    cipher_daemon_t* d = k_timer_user_data_get(timer);

    rpc_event_opt_timer_expired_t timer_expired_opts = {
        .timer = timer,
    };

    rpc_event_t event = {
        .type = RPC_EVENT_TYPE_TIMER_EXPIRED,
        .options = &timer_expired_opts,
    };

    cipher_rpc_add_event(d, &event);
}

void handle_local_request(cipher_daemon_t* d) {
    cipher_local_rpc_request_fifo_item_t* fifo_item = k_fifo_get(&d->localhost_rpc_queue, K_NO_WAIT);
    __ASSERT(fifo_item, "Null item on localhost_rpc_queue, daemon %d", d->id);

    cipher_rpc_entry_t* entry = fifo_item->entry;
    cipher_rpc_user_info_t* info = entry->user_info;

    if (!cipher_rpc_entry_register(d, entry)) {
        ERROR("Unable to register RPC with daemon");
    }

    // Find remote service with RPC
    cipher_iface_t* rpc_iface = registry_get_iface(d, info->device_id);
    if (!rpc_iface) {
        info->error = CIPHER_RPC_ERR_NOT_FOUND;
        k_sem_give(&entry->await_sem);
        return;
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
    k_fifo_put(&rpc_iface->decoded_packets_queue, packet_fifo_item);

    // Set a timeout event for this RPC
    k_timer_init(&entry->timer, handle_rpc_timeout_event, NULL);
    k_timer_user_data_set(&entry->timer, d);
    k_timer_start(&entry->timer, K_MSEC(info->timeout_ms), K_NO_WAIT);
}