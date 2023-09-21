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

LOG_MODULE_REGISTER(sd, SD_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief The service discovery thread will do the following actions
 *
 * [ ] Register a new service when it's broadcasted from an interface
 * [ ] Unregister a service when an interface disconnects
 *
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
static void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *events);
static bool service_exists(cipher_daemon_t *d, cipher_service_entry_t *entry);
static void register_service(cipher_daemon_t *d, cipher_service_entry_t *entry);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
void cipher_sd_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    while (true)
    {
        cipher_iface_packet_info_t *packet_info = k_fifo_get(&d->sd_packet_queue, K_FOREVER);
        if (packet_info == NULL)
            ERROR("Null item on sd_packet_queue, daemon %d", d->id);

        cipher_packet_t *packet = (cipher_packet_t *)packet_info->packet;

        // Check if service is already registered
        cipher_service_entry_t potential_entry = {
            .device_id = packet->header.source_id,
            .service_id = packet->header.service_id,
            .iface = packet_info->iface,
        };

        if (!service_exists(d, &potential_entry))
            register_service(d, &potential_entry);

        free_iface_packet_info(d, packet_info);
    }
}

void cipher_sd_iface_disconnected(cipher_daemon_t *d, cipher_iface_t *iface)
{
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Setup Events
 *---------------------------------------------------------------------------------------------------*/
static void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *events)
{
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/

static bool service_exists(cipher_daemon_t *d, cipher_service_entry_t *entry)
{
    size_t service_count = sizeof(d->service_registry.entries) / sizeof(d->service_registry.entries[0]);
    for (size_t i = 0; i < service_count; i++)
    {
        if (d->service_registry.entries[i].device_id == entry->device_id)
        {
            if (d->service_registry.entries[i].service_id == entry->device_id)
                return true;
        }
    }

    LOG("Service %d, for device %d, on iface %d not in daemon's %d registry",
        entry->service_id, entry->device_id, entry->iface->id, d->id);
    return false;
}

static void register_service(cipher_daemon_t *d, cipher_service_entry_t *entry)
{
    size_t service_count = sizeof(d->service_registry.entries) / sizeof(d->service_registry.entries[0]);
    for (size_t i = 0; i < service_count; i++)
    {
        if (d->service_registry.entries[i].used == false)
        {
            memcpy(&d->service_registry.entries[i], entry, sizeof(cipher_service_entry_t));
            d->service_registry.entries[i].used = true;
            LOG("Service %d, device %d, on iface %d added to daemon's %d registry",
                entry->service_id, entry->device_id, entry->iface->id, d->id);
            return;
        }
    }

    ERROR("Daemon %d service registry is full!", d->id);
}