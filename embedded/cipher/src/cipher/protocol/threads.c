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
LOG_MODULE_DECLARE(protocol, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

// Listener thread
#define LISTENER_THREAD_PRIORITY 5
#define LISTENER_THREAD_STACK_SIZE 8192
K_THREAD_STACK_DEFINE(listener_thread_stack_area, LISTENER_THREAD_STACK_SIZE);
struct k_thread listener_thread_data;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
static void cipher_listener_thread(void *arg0, void *arg1, void *arg2);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/

bool cipher_threads_init(cipher_daemon_t *daemon)
{
    bool status = false;

    daemon->uplink_listener_tid = k_thread_create(&listener_thread_data,
                                                  listener_thread_stack_area,
                                                  K_THREAD_STACK_SIZEOF(listener_thread_stack_area),
                                                  cipher_listener_thread,
                                                  (void *)&daemon->uplink_cfg, NULL, NULL,
                                                  5,
                                                  0,
                                                  K_NO_WAIT);

    // TODO: how do we verify all threads were initialized ok?
    status = true;

    // k_msleep(100000);

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                      Private Function Implementation
 *---------------------------------------------------------------------------------------------------*/

static void cipher_listener_thread(void *arg0, void *arg1, void *arg2)
{
    tal_config_t *interface_cfg = (tal_config_t *)arg0;

    while (1)
    {
        uint8_t recv_buffer[CIPHER_CONFIG_MAX_PAYLOAD_SIZE] = {0}; // TODO: Create a buffer pool for this
        uint16_t bytes_recv = 0;
        bool conn_closed = false;

        if (!tal_recv(interface_cfg, recv_buffer, sizeof(recv_buffer), &bytes_recv, &conn_closed))
        {
            WARN("I am this error whihc idek what it means");

            // TODO: What should happen if receive fails for this interface?
            if (!conn_closed)
                WARN("Could not recv on interface");
        }
        else
        {
            if (bytes_recv < sizeof(cipher_packet_header_t))
            {
                WARN("Incomplete payload");
                // TODO: If payload is incomplete, do recv magic to await for it, timeouts and everything
            }
            else
            {
                cipher_packet_header_t header = {0};
                if (!cipher_packet_parse_header(recv_buffer, bytes_recv, &header))
                {
                    WARN("Unable to parse cipher header");
                }
                else
                {
                    cipher_print_header(&header);

                    // TODO: Check that payload length in header matches the recv payload (did we get a full packet?)

                    // TODO: If payload is complete, dispatch to the right receiver
                }
            }
        }
    }
}

bool cipher_packet_parse_header(const uint8_t *recv_buffer, uint16_t recv_buffer_size, cipher_packet_header_t *header_buffer);
