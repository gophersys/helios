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
#include "protocol/serdes.h"
#include "transport/transport.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "threads.h"

LOG_MODULE_DECLARE(iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

#define EVENT_NUM 2
#define ENCODED_EVENT 0
#define DECODED_EVENT 1
/**
 * This thread could receive raw packets (for routing) or packets that must be encoded (from host)
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Event Handlers
static void setup_thread_events(cipher_daemon_t *d, cipher_iface_t *iface, struct k_poll_event *events);
static void handle_encoded_packet_event(cipher_daemon_t *d, cipher_iface_t *iface);
static void handle_decoded_packet_event(cipher_daemon_t *d, cipher_iface_t *iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Send Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_interface_send_thread(void *arg0, void *arg1, void *arg2) {
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    cipher_iface_t *iface = (cipher_iface_t *)arg1;

    __ASSERT(d != NULL, "null daemon passed to thread");
    __ASSERT(iface != NULL, "null interface passed to thread");

    struct k_poll_event send_events[EVENT_NUM];
    setup_thread_events(d, iface, send_events);

    while (1) {
        // Wait until the iface is connected
        k_sem_take(&iface->conn_sem, K_FOREVER);  // TODO: handle timeout
        LOG("Send thread for iface %d unblocked", iface->id);

        while (iface->connected) {
            int event = k_poll(send_events, EVENT_NUM, K_FOREVER);
            if (event == 0) {
                if (send_events[ENCODED_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                    handle_encoded_packet_event(d, iface);
                else if (send_events[DECODED_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                    handle_decoded_packet_event(d, iface);
                else
                    ERROR("Unknown poll condition: %d. iface %d, daemon %d", event, iface->id, d->id);

                // reset events
                for (uint8_t i = 0; i < EVENT_NUM; i++)
                    send_events[i].state = K_POLL_STATE_NOT_READY;
            } else {
                ERROR("Unexpected timeout on k_poll: %d. iface %d, daemon %d", event, iface->id, d->id);
            }
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Setup Events
 *---------------------------------------------------------------------------------------------------*/
static void setup_thread_events(cipher_daemon_t *d, cipher_iface_t *iface, struct k_poll_event *events) {
    k_poll_event_init(&events[ENCODED_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &iface->encoded_packets_queue);

    k_poll_event_init(&events[DECODED_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &iface->decoded_packets_queue);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Encoded Packet Event
 *---------------------------------------------------------------------------------------------------*/
static void handle_encoded_packet_event(cipher_daemon_t *d, cipher_iface_t *iface) {

    __ASSERT(iface->connected, "Received an encoded_packet to be sent on a disconnected interface");
    DBG("Send thread for iface %d, daemon %d, received encoded encoded_packet", iface->id, d->id);

    cipher_router_packet_fifo_item_t *fifo_item = k_fifo_get(&iface->encoded_packets_queue, K_NO_WAIT);
    __ASSERT(fifo_item, "Null item on encoded_packets_queue, iface %d, daemon %d", iface->id, d->id);

    uint16_t bytes_sent = 0;
    bool conn_closed = false;
    bool timeout = false;

    // Send the encoded encoded_packet on the interface
    if (!tal_send(iface->cfg, fifo_item->raw_packet, fifo_item->packet_len, &bytes_sent, &conn_closed, &timeout)) {

        free_router_packet_fifo_item(d, fifo_item);

        if (timeout) {
            handle_iface_timeout(d, iface, __func__);
        } else if (conn_closed) {
            handle_iface_disconnect(d, iface, __func__);
        } else {
            ERROR("Send error on iface %d, daemon %d", iface->id, d->id);
        }

        return;
    }

    if (bytes_sent != fifo_item->packet_len) {
        ERROR("Expected to send %d bytes, sent %d", fifo_item->packet_len, bytes_sent);  // TODO: Implement retry functionality
    }

    free_router_packet_fifo_item(d, fifo_item);

    DBG("Encoded encoded_packet sent succesfully on iface %d, daemon %d", iface->id, d->id);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Decoded Packet Event
 *---------------------------------------------------------------------------------------------------*/
static void handle_decoded_packet_event(cipher_daemon_t *d, cipher_iface_t *iface) {
    __ASSERT(iface->connected, "Received an encoded_packet to be sent on a disconnected interface");
    DBG("Send thread for iface %d, daemon %d, received decoded packet", iface->id, d->id);

    // Receive fifo item
    cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&iface->decoded_packets_queue, K_NO_WAIT);

    cipher_packet_t *decoded_packet = &fifo_item->packet;

    // Allocate a buffer to hold encoded payload
    uint16_t packet_len = sizeof(cipher_header_t) + decoded_packet->header.payload_len;
    uint8_t *send_buffer = k_heap_alloc(&d->net_packets_heap, packet_len, K_FOREVER);
    CHECK_MALLOC(send_buffer);

    cipher_print_header(&decoded_packet->header);  // Uncommnet to see raw header

    // Encode raw payload
    serdes_encode_args_t args = {
        .header = &decoded_packet->header,
        .raw_payload = decoded_packet->payload,
        .raw_payload_size = decoded_packet->header.payload_len,
        .encoded_packet = send_buffer,
        .encoded_packet_size = packet_len,
    };
    serdes_error_t err = serdes_encode_packet(d, &args);
    if (err != SERDES_ERROR_OK) {
        ERROR("Could not encode encoded_packet, err: %d. iface %d, daemon %d", err, iface->id, d->id);
    }

    // Send the encoded encoded_packet on the interface
    uint16_t bytes_sent = 0;
    bool conn_closed = false;
    bool timeout = false;

    if (!tal_send(iface->cfg, send_buffer, packet_len, &bytes_sent, &conn_closed, &timeout)) {
        if (timeout) {
            handle_iface_timeout(d, iface, __func__);
        } else if (conn_closed) {
            handle_iface_disconnect(d, iface, __func__);
        } else {
            ERROR("Send error on iface %d, daemon %d", iface->id, d->id);
        }

        k_heap_free(&d->net_packets_heap, send_buffer);
        return;
    }

    if (bytes_sent != packet_len)
        ERROR("Expected to send %d bytes, sent %d", packet_len, bytes_sent);  // TODO: Implement retry functionality

    k_heap_free(&d->net_packets_heap, send_buffer);

    DBG("Encoded encoded_packet sent succesfully on iface %d, daemon %d", iface->id, d->id);
}
