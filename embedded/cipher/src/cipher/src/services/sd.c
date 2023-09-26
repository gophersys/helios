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
 * @brief The service discovery thread will do the following actions:
 *
 * [ ] Register a new service when a service discovery status packet is received
 * [ ] Unregister a service when a service discovery status packet is received
 * [ ] Unregister all services on an interface when its disconnected
 * [ ] Broadcast a service status to all affected interfaces when the service registry changes
 */

#define EVENT_NUM 3
#define SD_PACKET_EVENT 0
#define IFACE_CONN_EVENT 1
#define IFACE_DISCONN_EVENT 2

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

static void send_service_broadcast(cipher_daemon_t *d, cipher_iface_t *iface, cipher_payload_sd_t *sd_payload);

// Event handlers
static void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *events);
static void handle_packet_event(cipher_daemon_t *d);
static void handle_iface_conn_event(cipher_daemon_t *d);
static void handle_iface_disconn_event(cipher_daemon_t *d);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_sd_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    __ASSERT(d != NULL, "null daemon passed to thread");

    struct k_poll_event sd_events[EVENT_NUM];
    setup_thread_events(d, sd_events);

    while (true)
    {
        int event = k_poll(sd_events, EVENT_NUM, K_FOREVER);
        if (event == 0)
        {
            if (sd_events[SD_PACKET_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                handle_packet_event(d);
            else if (sd_events[IFACE_CONN_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                handle_iface_conn_event(d);
            else if (sd_events[IFACE_DISCONN_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                handle_iface_disconn_event(d);
            else
                ERROR("Unknown poll condition: %d, daemon %d", event, d->id);

            // reset events
            for (uint8_t i = 0; i < EVENT_NUM; i++)
                sd_events[i].state = K_POLL_STATE_NOT_READY;
        }
        else
        {
            ERROR("Unexpected timeout on k_poll: %d, daemon %d", event, d->id);
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Setup Events
 *---------------------------------------------------------------------------------------------------*/
static void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *events)
{
    k_poll_event_init(&events[SD_PACKET_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->sd_packet_queue);

    k_poll_event_init(&events[IFACE_CONN_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->sd_iface_conn_queue);

    k_poll_event_init(&events[IFACE_DISCONN_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->sd_iface_disconn_queue);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Packet Event
 *---------------------------------------------------------------------------------------------------*/
static bool service_exists(cipher_daemon_t *d, cipher_service_entry_t *entry);
static void register_service(cipher_daemon_t *d, cipher_service_entry_t *entry);
static void notify_interfaces(cipher_daemon_t *d);

static void handle_packet_event(cipher_daemon_t *d)
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
    {
        register_service(d, &potential_entry);
        free_iface_packet_info(d, packet_info);

        notify_interfaces(d);
    }
}

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

static void notify_interfaces(cipher_daemon_t *d)
{
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                               Iface Connection Event
 *---------------------------------------------------------------------------------------------------*/

static void handle_iface_conn_event(cipher_daemon_t *d)
{
    cipher_iface_t *conn_iface = k_fifo_get(&d->sd_iface_conn_queue, K_FOREVER);
    if (conn_iface == NULL)
        ERROR("Null item on sd_iface_conn_queue, daemon %d", d->id);

    LOG("iface %d connected!, advertising all services", conn_iface->id);

    // For each registered service in our registry
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++)
    {
        // If the interface is still connected
        if (d->service_registry.entries[i].iface->connected)
        {
            // If the entry's iface is NOT the one that just connected
            if (d->service_registry.entries[i].iface->id != conn_iface->id)
            {
                // Create the service discovery payload
                cipher_payload_sd_t payload = {
                    .alive = true,
                    .id = d->service_registry.entries[i].service_id,
                    .num_ops = 0,
                };

                send_service_broadcast(d, conn_iface, &payload);
            }
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                             Iface Disonnection Event
 *---------------------------------------------------------------------------------------------------*/

static void handle_iface_disconn_event(cipher_daemon_t *d)
{
    cipher_iface_t *disconn_iface = k_fifo_get(&d->sd_iface_disconn_queue, K_FOREVER);

    __ASSERT(disconn_iface, "Null item on sd_iface_disconn_queue, daemon %d", d->id);
    __ASSERT(!disconn_iface->connected, "Expected iface %d for daemon %d to be disconencted", disconn_iface->id, d->id);

    DBG("iface %d disconnected!, advertising all services", disconn_iface->id);

    // For each registered service in our registry
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++)
    {
        // If the entry's iface is the one that just disconnected
        if (d->service_registry.entries[i].iface->id == disconn_iface->id)
        {
            // Create the service discovery payload
            cipher_payload_sd_t payload = {
                .alive = false,
                .id = d->service_registry.entries[i].service_id,
                .num_ops = 0,
            };

            // Tell every other uplink interface about it
            for (uint8_t i = 0; i < CONFIG_UP_LINK_IFACE_COUNT; i++)
            {
                cipher_iface_t *adv_iface = &d->uplink_t_g[i].iface;
                if (adv_iface->connected)
                    send_service_broadcast(d, adv_iface, &payload);
            }

            // Tell every other downlink interface about it
            for (uint8_t i = 0; i < CONFIG_DOWN_LINK_IFACE_COUNT; i++)
            {
                cipher_iface_t *adv_iface = &d->downlink_t_g[i].iface;
                if (adv_iface->connected)
                {
                    if (adv_iface->connected)
                        send_service_broadcast(d, adv_iface, &payload);
                }
            }
        }
    }

    // Update registry
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Helpers
 *---------------------------------------------------------------------------------------------------*/

static void send_service_broadcast(cipher_daemon_t *d, cipher_iface_t *iface, cipher_payload_sd_t *sd_payload)
{
    // Allocate memory for queue item
    cipher_packet_fifo_t *fifo_item = k_heap_aligned_alloc(&d->local_packets_heap, 8, sizeof(cipher_packet_fifo_t), K_FOREVER);
    CHECK_MALLOC(fifo_item);

    // Allocate memory for packet payload
    cipher_packet_t *packet = &fifo_item->packet;
    packet->payload = k_heap_aligned_alloc(&d->local_packets_heap, 8, sizeof(cipher_payload_sd_t), K_FOREVER);
    CHECK_MALLOC(packet->payload);

    // Set payload values
    cipher_payload_sd_t *payload = (cipher_payload_sd_t *)packet->payload;
    payload->alive = sd_payload->alive;
    payload->id = sd_payload->id;
    payload->num_ops = sd_payload->num_ops;

    // Add to interface's send queue
    DBG("Sending service discovery payload to iface %d", iface->id);
    k_fifo_put(&iface->decoded_packets_queue, packet);
}