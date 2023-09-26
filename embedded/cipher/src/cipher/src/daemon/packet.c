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
#include "utils/err.h"

// Private include
#include "controller.h"
#include "packet.h"
#include "threads.h"

inline cipher_packet_fifo_item_t *alloc_packet_fifo_item(cipher_daemon_t *d, size_t payload_size) {

    cipher_packet_fifo_item_t *fifo_item = k_heap_aligned_alloc(&d->local_packets_heap, 8, sizeof(cipher_packet_fifo_item_t), K_FOREVER);
    if (!fifo_item) {
        return NULL;
    }

    fifo_item->packet.payload = k_heap_aligned_alloc(&d->local_packets_heap, 8, payload_size, K_FOREVER);
    if (!fifo_item->packet.payload) {
        k_heap_free(&d->local_packets_heap, fifo_item);
        return NULL;
    }

    return fifo_item;
}

inline void free_packet_fifo_item(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item) {
    if (fifo_item) {
        if (fifo_item->packet.payload) {
            k_heap_free(&d->local_packets_heap, fifo_item->packet.payload);
        }
        k_heap_free(&d->local_packets_heap, fifo_item);
    }
}
