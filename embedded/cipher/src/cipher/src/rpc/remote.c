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
#include "rpc.h"
#include "threads.h"

LOG_MODULE_DECLARE(rpc);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/

#define EVENT_NUM 2
#define LOCAL_RPC_EVENT 0
#define REMOTE_RPC_EVENT 1

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

void assert_packet(cipher_daemon_t *d, cipher_packet_t *packet);
cipher_ops_entry_t *find_op_in_registry(cipher_daemon_t *d, cipher_packet_t *packet);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Event Handler
 *---------------------------------------------------------------------------------------------------*/
void handle_remote_rpc_request_event(cipher_daemon_t *d) {
    cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&d->rpc_packet_queue, K_FOREVER);
    __ASSERT(fifo_item, "Null item on rpc_packet_queue, daemon %d", d->id);

    cipher_packet_t *req_packet = &fifo_item->packet;
    assert_packet(d, req_packet);

    // Find the localhost operation
    cipher_ops_entry_t *entry = find_op_in_registry(d, req_packet);
    if (!entry) {
        WARN("Host %d requested local RPC %d, for service %d, but entry was not found locally",
             req_packet->header.source_id, req_packet->header.operation_id, req_packet->header.service_id);
    } else {

        if (entry->op.rpc.supports_parallelism) {
            WARN("Parallelism is not yet supported by RPC thread, executing serialized");
        }

        void *request_memory = k_heap_alloc(&d->rpc_events_heap, entry->op.rpc.request_size, K_FOREVER);
        CHECK_MALLOC(request_memory);
        void *response_memory = k_heap_alloc(&d->rpc_events_heap, entry->op.rpc.response_size, K_FOREVER);
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
        cipher_packet_fifo_item_t *fifo_item = alloc_packet_fifo_item(d, entry->op.rpc.response_size);
        CHECK_MALLOC(fifo_item);

        // Populate header
        cipher_packet_t *resp_packet = &fifo_item->packet;
        resp_packet->header.source_id = d->device_id;
        resp_packet->header.destination_id = req_packet->header.source_id;
        resp_packet->header.service_id = req_packet->header.service_id;
        resp_packet->header.operation_id = req_packet->header.operation_id;
        resp_packet->header.payload_len = payload_len;
        resp_packet->header.sequence_num = 0;
        resp_packet->header.type = CIPHER_PACKET_TYPE_RPC;
        resp_packet->header.hop_count = 0;
        CIPHER_SET_FLAG(resp_packet->header.flags, resp_packet_flag);

        // Send decoded packet to the right interface
        cipher_iface_t *iface = cipher_get_iface_by_device_id(d, resp_packet->header.destination_id);
        k_fifo_put(&iface->decoded_packets_queue, fifo_item);
    }

    free_packet_fifo_item(d, fifo_item);
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

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Helper
 *---------------------------------------------------------------------------------------------------*/
cipher_ops_entry_t *find_op_in_registry(cipher_daemon_t *d, cipher_packet_t *packet) {

    // First find the service
    cipher_service_entry_t *entry = NULL;
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *e = &d->service_registry.entries[i];

        // Ensure its a local service
        if (!e->local) {
            continue;
        }

        // Find the matching service id
        if (e->service.service_id == packet->header.service_id) {
            entry = e;
            break;
        }
    }

    // Then find the op in the service
    if (entry) {

        cipher_ops_rpc_t *found_rpc = NULL;
        for (size_t i = 0; i < entry->service.num_ops; i++) {

            cipher_ops_entry_t *op = &entry->service.ops[i];

            if (op->id != packet->header.operation_id) {
                continue;
            }

            return op;
        }
    }
}