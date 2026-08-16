// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/random/random.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "utils/err.h"

// Private includes
#include "events.h"
#include "rpc.h"
#include "threads.h"

LOG_MODULE_REGISTER(rpc, CONFIG_CK_CIPHER_RPC_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Thread Events
 *---------------------------------------------------------------------------------------------------*/

#define EVENT_NUM 3
#define DAEMON_EVENT 0         // Iface status changes, timers expired, etc
#define NET_PACKET_EVENT 1     // Any RPC network packet
#define LOCAL_REQUEST_EVENT 2  // Localhost app RPC request

/**
 * @brief Set the up thread events object
 *
 * @param d The daemon
 * @param events The events object
 */
void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *events) {
    k_poll_event_init(&events[DAEMON_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->rpc.ctrl_event_queue);

    k_poll_event_init(&events[LOCAL_REQUEST_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->rpc.local_request_event_queue);

    k_poll_event_init(&events[NET_PACKET_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->rpc.packets_event_queue);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief The RPC thread will poll on 3 queues, 1 for each event type.
 *
 * Depending on the event, this thread will do the work, or offload work to one of the daemon's worker-
 * thread members.
 *
 * @param arg0 (cipher_daemon_t*) A pointer to the daemon this thread belongs to
 */
void cipher_rpc_thread(void *arg0, void *arg1, void *arg2) {

    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    __ASSERT(d != NULL, "null daemon passed to thread");

    struct k_poll_event rpc_events[EVENT_NUM] = {0};
    setup_thread_events(d, rpc_events);

    while (true) {
        int event = k_poll(rpc_events, EVENT_NUM, K_FOREVER);
        if (event == 0) {
            if (rpc_events[DAEMON_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                handle_ctrl_event(d);
            } else if (rpc_events[NET_PACKET_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                handle_net_packet_event(d);
            } else if (rpc_events[LOCAL_REQUEST_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                handle_local_request_event(d);
            } else {
                ERROR("Unknown poll condition: %d, daemon %d", event, d->id);
            }

            for (uint8_t i = 0; i < EVENT_NUM; i++) {
                rpc_events[i].state = K_POLL_STATE_NOT_READY;  // reset events
            }

        } else {
            ERROR("Unexpected timeout on k_poll: %d, thread %s daemon %d",
                  event, k_thread_name_get(d->rpc.t_id), d->id);
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Helpers
 *---------------------------------------------------------------------------------------------------*/
char *cipher_rpc_err_str(cipher_rpc_err_t err) {
    switch (err) {
        case CIPHER_RPC_ERR_OK:              return "OK";
        case CIPHER_RPC_ERR_TIMEOUT:         return "TIMEOUT";
        case CIPHER_RPC_ERR_CONN_LOST:       return "CONNECTION_LOST";
        case CIPHER_RPC_ERR_NOT_FOUND:       return "NOT_FOUND";
        case CIPHER_RPC_ERR_NOT_IMPLEMENTED: return "NOT_IMPLEMENTED";
        default:                             return "UNKNOWN";
    }
}
