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
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

void assert_packet(cipher_daemon_t *d, cipher_packet_t *packet);

static void handle_rpc_response_packet(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item);
static void handle_rpc_request_packet(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Event Handler
 *---------------------------------------------------------------------------------------------------*/
void handle_rpc_packet(cipher_daemon_t *d) {
    cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&d->rpc_packet_queue, K_FOREVER);
    __ASSERT(fifo_item, "Null item on rpc_packet_queue, daemon %d", d->id);

    cipher_packet_t *packet = &fifo_item->packet;

    if (CIPHER_IS_FLAG_SET(packet->header.flags, CIPHER_FLAG_RPC_REQUEST)) {
        handle_rpc_request_packet(d, fifo_item);
    } else if (CIPHER_IS_FLAG_SET(packet->header.flags, CIPHER_FLAG_RPC_RESPONSE) ||
               CIPHER_IS_FLAG_SET(packet->header.flags, CIPHER_FLAG_RPC_ERR)) {
        handle_rpc_response_packet(d, fifo_item);
    } else {
        ERROR("Expected at least 1 flag to be set in RPC packet");
    }
}

static void handle_rpc_request_packet(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item) {
    cipher_packet_t *packet = &fifo_item->packet;

    // Find the localhost operation
    cipher_ops_entry_t *entry = find_op_in_registry(d, &packet->header);
    if (!entry) {
        WARN("Host %d requested local RPC %d, for service %d, but entry was not found locally",
             packet->header.source_id, packet->header.operation_id, packet->header.service_id);

        free_packet_fifo_item(d, fifo_item);
        return;
    }

    if (entry->op.rpc.supports_parallelism) {
        WARN("Parallelism is not yet supported by RPC thread, executing serialized");
    }

    void *request_memory = k_heap_alloc(&d->rpc_heap, entry->op.rpc.request_size, K_FOREVER);
    CHECK_MALLOC(request_memory);
    void *response_memory = k_heap_alloc(&d->rpc_heap, entry->op.rpc.response_size, K_FOREVER);
    CHECK_MALLOC(response_memory);

    // Call the handler
    cipher_rpc_err_t err = entry->op.rpc.handler(request_memory, response_memory);

    void *payload = NULL;
    size_t payload_len = 0;
    cipher_flags_e resp_packet_flag = CIPHER_FLAG_RPC_RESPONSE;

    // Create the payload based on the RPC result
    if (err != CIPHER_RPC_ERR_OK) {
        resp_packet_flag = CIPHER_FLAG_RPC_ERR;
        cipher_payload_rpc_err_t err_payload = {
            .err = err,
        };
        payload = &err_payload;
        payload_len = sizeof(err_payload);
    } else {
        memcpy(&fifo_item->packet.payload, response_memory, entry->op.rpc.response_size);
        payload_len = sizeof(entry->op.rpc.response_size);
    }

    k_heap_free(&d->ctrl_events_heap, request_memory);
    k_heap_free(&d->ctrl_events_heap, response_memory);

    // Allocate response packet
    cipher_packet_fifo_item_t *resp_fifo_item = alloc_packet_fifo_item(d, entry->op.rpc.response_size);
    CHECK_MALLOC(fifo_item);

    // Populate header
    cipher_packet_t *resp_packet = &resp_fifo_item->packet;
    resp_packet->header.source_id = d->device_id;
    resp_packet->header.destination_id = packet->header.source_id;
    resp_packet->header.service_id = packet->header.service_id;
    resp_packet->header.operation_id = packet->header.operation_id;
    resp_packet->header.payload_len = payload_len;
    resp_packet->header.sequence_num = 0;
    resp_packet->header.type = CIPHER_PACKET_TYPE_RPC;
    resp_packet->header.hop_count = 0;
    CIPHER_SET_FLAG(resp_packet->header.flags, resp_packet_flag);

    // Send decoded packet to the right interface
    cipher_iface_t *iface = registry_get_iface(d, resp_packet->header.destination_id);
    k_fifo_put(&iface->decoded_packets_queue, resp_fifo_item);
}

static void handle_rpc_response_packet(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item) {
    // Find the RPC entry
    cipher_rpc_entry_t *entry = cipher_rpc_get_entry(d, fifo_item->packet.header.service_id, fifo_item->packet.header.operation_id);
    if (!entry) {
        WARN("Unknown RPC response message");
        return;
    }

    // Stop the timeout timer
    k_timer_stop(&entry->timer);

    // Find remote service with RPC
    cipher_rpc_user_info_t *info = entry->user_info;
    info->error = CIPHER_RPC_ERR_OK;
    k_sem_give(&entry->await_sem);

    // Remove RPC entry
    cipher_rpc_entry_unregister(d, entry);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Assert
 *---------------------------------------------------------------------------------------------------*/
void assert_packet(cipher_daemon_t *d, cipher_packet_t *packet) {
    __ASSERT(packet->header.type == CIPHER_PACKET_TYPE_RPC, "Expected packet type %d, got %d, daemon %d",
             CIPHER_PACKET_TYPE_RPC, packet->header.type, d->id);

    __ASSERT(packet->header.destination_id == d->device_id, "Expected destination id %d to match localhost %d, daemon %d",
             packet->header.destination_id, d->device_id, d->id);
}