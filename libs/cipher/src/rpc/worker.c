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

static void handle_entry_not_found(cipher_daemon_t *d, cipher_packet_t *packet);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Worker
 *---------------------------------------------------------------------------------------------------*/
void cipher_rpc_worker_thread(void *arg0, void *arg1, void *arg2) {
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    cipher_rpc_worker_thread_t *worker_info = (cipher_rpc_worker_thread_t *)arg1;

    while (true) {
        worker_info->in_use = false;

        // Get work item
        cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&worker_info->packets_event_queue, K_FOREVER);
        worker_info->in_use = true;

        LOG("RPC thread received work");

        cipher_packet_t *packet = &fifo_item->packet;

        // Find op in localhost
        cipher_ops_entry_t *entry = find_op_in_registry(d, &packet->header);
        if (!entry) {
            handle_entry_not_found(d, packet);
            free_packet_fifo_item(d, fifo_item);
            continue;
        }

        if (entry->op.rpc.supports_parallelism) {
            WARN("Parallelism is not yet supported by RPC thread, executing serialized");
        }

        // Allocate memory for the request and response types
        void *request_memory = NULL;
        void *response_memory = NULL;
        if (entry->op.rpc.request_size > 0) {
            request_memory = k_heap_aligned_alloc(&d->rpc.heap, 8, entry->op.rpc.request_size, K_FOREVER);
            CHECK_MALLOC(request_memory);
            memcpy(request_memory, fifo_item->packet.payload, fifo_item->packet.header.payload_len);
        }

        if (entry->op.rpc.response_size > 0) {
            response_memory = k_heap_aligned_alloc(&d->rpc.heap, 8, entry->op.rpc.response_size, K_FOREVER);
            CHECK_MALLOC(response_memory);
        }

        // Call the handler
        cipher_rpc_err_t err = entry->op.rpc.handler(request_memory, response_memory);

        void *payload = NULL;
        size_t payload_len = 0;
        cipher_flags_e resp_packet_flag = CIPHER_FLAG_RPC_ERR;

        // Allocate response packet
        cipher_packet_fifo_item_t *resp_fifo_item = alloc_packet_fifo_item(d, entry->op.rpc.response_size);
        CHECK_MALLOC(resp_fifo_item);

        // Create the payload based on the RPC result
        if (err != CIPHER_RPC_ERR_OK) {
            resp_packet_flag = CIPHER_FLAG_RPC_ERR;
            cipher_payload_rpc_err_t err_payload = {
                .err = err,
            };
            payload = &err_payload;
            payload_len = sizeof(err_payload);
        } else {
            resp_packet_flag = CIPHER_FLAG_RPC_RESPONSE;
            memcpy(resp_fifo_item->packet.payload, response_memory, entry->op.rpc.response_size);
            payload_len = entry->op.rpc.response_size;
        }

        k_heap_free(&d->rpc.heap, request_memory);
        k_heap_free(&d->rpc.heap, response_memory);

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
        memset(&resp_packet->header.flags, 0, sizeof(resp_packet->header.flags));
        CIPHER_SET_FLAG(resp_packet->header.flags, resp_packet_flag);

        // We don't need the original memory anymore
        free_packet_fifo_item(d, fifo_item);

        // Send decoded packet to the right interface
        cipher_iface_t *iface = registry_get_iface(d, resp_packet->header.destination_id);
        k_fifo_put(&iface->decoded_packets_queue, resp_fifo_item);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Entry not found
 *---------------------------------------------------------------------------------------------------*/

static void handle_entry_not_found(cipher_daemon_t *d, cipher_packet_t *packet) {
    WARN("Host %d requested local RPC %d, for service %d, but entry was not found in localhost",
         packet->header.source_id, packet->header.operation_id, packet->header.service_id);

    cipher_payload_rpc_err_t err_payload = {
        .err = CIPHER_RPC_ERR_NOT_FOUND,
    };

    cipher_packet_fifo_item_t *fifo_item = alloc_packet_fifo_item(d, sizeof(cipher_payload_rpc_err_t));
    CHECK_MALLOC(fifo_item);

    // Copy payload
    memcpy(&fifo_item->packet.payload, &err_payload, sizeof(cipher_payload_rpc_err_t));

    // Populate the header
    cipher_header_t *header = &fifo_item->packet.header;
    header->source_id = d->device_id;
    header->destination_id = packet->header.source_id;
    header->service_id = packet->header.service_id;
    header->operation_id = packet->header.operation_id;
    header->payload_len = sizeof(cipher_payload_rpc_err_t);
    header->sequence_num = 0;
    header->type = CIPHER_PACKET_TYPE_RPC;
    header->hop_count = 0;
    memset(&header->flags, 0, sizeof(header->flags));
    CIPHER_SET_FLAG(header->flags, CIPHER_FLAG_RPC_ERR);

    // Send decoded packet to the right interface
    cipher_iface_t *iface = registry_get_iface(d, header->destination_id);
    if (!iface) {
        WARN("Could not find an iface for device %d", header->destination_id);
        return;
    }

    k_fifo_put(&iface->decoded_packets_queue, fifo_item);
}
