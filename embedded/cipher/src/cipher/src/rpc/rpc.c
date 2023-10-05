// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/random/rand32.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "utils/err.h"

// Private includes
#include "controller.h"
#include "rpc.h"
#include "threads.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Dev Notes
 *---------------------------------------------------------------------------------------------------*/

/**
 * [ ] Implement Local Events
 *
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/

LOG_MODULE_REGISTER(rpc, RPC_LOG_LEVEL);

#define EVENT_NUM 3
#define RPC_EVENT 0
#define LOCAL_REQUEST 1
#define RPC_PACKET 2

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
void cipher_rpc_add_event(cipher_daemon_t *d, rpc_event_t *event) {
    __ASSERT(d, "null daemon pointer");
    __ASSERT(event, "null event pointer");

    // Get the option size of the event
    size_t option_size = 0;
    switch (event->type) {
        case RPC_EVENT_TYPE_IFACE_DISCONNECTED:
            option_size = sizeof(rpc_event_opt_iface_disconn_t);
            break;

        case RPC_EVENT_TYPE_TIMER_EXPIRED:
            option_size = sizeof(rpc_event_opt_timer_expired_t);
            break;
        default:
            ERROR("Unknown event type %d", event->type);
            break;
    }

    // Allocate memory for the event & its options
    rpc_event_t *local_event = k_heap_aligned_alloc(&d->rpc_heap, 8, sizeof(rpc_event_t), K_NO_WAIT);
    CHECK_MALLOC(local_event);
    local_event->options = k_heap_aligned_alloc(&d->rpc_heap, 8, option_size, K_NO_WAIT);
    CHECK_MALLOC(local_event->options);

    // Copy user's event
    local_event->type = event->type;
    memcpy(local_event->options, event->options, option_size);
    sys_rand_get(&local_event->id, sizeof(local_event->id));

    k_fifo_put(&d->rpc_event_queue, local_event);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *events) {
    k_poll_event_init(&events[RPC_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->rpc_event_queue);

    k_poll_event_init(&events[LOCAL_REQUEST],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->localhost_rpc_queue);

    k_poll_event_init(&events[RPC_PACKET],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->rpc_packet_queue);
}

void handle_rpc_packet(cipher_daemon_t *d) {
    cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&d->rpc_packet_queue, K_FOREVER);
    __ASSERT(fifo_item, "Null item on rpc_packet_queue, daemon %d", d->id);

    cipher_packet_t *packet = &fifo_item->packet;

    if (CIPHER_IS_FLAG_SET(packet->header.flags, CIPHER_FLAG_RPC_REQUEST)) {
        handle_rpc_request_packet(d, fifo_item);
    } else if (CIPHER_IS_FLAG_SET(packet->header.flags, CIPHER_FLAG_RPC_RESPONSE) ||
               CIPHER_IS_FLAG_SET(packet->header.flags, CIPHER_FLAG_RPC_ERR)) {
        handle_rpc_response_packet(d, fifo_item);
    } else {
        ERROR("Expected at least 1 flag to be set in RPC packet");
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_rpc_thread(void *arg0, void *arg1, void *arg2) {
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    __ASSERT(d != NULL, "null daemon passed to thread");

    struct k_poll_event rpc_events[EVENT_NUM];
    setup_thread_events(d, rpc_events);

    while (true) {
        int event = k_poll(rpc_events, EVENT_NUM, K_FOREVER);
        if (event == 0) {
            if (rpc_events[RPC_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                handle_rpc_event(d);
            } else if (rpc_events[LOCAL_REQUEST].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                handle_local_request(d);
            } else if (rpc_events[RPC_PACKET].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                handle_rpc_packet(d);
            } else {
                ERROR("Unknown poll condition: %d, daemon %d", event, d->id);
            }

            // reset events
            for (uint8_t i = 0; i < EVENT_NUM; i++)
                rpc_events[i].state = K_POLL_STATE_NOT_READY;
        } else {
            ERROR("Unexpected timeout on k_poll: %d, daemon %d", event, d->id);
        }
    }
}