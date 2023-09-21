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

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
static void process_ingress_packet(cipher_daemon_t *d, uint8_t *recv_buffer, uint16_t bytes_recv);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Recv Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_interface_recv_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    cipher_iface_t *iface = (cipher_iface_t *)arg1;

    __ASSERT(d != NULL, "null daemon passed to thread");
    __ASSERT(iface != NULL, "null interface passed to thread");

    tal_config_t *interface_cfg = iface->cfg;

    while (1)
    {
        // Wait until the connection is established before receiving data
        k_sem_take(&iface->conn_sem, K_FOREVER);
        LOG("Recv thread for iface %d unblocked", iface->id);

        while (iface->connected) // Only receive data while connected
        {
            const size_t buffer_size = CONFIG_MAX_PAYLOAD_SIZE;
            uint8_t *recv_buffer = k_heap_alloc(&d->net_packets_heap, CONFIG_MAX_PAYLOAD_SIZE, K_FOREVER);
            uint16_t bytes_recv = 0;
            bool conn_closed = false;
            bool timeout = false;

            if (!tal_recv(interface_cfg, recv_buffer, buffer_size, &bytes_recv, &conn_closed, &timeout))
            {
                if (timeout || conn_closed)
                {
                    if (timeout)
                        WARN("Timeout trying to recv on iface %d, daemon %d", iface->id, d->id);
                    else
                        WARN("Connection closed trying to recv on iface %d, daemon %d", iface->id, d->id);

                    // Signal a disconnection
                    k_sem_give(&iface->disconn_sem);

                    // Break out of the inner loop to await a new connection
                    break;
                }
                else
                {
                    handle_interface_error(d, iface, IFACE_ERROR_RECV);
                }
            }
            else
            {
                process_ingress_packet(d, recv_buffer, bytes_recv);
            }

            k_heap_free(&d->net_packets_heap, recv_buffer);
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Ingress
 *---------------------------------------------------------------------------------------------------*/
static void process_ingress_packet(cipher_daemon_t *d, uint8_t *recv_buffer, uint16_t bytes_recv)
{

    if (bytes_recv < sizeof(cipher_header_t))
    {
        WARN("Incomplete payload");
    }
    else
    {
        cipher_header_t header = {0};
        if (!cipher_packet_parse_header(recv_buffer, bytes_recv, &header))
        {
            WARN("Unable to parse cipher header");
        }
        else
        {
            cipher_print_header(&header);

            if (header.payload_len == (bytes_recv - sizeof(header)))
            {
                if (header.destination_id != d->device_id)
                {
                    void *unrouted_packet = k_heap_alloc(&d->unrouted_packets_heap, bytes_recv, K_FOREVER);
                    memcpy(unrouted_packet, recv_buffer, bytes_recv);
                    k_fifo_put(&d->unrouted_packets_queue, unrouted_packet);
                }
                else
                {
                    cipher_packet_t *packet = k_heap_alloc(&d->local_packets_heap, sizeof(cipher_packet_t), K_FOREVER);
                    packet->payload = k_heap_alloc(&d->local_packets_heap, bytes_recv, K_FOREVER);

                    cipher_decode_args_t args = {
                        .header = &header,
                        .raw_payload = recv_buffer,
                        .raw_payload_size = bytes_recv,
                        .decoded_payload = packet->payload,
                    };

                    cipher_error_t err = cipher_decode_packet(args);
                    if (err != CIPHER_ERROR_OK)
                        ERROR("Could not decode packet, err: %d", err);

                    switch (header.type)
                    {
                    case CIPHER_PACKET_TYPE_RPC:
                        k_fifo_put(&d->rpc_queue, (cipher_packet_t *)packet);
                        break;
                    case CIPHER_PACKET_TYPE_EVENT:
                        k_fifo_put(&d->event_queue, (cipher_packet_t *)packet);
                        break;
                    case CIPHER_PACKET_TYPE_SD:
                        k_fifo_put(&d->service_discovery_queue, (cipher_packet_t *)packet);
                        break;
                    default:
                        WARN("Unknow header type: %d", header.type);
                    }
                }
            }
            else
            {
                WARN("Received incomplete packet, header.length = %u, recv: %d", header.payload_len, bytes_recv);
                // TODO: COuld receive less OR more bytes so account for this
            }
        }
    }
}