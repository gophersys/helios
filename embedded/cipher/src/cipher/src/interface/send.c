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

/**
 * This thread could receive raw packets (for routing) or packets that must be encoded (from host)
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
// static void process_egress_packet(cipher_daemon_t *d, uint8_t *send_buffer, uint16_t send_bytes);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Send Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_interface_send_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    cipher_iface_t *iface = (cipher_iface_t *)arg1;

    __ASSERT(d != NULL, "null daemon passed to thread");
    __ASSERT(iface != NULL, "null interface passed to thread");

    tal_config_t *interface_cfg = iface->cfg;

    while (1)
    {
        // Wait until the connection is established before sending data
        k_sem_take(&iface->conn_sem, K_FOREVER);
        DBG("Send thread for iface %d unblocked", iface->id);

        while (iface->connected) // Only send data while connected
        {
            // Await for a thread to request a send packet
            cipher_packet_t *packet = k_fifo_get(&d->rpc_queue, K_FOREVER);
            // TODO: Verify that the packet received is correct

            // Allocate a big enough buffer to store the serialized payload
            uint8_t *send_buffer = k_heap_alloc(&d->net_packets_heap, packet->header.payload_len, K_FOREVER);

            // Host byte order to Network byte order
            cipher_encode_args_t args = {
                .header = &packet->header,
                .raw_payload = packet->payload,
                .raw_payload_size = packet->header.payload_len,
                .encoded_payload = send_buffer,
            };
            cipher_error_t err = cipher_encode_packet(args);
            if (err != CIPHER_ERROR_OK)
                ERROR("Could not encode packet, err: %d", err);

            // Free raw packet memory
            k_heap_free(&d->local_packets_heap, packet->payload);
            k_heap_free(&d->local_packets_heap, packet);

            // Send packet
            uint16_t bytes_sent = 0;
            bool conn_closed = false;
            bool timeout = false;
            if (!tal_send(interface_cfg, send_buffer, packet->header.payload_len, &bytes_sent, &conn_closed, &timeout))
            {
                if (!conn_closed)
                {
                    handle_interface_error(d, iface, IFACE_ERROR_SEND);
                }
                else
                {
                    DBG("Connection closed on send, iface %d", iface->id);

                    // Signal a disconnection
                    k_sem_give(&iface->disconn_sem);

                    // Break out of the inner loop to await a new connection
                    break;
                }
            }

            // Free network payload buffer
            k_heap_free(&d->net_packets_heap, send_buffer);
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Egress
 *---------------------------------------------------------------------------------------------------*/
// static void process_egress_packet(cipher_daemon_t *d, uint8_t *send_buffer, uint16_t send_bytes)
// {
// }
