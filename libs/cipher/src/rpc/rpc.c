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


void handle_rpc_event(cipher_daemon_t *d) {
    rpc_event_t *event = k_fifo_get(&d->rpc_event_queue, K_NO_WAIT);
    if (event == NULL)
        ERROR("Null item on rpc_event_queue, daemon %d", d->id);

    switch (event->type) {
        case RPC_EVENT_TYPE_IFACE_DISCONNECTED:
            handle_iface_disconnected(d, event);
            break;

        case RPC_EVENT_TYPE_TIMER_EXPIRED:
            handle_timer_expired(d, event);
            break;

        default:
            break;
    }

    k_heap_free(&d->rpc_heap, event->options);
    k_heap_free(&d->rpc_heap, event);
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