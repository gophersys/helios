// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "utils/err.h"

// Private includes
#include "rpc.h"
#include "threads.h"

LOG_MODULE_REGISTER(rpc, RPC_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/

#define EVENT_NUM 2
#define LOCAL_RPC_EVENT 0
#define REMOTE_RPC_EVENT 1

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *events) {
    // TODO: Add an interface disconnected event and clean up/cancel all rpcs
    k_poll_event_init(&events[LOCAL_RPC_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->localhost_rpc_queue);

    k_poll_event_init(&events[REMOTE_RPC_EVENT],
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
            if (rpc_events[LOCAL_RPC_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                handle_local_rpc_request_event(d);
            } else if (rpc_events[REMOTE_RPC_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
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