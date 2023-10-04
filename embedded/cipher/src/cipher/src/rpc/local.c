// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/registry.h"
#include "protocol/protocol.h"
#include "protocol/serdes.h"
#include "transport/transport.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "packet.h"
#include "rpc.h"
#include "threads.h"

LOG_MODULE_DECLARE(rpc);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Assert
 *---------------------------------------------------------------------------------------------------*/

void handle_local_rpc_request_event(cipher_daemon_t *d) {
}