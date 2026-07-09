// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include "daemon/daemon.h"
#include "daemon/registry.h"
#include "utils/err.h"

// Private includes
#include "rpc.h"

LOG_MODULE_DECLARE(rpc);

static void handle_iface_disconnected(cipher_daemon_t *d, rpc_event_t *event);
static void handle_timer_expired(cipher_daemon_t *d, rpc_event_t *event);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Thread Events
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief A control event is any situation that immediately affects the status of an RPC
 *
 * @param d The daemon
 */
void handle_ctrl_event(cipher_daemon_t *d) {
    rpc_event_t *event = k_fifo_get(&d->rpc.ctrl_event_queue, K_NO_WAIT);
    if (event == NULL)
        ERROR("Null item on ctrl_event_queue, daemon %d", d->id);

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

    k_heap_free(&d->rpc.heap, event->options);
    k_heap_free(&d->rpc.heap, event);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                  Iface Disconnection
 *---------------------------------------------------------------------------------------------------*/
void handle_iface_disconnected(cipher_daemon_t *d, rpc_event_t *event) {
    // Unblock the semaphore of the waiting function and chekc that it was taken to unallocate packet
    // Remove this rpc request from the active list
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Timer expired
 *---------------------------------------------------------------------------------------------------*/
cipher_registry_rpc_entry_t *cipher_rpc_get_entry_from_timer(cipher_daemon_t *d, struct k_timer *timer) {

    for (size_t i = 0; i < ARRAY_SIZE(d->rpc_registry.entries); i++) {
        cipher_registry_rpc_entry_t *current_entry = d->rpc_registry.entries[i];

        // A late RPC reply may unregister an entry (slot set to NULL) while a
        // TIMER_EXPIRED event for it is still queued. Guard against the NULL
        // slot before dereferencing, exactly like cipher_rpc_get_entry().
        if (current_entry == NULL) {
            continue;
        }

        if (!current_entry->_used) {
            continue;
        }

        if (&current_entry->timer != timer) {
            continue;
        }

        return current_entry;
    }

    return NULL;
}

void send_rpc_cancel_request(cipher_daemon_t *d, cipher_registry_rpc_entry_t *entry) {
    // Find the interface upon which we sent the RPC on
    // Populate header
    // Send on interface if connected
}

void signal_rpc_caller(cipher_daemon_t *d, cipher_registry_rpc_entry_t *entry) {
    // Tolerate a NULL entry: the timer may fire for an RPC that already
    // completed and was unregistered before this event was processed.
    if (entry == NULL) {
        return;
    }

    cipher_unary_rpc_user_info_t *info = entry->user_info;
    if (info != NULL) {
        info->error = CIPHER_RPC_ERR_TIMEOUT;
    }
    k_sem_give(&entry->await_sem);
}

void handle_timer_expired(cipher_daemon_t *d, rpc_event_t *event) {

    rpc_event_opt_timer_expired_t *opts = (rpc_event_opt_timer_expired_t *)event->options;
    cipher_registry_rpc_entry_t *entry = cipher_rpc_get_entry_from_timer(d, opts->timer);
    if (entry == NULL) {
        // The RPC replied and was unregistered before this queued timeout was
        // handled — nothing to cancel. Not an error, just a lost race.
        WARN("No active RPC entry for expired timer %p — already completed", opts->timer);
        return;
    }

    send_rpc_cancel_request(d, entry);
    signal_rpc_caller(d, entry);

    cipher_rpc_entry_unregister(d, entry);
}
