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
#include "packet.h"

LOG_MODULE_REGISTER(rpc, RPC_LOG_LEVEL);

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
void cipher_rpc_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    while (true)
    {
        cipher_iface_packet_info_t *packet_info = k_fifo_get(&d->rpc_packet_queue, K_FOREVER);
        if (packet_info == NULL)
            ERROR("Null item on rpc_packet_queue, daemon %d", d->id);

        uint16_t packet_len = packet_info->packet->header.payload_len + sizeof(packet_info->packet->header);
        LOG("Received rpc packet, len %d", packet_len);
        // TODO: Implement me

        free_iface_packet_info(d, packet_info);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/
