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
#include "threads.h"

LOG_MODULE_REGISTER(rpc, RPC_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

void assert_packet(cipher_daemon_t *d, cipher_packet_t *packet) {
    __ASSERT(packet->header.type == CIPHER_PACKET_TYPE_RPC, "Expected packet type %d, got %d, daemon %d",
             CIPHER_PACKET_TYPE_RPC, packet->header.type, d->id);

    __ASSERT(packet->header.destination_id == d->device_id, "Expected destination id %d to match localhost %d, daemon %d",
             packet->header.destination_id, d->device_id, d->id);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
void cipher_rpc_thread(void *arg0, void *arg1, void *arg2) {
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    while (true) {
        cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&d->rpc_packet_queue, K_FOREVER);
        __ASSERT(fifo_item, "Null item on rpc_packet_queue, daemon %d", d->id);

        // Get the header from the packet
        cipher_packet_t *packet = &fifo_item->packet;
        assert_packet(d, packet);

        // Find the service of the RPC
        cipher_service_entry_t *rpc_service = NULL;
        for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

            cipher_service_entry_t *entry = &d->service_registry.entries[i];

            // Ensure its a local service
            if (!entry->local) {
                continue;
            }

            // Find the matching service id
            if (entry->service.service_id == packet->header.service_id) {
                rpc_service = entry;
                break;
            }
        }

        if (rpc_service) {
            // Find the RPC in the service
            cipher_op_rpc_t *found_rpc = NULL;
            for (size_t i = 0; i < ARRAY_SIZE(rpc_service->service.ops); i++) {

                cipher_op_union_t *op = rpc_service->service.ops[i];

                // Ensure that its an RPC
                if (op->type != CIPHER_OP_TYPE_RPC) {
                    continue;
                }

                // Ensure its the right RPC
                cipher_op_rpc_t *rpc_entry = &op->op.rpc;
                if (rpc_entry->base.op_id != packet->header.operation_id) {
                    continue;
                }

                found_rpc = rpc_entry;
                break;
            }

            if (found_rpc) {
                void *request_memory = k_heap_alloc(&d->ctrl_events_heap, found_rpc->request_size, K_FOREVER);
                void *response_memory = k_heap_alloc(&d->ctrl_events_heap, found_rpc->response_size, K_FOREVER);

                void *returned_reponse = found_rpc->handler(request_memory);

                k_heap_free(&d->ctrl_events_heap, request_memory);
                k_heap_free(&d->ctrl_events_heap, response_memory);
            }
        } else {
            ERROR("RPC not found");
        }

        free_packet_fifo_item(d, fifo_item);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/
