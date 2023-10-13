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
#include "protocol/protocol.h"
#include "utils/err.h"

// Private include
#include "controller.h"
#include "threads.h"

// TODO: For this file put all the heaps at the top of the allocation

inline cipher_packet_fifo_item_t *alloc_packet_fifo_item(cipher_daemon_t *d, size_t payload_size) {

    cipher_packet_fifo_item_t *fifo_item = k_heap_aligned_alloc(&d->local_packets_heap, 8, sizeof(cipher_packet_fifo_item_t), K_FOREVER);
    if (!fifo_item) {
        return NULL;
    }

    if (payload_size != 0) {
        fifo_item->packet.payload = k_heap_aligned_alloc(&d->local_packets_heap, 8, payload_size, K_FOREVER);
        if (!fifo_item->packet.payload) {
            k_heap_free(&d->local_packets_heap, fifo_item);
            return NULL;
        }
    }

    return fifo_item;
}

inline void free_packet_fifo_item(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item) {
    if (fifo_item) {
        if (fifo_item->packet.payload && fifo_item->packet.header.payload_len > 0) {
            k_heap_free(&d->local_packets_heap, fifo_item->packet.payload);
        }
        k_heap_free(&d->local_packets_heap, fifo_item);
    }
}

inline cipher_router_packet_fifo_item_t *alloc_router_packet_fifo_item(cipher_daemon_t *d, size_t packet_size) {

    cipher_router_packet_fifo_item_t *fifo_item = k_heap_aligned_alloc(&d->unrouted_packets_heap, 8, sizeof(cipher_router_packet_fifo_item_t), K_FOREVER);
    if (!fifo_item) {
        return NULL;
    }

    fifo_item->raw_packet = k_heap_aligned_alloc(&d->unrouted_packets_heap, 8, packet_size, K_FOREVER);
    if (!fifo_item->raw_packet) {
        k_heap_free(&d->unrouted_packets_heap, fifo_item);
        return NULL;
    }

    return fifo_item;
}

inline void free_router_packet_fifo_item(cipher_daemon_t *d, cipher_router_packet_fifo_item_t *fifo_item) {
    if (fifo_item) {
        if (fifo_item->raw_packet) {
            k_heap_free(&d->unrouted_packets_heap, fifo_item->raw_packet);
        }
        k_heap_free(&d->unrouted_packets_heap, fifo_item);
    }
}

inline cipher_local_rpc_request_fifo_item_t *alloc_local_rpc_request_fifo_item(cipher_daemon_t *d, size_t req_size, size_t rep_size) {
    cipher_local_rpc_request_fifo_item_t *fifo_item = k_heap_aligned_alloc(&d->rpc_heap, 8, sizeof(cipher_local_rpc_request_fifo_item_t), K_FOREVER);
    if (!fifo_item) {
        return NULL;
    }

    // fifo_item->entry->request = k_heap_aligned_alloc(&d->rpc_heap, 8, req_size, K_FOREVER);
    // if (!fifo_item->entry->request) {
    //     k_heap_free(&d->rpc_heap, fifo_item);
    //     return NULL;
    // }

    // fifo_item->entry->response = k_heap_aligned_alloc(&d->rpc_heap, 8, rep_size, K_FOREVER);
    // if (!fifo_item->entry.response) {
    //     k_heap_free(&d->rpc_heap, fifo_item->entry.request);
    //     k_heap_free(&d->rpc_heap, fifo_item);
    //     return NULL;
    // }

    return fifo_item;
}

inline void free_local_rpc_request_fifo_item(cipher_daemon_t *d, cipher_local_rpc_request_fifo_item_t *fifo_item) {
    if (fifo_item) {
        // if (fifo_item->entry.request) {
        //     k_heap_free(&d->rpc_heap, fifo_item->entry.request);
        // }
        // if (fifo_item->entry.response) {
        //     k_heap_free(&d->rpc_heap, fifo_item->entry.response);
        // }
        k_heap_free(&d->rpc_heap, fifo_item);
    }
}