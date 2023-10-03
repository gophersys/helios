// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>
#include <zephyr/random/rand32.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "protocol/protocol.h"
#include "utils/err.h"

// Private include
#include "controller.h"
#include "packet.h"
#include "threads.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_DECLARE(daemon);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

#define EVENT_NUM 2
#define HOST_LOCAL_EVENT 0
#define ADMIN_PACKET_EVENT 1

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Event handlers
static void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *send_events);
static void handle_local_event(cipher_daemon_t *d);
static void handle_admin_packet_event(cipher_daemon_t *d);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
void cipher_ctrl_add_event(cipher_daemon_t *d, ctrl_event_t *event) {
    __ASSERT(d, "null daemon pointer");
    __ASSERT(event, "null event pointer");

    // Get the option size of the event
    size_t option_size = 0;
    switch (event->type) {
        case CTRL_EVENT_TYPE_IFACE_CONNECTED:
        case CTRL_EVENT_TYPE_IFACE_DISCONNECTED:
            option_size = sizeof(ctrl_event_opt_iface_conn_t);
            break;

        case CTRL_EVENT_TYPE_EXIT:
            // TODO: how do i halt this thread?
            break;
        default:
            ERROR("Unknown event type %d", event->type);
            break;
    }

    // Allocate memory for the event & its options
    ctrl_event_t *local_event = k_heap_aligned_alloc(&d->ctrl_events_heap, 8, sizeof(ctrl_event_t) + sizeof(uint32_t), K_NO_WAIT);
    CHECK_MALLOC(local_event);
    local_event->options = k_heap_aligned_alloc(&d->ctrl_events_heap, 8, option_size, K_NO_WAIT);
    CHECK_MALLOC(local_event->options);

    // Copy user's event
    local_event->type = event->type;
    memcpy(local_event->options, event->options, option_size);
    sys_rand_get(&local_event->id, sizeof(local_event->id));

    // Add the event to the FIFO using k_fifo_alloc_put
    k_fifo_put(&d->ctrl_event_queue, local_event);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_ctrl_thread(void *arg0, void *arg1, void *arg2) {
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    __ASSERT(d != NULL, "null daemon passed to thread");

    struct k_poll_event ctrl_events[EVENT_NUM];
    setup_thread_events(d, ctrl_events);

    while (true) {
        int event = k_poll(ctrl_events, EVENT_NUM, K_FOREVER);
        if (event == 0) {
            if (ctrl_events[HOST_LOCAL_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                handle_local_event(d);
            else if (ctrl_events[ADMIN_PACKET_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE)
                handle_admin_packet_event(d);
            else
                ERROR("Unknown poll condition: %d. daemon %d", event, d->id);

            // reset events
            for (uint8_t i = 0; i < ARRAY_SIZE(ctrl_events); i++)
                ctrl_events[i].state = K_POLL_STATE_NOT_READY;
        } else {
            ERROR("Unexpected timeout on k_poll: %d. daemon %d", event, d->id);
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Setup Events
 *---------------------------------------------------------------------------------------------------*/
static void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *events) {
    k_poll_event_init(&events[HOST_LOCAL_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->ctrl_event_queue);

    k_poll_event_init(&events[ADMIN_PACKET_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->admin_packet_queue);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Admin Packet Handler
 *---------------------------------------------------------------------------------------------------*/
static void handle_admin_packet_event(cipher_daemon_t *d) {
    cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&d->admin_packet_queue, K_NO_WAIT);
    __ASSERT(fifo_item, "Null item on admin_packet_queue, daemon %d", d->id);
    free_packet_fifo_item(d, fifo_item);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                  Local Event Handler
 *---------------------------------------------------------------------------------------------------*/
static void handle_local_event(cipher_daemon_t *d) {
    ctrl_event_t *event = k_fifo_get(&d->ctrl_event_queue, K_FOREVER);
    if (event == NULL)
        ERROR("Null item on ctrl_event_queue, daemon %d", d->id);

    switch (event->type) {
        case CTRL_EVENT_TYPE_IFACE_CONNECTED: {
            DBG("CTRL_EVENT_TYPE_IFACE_CONNECTED received");
            ctrl_event_opt_iface_conn_t *iface_options = (ctrl_event_opt_iface_conn_t *)event->options;
            cipher_iface_t *iface = iface_options->iface;
            k_fifo_put(&d->sd_iface_conn_queue, iface);
        } break;

        case CTRL_EVENT_TYPE_IFACE_DISCONNECTED: {
            DBG("CTRL_EVENT_TYPE_IFACE_DISCONNECTED received");
            ctrl_event_opt_iface_conn_t *iface_options = (ctrl_event_opt_iface_conn_t *)event->options;
            cipher_iface_t *iface = iface_options->iface;
            k_fifo_put(&d->sd_iface_disconn_queue, iface);
        } break;

        case CTRL_EVENT_TYPE_EXIT: {
            DBG("Ending dameon instance...");

            k_thread_abort(d->sd_t_id);
            k_thread_abort(d->router_t_id);

            // tal_close(&daemon->uplink_cfg);

            DBG("Exiting");

            k_thread_abort(k_current_get());
        } break;

        default:
            ERROR("Unknown controller event type: %d", event->type);
    }

    k_heap_free(&d->ctrl_events_heap, event->options);
    k_heap_free(&d->ctrl_events_heap, event);
}