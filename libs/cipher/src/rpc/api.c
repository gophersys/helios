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

LOG_MODULE_DECLARE(rpc);

void cipher_rpc_thread_add_event(cipher_daemon_t *d, rpc_event_t *event) {
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
    rpc_event_t *local_event = k_heap_aligned_alloc(&d->rpc.rpc_heap, 8, sizeof(rpc_event_t), K_NO_WAIT);
    CHECK_MALLOC(local_event);
    local_event->options = k_heap_aligned_alloc(&d->rpc.rpc_heap, 8, option_size, K_NO_WAIT);
    CHECK_MALLOC(local_event->options);

    // Copy user's event
    local_event->type = event->type;
    memcpy(local_event->options, event->options, option_size);
    static uint16_t event_id = 0;
    local_event->id = event_id++;

    k_fifo_put(&d->rpc.rpc_ctrl_event_queue, local_event);
}

void cipher_remote_rpc_handler(cipher_daemon_t *d, cipher_rpc_entry_t *entry) {

    cipher_local_rpc_request_fifo_item_t *fifo_item = alloc_local_rpc_request_fifo_item(d, entry->request_size, entry->response_size);
    CHECK_MALLOC(fifo_item);

    fifo_item->entry = entry;

    k_sem_init(&fifo_item->entry->await_sem, 0, 1);

    k_fifo_put(&d->rpc.rpc_local_request_event_queue, fifo_item);

    // Async wait
    k_sem_take(&fifo_item->entry->await_sem, K_FOREVER);  // Timeout is handled internally in thread

    free_local_rpc_request_fifo_item(d, fifo_item);
}
