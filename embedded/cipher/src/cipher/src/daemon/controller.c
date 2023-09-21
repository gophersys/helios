// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "protocol/protocol.h"
#include "utils/err.h"

// Private include
#include "threads.h"
#include "controller.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_DECLARE(daemon);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

#define EVENT_NUM 2
#define ADMIN_PACKET_EVENT 0
#define HOST_LOCAL_EVENT 1

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Event handlers
static void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *send_events);
static void handle_admin_packet_event(cipher_daemon_t *d);
static void handle_local_event(cipher_daemon_t *d);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/

bool cipher_controller_exit(cipher_daemon_t *daemon)
{
    bool status = false;
    controller_event_t exit_event = {
        .type = CONTROLLER_EVENT_TYPE_EXIT,
    };
    k_fifo_alloc_put(&daemon->controller_event_queue, &exit_event);

    // TODO: me
    status = true;
    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/

void cipher_controller_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    __ASSERT(d != NULL, "null daemon passed to thread");

    struct k_poll_event ctl_events[EVENT_NUM];
    setup_thread_events(d, ctl_events);

    while (true)
    {
        int event = k_poll(ctl_events, EVENT_NUM, K_FOREVER);
        if (event == 0)
        {
            if (ctl_events[ADMIN_PACKET_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                handle_admin_packet_event(d);
            else if (ctl_events[HOST_LOCAL_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                handle_local_event(d);
            else
                ERROR("Unknown poll condition: %d. daemon %d", event, d->id);

            // reset events
            for (uint8_t i = 0; i < EVENT_NUM; i++)
                ctl_events[i].state = K_POLL_STATE_NOT_READY;
        }
        else
        {
            ERROR("Unexpected timeout on k_poll: %d. daemon %d", event, d->id);
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Setup Events
 *---------------------------------------------------------------------------------------------------*/
static void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *events)
{
    k_poll_event_init(&events[ADMIN_PACKET_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->admin_packet_queue);

    k_poll_event_init(&events[HOST_LOCAL_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->controller_event_queue);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Admin Packet Handler
 *---------------------------------------------------------------------------------------------------*/
static void handle_admin_packet_event(cipher_daemon_t *d)
{
    cipher_packet_t *packet = k_fifo_get(&d->admin_packet_queue, K_NO_WAIT);
    if (packet == NULL)
        ERROR("Null item on admin_packet_queue, daemon %d", d->id);

    uint16_t packet_len = packet->header.payload_len + sizeof(packet->header);
    LOG("Received admin packet, len %d", packet_len);
    // TODO: Implement me

    k_heap_free(&d->local_packets_heap, packet->payload);
    k_heap_free(&d->local_packets_heap, packet);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                  Local Event Handler
 *---------------------------------------------------------------------------------------------------*/
static void handle_local_event(cipher_daemon_t *d)
{
    controller_event_t *event = k_fifo_get(&d->controller_event_queue, K_NO_WAIT);
    if (event == NULL)
        ERROR("Null item on controller_event_queue, daemon %d", d->id);

    switch (event->type)
    {
    case CONTROLLER_EVENT_TYPE_EXIT:

        DBG("Ending dameon instance...");

        k_thread_abort(d->sd_t_id);
        // k_thread_abort(daemon->);
        k_thread_abort(d->router_t_id);

        // tal_close(&daemon->uplink_cfg);

        DBG("Exiting");

        k_thread_abort(k_current_get());

        break;

    default:
        ERROR("Unknown controller event type: %d", event->type);
    }
}