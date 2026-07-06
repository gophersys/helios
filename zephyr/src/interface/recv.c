// Standard includes
#include <stdio.h>
#include <string.h>

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
/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Recv Thread
 *---------------------------------------------------------------------------------------------------*/

// TCP is a byte stream: one read may deliver several cipher packets back to
// back, or a fraction of one. The recv thread accumulates bytes and frames out
// complete packets (header.payload_len tells us each packet's exact length),
// keeping any trailing partial for the next read. ACC_SIZE holds at least one
// max-size packet plus a coalesced neighbour.
#define ACC_SIZE (2 * CONFIG_MAX_PAYLOAD_SIZE)

static void dispatch_framed_packet(cipher_daemon_t *d, cipher_iface_t *iface,
                                   cipher_header_t *header, uint8_t *packet, uint16_t packet_size);
static void process_routing_packet(cipher_daemon_t *d, cipher_header_t *header, uint8_t *recv_buffer, uint16_t packet_size);

void cipher_interface_recv_thread(void *arg0, void *arg1, void *arg2) {
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    cipher_iface_t *iface = (cipher_iface_t *)arg1;

    __ASSERT(d != NULL, "null daemon passed to thread");
    __ASSERT(iface != NULL, "null interface passed to thread");

    iface_t *interface_cfg = iface->cfg;

    uint8_t *acc = k_heap_alloc(&d->net_buffers_heap, ACC_SIZE, K_FOREVER);
    CHECK_MALLOC(acc);
    size_t acc_len = 0;

    while (1) {
        // Wait until the iface is connected
        k_sem_take(&iface->conn_sem, K_FOREVER);  // TODO: handle timeout
        LOG("Recv thread for iface %d unblocked", iface->id);
        acc_len = 0;  // fresh framing state per connection

        bool timeout = false;
        while (iface->connected) {
            bool conn_closed = false;
            uint16_t bytes_recv = 0;

            if (!iface_recv(interface_cfg, acc + acc_len, ACC_SIZE - acc_len, &bytes_recv, &conn_closed, &timeout)) {
                if (timeout) {
                    handle_iface_timeout(d, iface, __func__);
                } else if (conn_closed) {
                    handle_iface_disconnect(d, iface, __func__);
                } else {
                    ERROR("Recv error on iface %d, daemon %d", iface->id, d->id);
                }
                break;
            }

            acc_len += bytes_recv;

            // Frame every complete packet currently buffered.
            size_t offset = 0;
            while (acc_len - offset >= sizeof(cipher_header_t)) {
                cipher_header_t header = {0};
                serdes_error_t err = serdes_decode_header(acc + offset, acc_len - offset, &header);
                if (err != SERDES_ERROR_OK) {
                    handle_iface_error(d, iface, IFACE_ERROR_SERDES, &err, sizeof(err));
                    offset = acc_len;  // desync guard: drop the buffer
                    break;
                }

                size_t packet_size = sizeof(cipher_header_t) + header.payload_len;
                if (packet_size > ACC_SIZE) {
                    ERROR("Oversized packet (%zu > %d) on iface %d, dropping stream", packet_size, ACC_SIZE, iface->id);
                    offset = acc_len;
                    break;
                }
                if (acc_len - offset < packet_size) {
                    break;  // rest of this packet has not arrived yet
                }

                dispatch_framed_packet(d, iface, &header, acc + offset, (uint16_t)packet_size);
                offset += packet_size;
            }

            // Slide any trailing partial packet to the front.
            if (offset > 0) {
                acc_len -= offset;
                if (acc_len > 0) {
                    memmove(acc, acc + offset, acc_len);
                }
            } else if (acc_len == ACC_SIZE) {
                // Full buffer with no complete packet -> unrecoverable desync.
                ERROR("Framing desync on iface %d, resetting buffer", iface->id);
                acc_len = 0;
            }
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Packet Dispatch
 *---------------------------------------------------------------------------------------------------*/

// Decode + route ONE complete, framed packet. Operates on a slice of the
// persistent accumulator (no ownership, no free).
static void dispatch_framed_packet(cipher_daemon_t *d, cipher_iface_t *iface,
                                   cipher_header_t *header, uint8_t *packet, uint16_t packet_size) {

    if (!registry_add_device_to_iface(d, iface, header->source_id)) {
        ERROR("Could not add device entry to iface");
    }

    // Not for us and not a broadcast -> forward it.
    if (header->destination_id != 0xFFFF && header->destination_id != d->device_id) {
        process_routing_packet(d, header, packet, packet_size);
        return;
    }

    size_t payload_size = packet_size - sizeof(cipher_header_t);
    cipher_packet_fifo_item_t *fifo_item = alloc_packet_fifo_item(d, payload_size);
    CHECK_MALLOC(fifo_item);

    serdes_decode_args_t args = {
        .header = header,
        .raw_packet = packet,
        .raw_packet_size = packet_size,
        .decoded_payload = fifo_item->packet.payload,
        .decoded_payload_size = payload_size,
    };
    serdes_error_t err = serdes_decode_packet(d, &args);
    if (err != SERDES_ERROR_OK) {
        handle_iface_error(d, iface, IFACE_ERROR_SERDES, &err, sizeof(err));
        free_packet_fifo_item(d, fifo_item);
        return;
    }

    fifo_item->iface = iface;
    fifo_item->packet.header = *header;

    switch (header->type) {
        case CIPHER_PACKET_TYPE_ADMIN:
            k_fifo_put(&d->admin_packet_queue, fifo_item);
            break;
        case CIPHER_PACKET_TYPE_RPC:
            k_fifo_put(&d->rpc.packets_event_queue, fifo_item);
            break;
        case CIPHER_PACKET_TYPE_EVENT:
            k_fifo_put(&d->events_packet_event_queue, fifo_item);
            break;
        case CIPHER_PACKET_TYPE_SD:
            k_fifo_put(&d->sd.packets_event_queue, fifo_item);
            break;
        case CIPHER_PACKET_TYPE_STREAM:
            k_fifo_put(&d->stream_packet_event_queue, fifo_item);
            break;
        default:
            WARN("Unknown header type: %d", header->type);
            free_packet_fifo_item(d, fifo_item);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Route Forward
 *---------------------------------------------------------------------------------------------------*/
static void process_routing_packet(cipher_daemon_t *d, cipher_header_t *header, uint8_t *recv_buffer, uint16_t packet_size) {

    cipher_router_packet_fifo_item_t *fifo_item = alloc_router_packet_fifo_item(d, packet_size);
    CHECK_MALLOC(fifo_item);

    memcpy(fifo_item->raw_packet, recv_buffer, packet_size);
    fifo_item->packet_len = packet_size;

    // TODO: We must unpack the header, increase the hop count, and pack it up again

    // Look up the destination interface
    cipher_iface_t *dest_iface = registry_get_iface(d, header->destination_id);
    if (dest_iface != NULL) {
        k_fifo_put(&dest_iface->encoded_packets_queue, fifo_item);
    } else {
        // Device destination was not found, simply free the buffer and drop the packet
        free_router_packet_fifo_item(d, fifo_item);
    }
}

