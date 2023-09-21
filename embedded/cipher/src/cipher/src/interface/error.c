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

void handle_interface_error(cipher_daemon_t *d, cipher_iface_t *iface, iface_error_t err)
{
    ERROR("Daemon %d, interface %d error %d", d->id, iface->id, err);
}