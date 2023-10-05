// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "utils/err.h"

// Private includes
#include "controller.h"
#include "rpc.h"
#include "threads.h"

LOG_MODULE_DECLARE(rpc);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Event Handler
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                   Iface Disconnected
 *---------------------------------------------------------------------------------------------------*/
/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Timer Expired
 *---------------------------------------------------------------------------------------------------*/

cipher_rpc_entry_t *cipher_rpc_get_entry_from_timer(cipher_daemon_t *d, struct k_timer *timer) {

    for (size_t i = 0; i < ARRAY_SIZE(d->rpc_registry.entries); i++) {
        cipher_rpc_entry_t *current_entry = d->rpc_registry.entries[i];

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

void send_rpc_cancel_request(cipher_daemon_t *d, cipher_rpc_entry_t *entry) {
    // Find the interface upon which we sent the RPC on
    // Populate header
    // Send on interface if connected
}

void signal_rpc_caller(cipher_daemon_t *d, cipher_rpc_entry_t *entry) {
    cipher_rpc_user_info_t *info = entry->user_info;
    info->error = CIPHER_RPC_ERR_TIMEOUT;
    k_sem_give(&entry->await_sem);
}

void handle_timer_expired(cipher_daemon_t *d, rpc_event_t *event) {
    rpc_event_opt_timer_expired_t *opts = (rpc_event_opt_timer_expired_t *)event->options;
    cipher_rpc_entry_t *entry = cipher_rpc_get_entry_from_timer(d, opts->timer);
    __ASSERT(entry, "No entry available for timer %p", opts->timer);

    send_rpc_cancel_request(d, entry);
    signal_rpc_caller(d, entry);

    if (!cipher_rpc_entry_unregister(d, entry)) {
        ERROR("could not unregister");
    }
}