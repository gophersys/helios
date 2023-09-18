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

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/

typedef struct
{
    uint16_t destination_id;
    uint16_t service_id;
    uint8_t max_hops;
} cipher_sd_table_entry_t;

void cipher_sd_thread(void *arg0, void *arg1, void *arg2)
{
    LOG("Starting cipher service discovery thread");
    while (true)
        k_msleep(1000);

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
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/
