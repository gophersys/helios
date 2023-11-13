#ifndef FIFO_H
#define FIFO_H

// Zephyr includes
#include "zephyr/kernel.h"

// Cipher includes
#include "config/daemon.h"
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/iface.h"
#include "daemon/ops.h"
#include "daemon/service.h"
#include "protocol/protocol.h"
#include "transport/transport.h"

typedef struct {
    uintptr_t __k_reserved;
    cipher_packet_t packet;
    cipher_iface_t *iface;
} cipher_packet_fifo_item_t;

typedef struct {
    uintptr_t __k_reserved;
    uint8_t *raw_packet;
    size_t packet_len;
} cipher_router_packet_fifo_item_t;

typedef struct {
    uintptr_t __k_reserved;
    cipher_rpc_entry_t *entry;
} cipher_local_rpc_request_fifo_item_t;

cipher_packet_fifo_item_t *alloc_packet_fifo_item(cipher_daemon_t *d, size_t payload_size);
void free_packet_fifo_item(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item);

cipher_router_packet_fifo_item_t *alloc_router_packet_fifo_item(cipher_daemon_t *d, size_t packet_size);
void free_router_packet_fifo_item(cipher_daemon_t *d, cipher_router_packet_fifo_item_t *fifo_item);

cipher_local_rpc_request_fifo_item_t *alloc_local_rpc_request_fifo_item(cipher_daemon_t *d, size_t req_size, size_t rep_size);
void free_local_rpc_request_fifo_item(cipher_daemon_t *d, cipher_local_rpc_request_fifo_item_t *fifo_item);

#endif