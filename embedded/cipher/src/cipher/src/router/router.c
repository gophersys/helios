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

LOG_MODULE_REGISTER(router, ROUTER_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
void cipher_router_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    while (true)
    {
        cipher_packet_t *packet = k_fifo_get(&d->unrouted_packets_queue, K_FOREVER);
        if (packet == NULL)
            ERROR("Null item on unrouted_packets_queue, daemon %d", d->id);

        uint16_t packet_len = packet->header.payload_len + sizeof(packet->header);
        LOG("Received unrouted packet, len %d", packet_len);
        // TODO: Implement me

        k_heap_free(&d->unrouted_packets_heap, packet);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/
