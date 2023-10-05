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
void handle_iface_disconnected(cipher_daemon_t *d, rpc_event_t *event) {
    // Unblock the semaphore of the waiting function and chekc that it was taken to unallocate packet
    // Remove this rpc request from the active list
}
