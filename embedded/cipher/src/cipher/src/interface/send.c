// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "transport/transport.h"
#include "protocol/protocol.h"
#include "protocol/serdes.h"
#include "daemon/daemon.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "threads.h"

LOG_MODULE_DECLARE(iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

#define EVENT_NUM 3
#define CONN_EVENT 0
#define ENCODED_EVENT 1
#define DECODED_EVENT 2
/**
 * This thread could receive raw packets (for routing) or packets that must be encoded (from host)
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Connection Handlers
static void handle_timeout(cipher_daemon_t *d, cipher_iface_t *iface, const char *func);
static void handle_disconnect(cipher_daemon_t *d, cipher_iface_t *iface, const char *func);

// Event Handlers
static void setup_thread_events(cipher_daemon_t *d, cipher_iface_t *iface, struct k_poll_event *send_events);
static void handle_connection_event(cipher_daemon_t *d, cipher_iface_t *iface);
static void handle_encoded_packet_event(cipher_daemon_t *d, cipher_iface_t *iface);
static void handle_decoded_packet_event(cipher_daemon_t *d, cipher_iface_t *iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Send Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_interface_send_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    cipher_iface_t *iface = (cipher_iface_t *)arg1;

    __ASSERT(d != NULL, "null daemon passed to thread");
    __ASSERT(iface != NULL, "null interface passed to thread");

    struct k_poll_event send_events[EVENT_NUM];
    setup_thread_events(d, iface, send_events);

    while (1)
    {
        int event = k_poll(send_events, EVENT_NUM, K_FOREVER);
        if (event == 0)
        {
            if (send_events[CONN_EVENT].state == K_POLL_STATE_SEM_AVAILABLE)
                handle_connection_event(d, iface);
            else if (send_events[ENCODED_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                handle_encoded_packet_event(d, iface);
            else if (send_events[DECODED_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                handle_decoded_packet_event(d, iface);
            else
                ERROR("Unknown poll condition: %d. iface %d, daemon %d", event, iface->id, d->id);

            // reset events
            send_events[0].state = K_POLL_STATE_NOT_READY;
            send_events[1].state = K_POLL_STATE_NOT_READY;
            send_events[2].state = K_POLL_STATE_NOT_READY;
        }
        else
        {
            ERROR("Unexpected timeout on k_poll: %d. iface %d, daemon %d", event, iface->id, d->id);
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Setup Events
 *---------------------------------------------------------------------------------------------------*/
static void setup_thread_events(cipher_daemon_t *d, cipher_iface_t *iface, struct k_poll_event *send_events)
{
    k_poll_event_init(&send_events[CONN_EVENT],
                      K_POLL_TYPE_SEM_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &iface->conn_sem);

    k_poll_event_init(&send_events[ENCODED_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &iface->encoded_packets_queue);

    k_poll_event_init(&send_events[DECODED_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &iface->decoded_packets_queue);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     Connection Event
 *---------------------------------------------------------------------------------------------------*/
static void handle_connection_event(cipher_daemon_t *d, cipher_iface_t *iface)
{
    LOG("Send thread for iface %d unblocked on conn_sem", iface->id);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Encoded Packet Event
 *---------------------------------------------------------------------------------------------------*/
static void handle_encoded_packet_event(cipher_daemon_t *d, cipher_iface_t *iface)
{
    __ASSERT(iface->connected, "Received an encoded_packet to be sent on a disconnected interface");
    LOG("Send thread for iface %d, daemon %d, received encoded encoded_packet", iface->id, d->id);

    // Receive decoded_packet on queue
    cipher_packet_t *encoded_packet = k_fifo_get(&iface->encoded_packets_queue, K_NO_WAIT);
    if (encoded_packet == NULL)
        ERROR("Null item on encoded_packets_queue, iface %d, daemon %d", iface->id, d->id);

    uint16_t bytes_sent = 0;
    bool conn_closed = false;
    bool timeout = false;

    // Send the encoded encoded_packet on the interface
    uint16_t packet_len = sizeof(cipher_header_t) + encoded_packet->header.payload_len;
    if (!tal_send(iface->cfg, encoded_packet, packet_len, &bytes_sent, &conn_closed, &timeout))
    {
        if (timeout)
            handle_timeout(d, iface, __func__);
        else if (conn_closed)
            handle_disconnect(d, iface, __func__);
        else
            ERROR("Send error on iface %d, daemon %d", iface->id, d->id);

        // Packet was allocated as payload first, then header + payload pointer
        k_heap_free(&d->unrouted_packets_heap, encoded_packet->payload);
        k_heap_free(&d->unrouted_packets_heap, encoded_packet);
        return;
    }

    if (bytes_sent != packet_len)
        ERROR("Expected to send %d bytes, sent %d", packet_len, bytes_sent);

    // Packet was allocated as payload first, then header + payload pointer
    k_heap_free(&d->unrouted_packets_heap, encoded_packet->payload);
    k_heap_free(&d->unrouted_packets_heap, encoded_packet);

    LOG("Encoded encoded_packet sent succesfully on iface %d, daemon %d", iface->id, d->id);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Decoded Packet Event
 *---------------------------------------------------------------------------------------------------*/
static void handle_decoded_packet_event(cipher_daemon_t *d, cipher_iface_t *iface)
{
    __ASSERT(iface->connected, "Received an encoded_packet to be sent on a disconnected interface");
    LOG("Send thread for iface %d, daemon %d, received decoded encoded_packet", iface->id, d->id);

    // Receive encoded_packet on queue
    cipher_packet_t *decoded_packet = k_fifo_get(&iface->decoded_packets_queue, K_NO_WAIT);
    if (decoded_packet == NULL)
        ERROR("Null item on decoded_packets_queue, iface %d, daemon %d", iface->id, d->id);

    // Allocate a buffer to hold encoded payload
    uint16_t packet_len = sizeof(cipher_header_t) + decoded_packet->header.payload_len;
    uint8_t *send_buffer = k_heap_alloc(&d->net_packets_heap, packet_len, K_FOREVER);

    // Encode raw payload
    cipher_encode_args_t args = {
        .header = &decoded_packet->header,
        .raw_payload = decoded_packet,
        .raw_payload_size = packet_len,
        .encoded_payload = send_buffer,
    };
    cipher_error_t err = cipher_encode_packet(args);
    if (err != CIPHER_ERROR_OK)
        ERROR("Could not encode encoded_packet, err: %d. iface %d, daemon %d", err, iface->id, d->id);

    // Free daemon's memory allocated for decoded encoded_packet
    k_heap_free(&d->local_packets_heap, decoded_packet->payload);
    k_heap_free(&d->local_packets_heap, decoded_packet);

    // Send the encoded encoded_packet on the interface
    uint16_t bytes_sent = 0;
    bool conn_closed = false;
    bool timeout = false;

    if (!tal_send(iface->cfg, send_buffer, packet_len, &bytes_sent, &conn_closed, &timeout))
    {
        if (timeout)
            handle_timeout(d, iface, __func__);
        else if (conn_closed)
            handle_disconnect(d, iface, __func__);
        else
            ERROR("Send error on iface %d, daemon %d", iface->id, d->id);

        k_heap_free(&d->net_packets_heap, send_buffer);
        return;
    }

    if (bytes_sent != packet_len)
        ERROR("Expected to send %d bytes, sent %d", packet_len, bytes_sent);

    k_heap_free(&d->net_packets_heap, send_buffer);

    LOG("Encoded encoded_packet sent succesfully on iface %d, daemon %d", iface->id, d->id);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                        Timeout & Disconnect Handlers
 *---------------------------------------------------------------------------------------------------*/
static void handle_timeout(cipher_daemon_t *d, cipher_iface_t *iface, const char *func)
{
    ERROR("%s: Timeout while trying to send on iface %d, daemon %d", func, iface->id, d->id);
}

static void handle_disconnect(cipher_daemon_t *d, cipher_iface_t *iface, const char *func)
{
    LOG("Iface %d, daemon %d, disconnected, signaling iface controller", iface->id, d->id);

    // Signal a disconnection
    k_sem_give(&iface->disconn_sem);
}