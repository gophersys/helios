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
#include "interface_prv.h"

LOG_MODULE_DECLARE(transport);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/
/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/
/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/

void handle_interface_error(cipher_daemon_t *d, cipher_iface_t *iface, iface_error_t err)
{
    ERROR("Unimplemented, err %d", err);
}