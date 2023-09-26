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
#include "protocol/serdes.h"
#include "transport/transport.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "packet.h"
#include "threads.h"

LOG_MODULE_DECLARE(iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
static void recv_ingress_packet(cipher_daemon_t *d, cipher_iface_t *iface, uint8_t *recv_buffer,
                                uint16_t bytes_recv);

static void process_complete_packet(cipher_daemon_t *d, cipher_iface_t *iface, cipher_header_t *header,
                                    uint8_t *recv_buffer, uint16_t bytes_recv);

static void process_incomplete_packet(cipher_daemon_t *d, cipher_iface_t *iface, cipher_header_t *header,
                                      uint8_t *recv_buffer, uint16_t bytes_recv);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Recv Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_interface_recv_thread(void *arg0, void *arg1, void *arg2) {
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    cipher_iface_t *iface = (cipher_iface_t *)arg1;

    __ASSERT(d != NULL, "null daemon passed to thread");
    __ASSERT(iface != NULL, "null interface passed to thread");

    tal_config_t *interface_cfg = iface->cfg;

    while (1) {
        // Wait until the iface is connected
        k_sem_take(&iface->conn_sem, K_FOREVER);  // TODO: handle timeout
        LOG("Recv thread for iface %d unblocked", iface->id);

        bool timeout = false;
        while (iface->connected) {
            bool conn_closed = false;
            const size_t buffer_size = CONFIG_MAX_PAYLOAD_SIZE;
            uint16_t bytes_recv = 0;
            uint8_t *recv_buffer = k_heap_alloc(&d->net_packets_heap, CONFIG_MAX_PAYLOAD_SIZE, K_FOREVER);
            CHECK_MALLOC(recv_buffer);

            if (!tal_recv(interface_cfg, recv_buffer, buffer_size, &bytes_recv, &conn_closed, &timeout)) {
                if (timeout)
                    handle_iface_timeout(d, iface, __func__);
                else if (conn_closed)
                    handle_iface_disconnect(d, iface, __func__);
                else
                    ERROR("Recv error on iface %d, daemon %d", iface->id, d->id);  // TODO: iface error

                k_heap_free(&d->net_packets_heap, recv_buffer);
                break;
            }

            recv_ingress_packet(d, iface, recv_buffer, bytes_recv);
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Ingress
 *---------------------------------------------------------------------------------------------------*/
static void recv_ingress_packet(cipher_daemon_t *d, cipher_iface_t *iface, uint8_t *recv_buffer,
                                uint16_t bytes_recv) {
    if (bytes_recv < sizeof(cipher_header_t)) {
        WARN("Dropping unexpected packet, len: %d, iface %d, daemon %d", bytes_recv, iface->id, d->id);
        return;
    }

    // Unpack header so we can get the payload length to allocate a buffer
    cipher_header_t header = {0};
    serdes_error_t err = serdes_decode_header(recv_buffer, bytes_recv, &header);
    if (err != SERDES_ERROR_OK)
        handle_iface_error(d, iface, IFACE_ERROR_SERDES, &err, sizeof(err));

    // cipher_print_header(&header); // Uncommnet to see raw header

    if (header.payload_len == (bytes_recv - sizeof(header)))
        process_complete_packet(d, iface, &header, recv_buffer, bytes_recv);
    else
        process_incomplete_packet(d, iface, &header, recv_buffer, bytes_recv);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Ingress
 *---------------------------------------------------------------------------------------------------*/
static void process_complete_packet(cipher_daemon_t *d, cipher_iface_t *iface, cipher_header_t *header,
                                    uint8_t *recv_buffer, uint16_t bytes_recv) {
    // Process remote packet
    if (header->destination_id != d->device_id) {
        // Copy unrouted packet into daemon's heap pool
        void *unrouted_packet = k_heap_alloc(&d->unrouted_packets_heap, bytes_recv, K_FOREVER);
        CHECK_MALLOC(unrouted_packet);
        memcpy(unrouted_packet, recv_buffer, bytes_recv);

        k_heap_free(&d->net_packets_heap, recv_buffer);

        // Signal daemon's router thread
        k_fifo_put(&d->unrouted_packets_queue, unrouted_packet);
        return;
    }

    // Allocate buffer for a local packet
    cipher_packet_fifo_item_t *fifo_item = alloc_packet_fifo_item(d, bytes_recv);
    CHECK_MALLOC(fifo_item);

    // Decode packet
    serdes_decode_args_t args = {
        .header = header,
        .raw_payload = recv_buffer,
        .raw_payload_size = bytes_recv,
        .decoded_payload = fifo_item->packet.payload,
    };

    serdes_error_t err = serdes_decode_packet(args);
    if (err != SERDES_ERROR_OK)
        handle_iface_error(d, iface, IFACE_ERROR_SERDES, &err, sizeof(err));

    k_heap_free(&d->net_packets_heap, recv_buffer);

    // Send packet to the right handler
    switch (header->type) {
        case CIPHER_PACKET_TYPE_ADMIN:
            k_fifo_put(&d->admin_packet_queue, fifo_item);
            break;
        case CIPHER_PACKET_TYPE_RPC:
            k_fifo_put(&d->rpc_packet_queue, fifo_item);
            break;
        case CIPHER_PACKET_TYPE_EVENT:
            k_fifo_put(&d->event_packet_queue, fifo_item);
            break;
        case CIPHER_PACKET_TYPE_SD:
            k_fifo_put(&d->sd_packet_queue, fifo_item);
            break;
        default:
            WARN("Unknow header type: %d", header->type);  // TODO: Prevent spam of wrong header types
    }
}

static void process_incomplete_packet(cipher_daemon_t *d, cipher_iface_t *iface, cipher_header_t *header,
                                      uint8_t *recv_buffer, uint16_t bytes_recv) {
    WARN("Received incomplete packet, functionality not yet implemented, dropping packet");
    // Implements d->net_partial_packets_heap
    k_heap_free(&d->net_packets_heap, recv_buffer);
    // TODO: COuld receive less OR more bytes so account for this
}