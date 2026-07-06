// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/cipher/serdes/decode.h>
#include <corekinect/cipher/serdes/encode.h>
#include <corekinect/cipher/serdes/print.h>
#include <corekinect/cipher/serdes/types.h>
#include <corekinect/iface/iface.h>

#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
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
void handle_net_packet_event(cipher_daemon_t *d) {
    cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&d->rpc.packets_event_queue, K_FOREVER);
    __ASSERT(fifo_item, "Null item on packets_event_queue, daemon %d", d->id);

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

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Request
 *---------------------------------------------------------------------------------------------------*/

static void handle_rpc_request_packet(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item) {

    bool work_assigned = false;
    for (size_t i = 0; i < ARRAY_SIZE(d->rpc.workers); i++) {

        cipher_rpc_worker_thread_t *worker = &d->rpc.workers[i];
        if (worker->in_use) {
            continue;
        }

        k_fifo_put(&worker->packets_event_queue, fifo_item);

        work_assigned = true;
        break;
    }

    if (!work_assigned) {
        ERROR("No worker threads available for RPC");
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Response
 *---------------------------------------------------------------------------------------------------*/
static void handle_rpc_response_packet(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item) {
    // Find the RPC entry
    cipher_registry_rpc_entry_t *entry = cipher_rpc_get_entry(d, fifo_item->packet.header.service_id, fifo_item->packet.header.operation_id);
    if (!entry) {
        WARN("Unknown RPC response message");
        return;
    }

    // Stop the timeout timer
    k_timer_stop(&entry->timer);

    // Copy the payload
    memcpy(entry->response, fifo_item->packet.payload, entry->response_size);

    // Find remote service with RPC
    cipher_rpc_user_info_t *info = entry->user_info;
    info->error = CIPHER_RPC_ERR_OK;
    k_sem_give(&entry->await_sem);

    // Remove RPC entry
    cipher_rpc_entry_unregister(d, entry);

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