// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "transport/transport.h"
#include "daemon/daemon.h"
#include "utils/err.h"

// Private include
#include "threads.h"
#include "interface.h"

LOG_MODULE_DECLARE(iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/
// TODO: Implement a better error handler for interfaces

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/
void handle_iface_error(cipher_daemon_t *d, cipher_iface_t *iface, iface_error_t err,
                        void *options, size_t option_size)
{
    ERROR("Daemon %d, interface %d error %d", d->id, iface->id, err);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                        Timeout & Disconnect Handlers
 *---------------------------------------------------------------------------------------------------*/
void handle_iface_timeout(cipher_daemon_t *d, cipher_iface_t *iface, const char *func)
{
    // TODO: What do we actually do about timeouts
    ERROR("%s: Timeout while trying to send on iface %d, daemon %d", func, iface->id, d->id);
}

void handle_iface_disconnect(cipher_daemon_t *d, cipher_iface_t *iface, const char *func)
{
    LOG("Iface %d, daemon %d, disconnected, signaling iface controller", iface->id, d->id);

    // TODO: Test if disconnects actually work lol

    // Signal a disconnection
    k_sem_give(&iface->disconn_sem);
}