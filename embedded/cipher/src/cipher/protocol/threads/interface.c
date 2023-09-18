#include "cipher.h"

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Private includes
#include "tal.h"
#include "utils.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_DECLARE(cipher);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

static void process_packet(cipher_daemon_t *d, uint8_t *recv_buffer, uint16_t bytes_recv);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/
static void process_packet(cipher_daemon_t *d, uint8_t *recv_buffer, uint16_t bytes_recv)
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
            // cipher_print_header(&header);

            if (header.payload_len == bytes_recv - sizeof(header))
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
                ERROR("Received incomplete packet, header.length = %d, recv: %d", header.payload_len, bytes_recv);
                // TODO: COuld receive less OR more bytes so account for this
            }
        }
    }
}

void cipher_interface_conn_thread(void *arg0, void *arg1, void *arg2)
{
    while (true)
        k_msleep(1000);
}

void cipher_interface_send_thread(void *arg0, void *arg1, void *arg2)
{
    while (true)
        k_msleep(1000);
}

void cipher_interface_recv_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    tal_config_t *interface_cfg = (tal_config_t *)arg1;

    while (1)
    {
        // TODO: Only stop listening after interface is connected

        const size_t buffer_size = CIPHER_CONFIG_MAX_PAYLOAD_SIZE;
        uint8_t *recv_buffer = k_heap_alloc(&d->recv_buffers_heap, CIPHER_CONFIG_MAX_PAYLOAD_SIZE, K_FOREVER);
        uint16_t bytes_recv = 0;
        bool conn_closed = false;

        if (tal_recv(interface_cfg, recv_buffer, buffer_size, &bytes_recv, &conn_closed))
        {
            process_packet(d, recv_buffer, bytes_recv);
        }
        else
        {
            if (!conn_closed)
            {
                WARN("Could not recv on interface");
            }
            else
            {
                WARN("Remote connection closed");

                cipher_controller_exit(d);
                k_thread_suspend(k_current_get());
            }
        }

        k_heap_free(&d->recv_buffers_heap, recv_buffer);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Uplink
 *---------------------------------------------------------------------------------------------------*/
/**
 * @brief Calls connect() and attempts a protocol handshake
 *
 * @param interface Desired interface to connect
 * @return true If connect and handshake succeed
 * @return false If remote end not found, or handshake failed
 */
static bool cipher_init_uplink(tal_config_t *interface)
{
    bool status = false;
    if (!tal_connect(interface))
    {
        WARN("Could not connect uplink interface");
    }
    else
    {
        DBG("Succesfully connected to remote node, handshaking...");

        if (!cipher_handshake(interface))
        {
            WARN("Could not handshake remote link");
        }
        else
        {
            LOG("Uplink interface initialized OK");
            status = true;
        }
    }

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Downlink
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Spins off a new connection listener thread, which gets cleaned up on accept()
 *
 * @param interface
 * @return true
 * @return false
 */
static bool cipher_init_downlink(tal_config_t *interface)
{
    bool status = false;

    return status;
}
