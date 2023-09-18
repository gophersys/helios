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
 *                                                                                          Work Queues
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Controller Thread
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Accept Thread
 *---------------------------------------------------------------------------------------------------*/

void cipher_downlink_accept_thread(void *arg0, void *arg1, void *arg2)
{
    tal_config_t *interface = (tal_config_t *)arg0;

    while (true)
    {
        if (!tal_accept(interface))
        {
            WARN("Unable to accept on interface");

            k_thread_suspend(k_current_get());
        }
        else
        {
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Listener Thread
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Router Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_router_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    while (true)
    {
        void *packet = k_fifo_get(&d->unrouted_packets_queue, K_FOREVER);
        LOG("Doing something with unrouted packet");
        k_heap_free(&d->unrouted_packets_heap, packet);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                             Service Discovery Thread
 *---------------------------------------------------------------------------------------------------*/

typedef struct
{
    uint16_t destination_id;
    uint16_t service_id;
    uint8_t max_hops;
} cipher_sd_table_entry_t;

void cipher_sd_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    while (true)
    {
        cipher_packet_t *packet = k_fifo_get(&d->service_discovery_queue, K_FOREVER);
        // cipher_payload_sd_t *payload = (cipher_payload_sd_t *)packet->payload;
        // LOG("SD packet: ID -> %d, Hops: %d ", payload->service_id, payload->num_hops);

        k_heap_free(&d->local_packets_heap, packet->payload);
        k_heap_free(&d->local_packets_heap, packet);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           RPC Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_rpc_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    while (true)
    {
        cipher_packet_t *packet = k_fifo_get(&d->rpc_queue, K_FOREVER);
        k_heap_free(&d->local_packets_heap, packet->payload);
        k_heap_free(&d->local_packets_heap, packet);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Event Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_event_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    while (true)
    {
        cipher_packet_t *packet = k_fifo_get(&d->rpc_queue, K_FOREVER);
        k_heap_free(&d->local_packets_heap, packet->payload);
        k_heap_free(&d->local_packets_heap, packet);
    }
}