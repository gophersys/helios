#ifndef API_H
#define API_H

#include <stdbool.h>
#include <zephyr/kernel.h>

// CoreKinect includes
#include <corekinect/cipher/config.h>
#include <corekinect/iface/iface.h>

#include "config/default.h"
#include "daemon/daemon.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/

void cipher_daemon_init(cipher_daemon_config_t *cfg, cipher_daemon_t *d);
void cipher_daemon_start(cipher_daemon_t *d);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Services
 *---------------------------------------------------------------------------------------------------*/
void cipher_register_local_services(cipher_daemon_t *d, cipher_service_entry_t *entries, size_t num_entries);
void cipher_register_remote_services(cipher_daemon_t *d, cipher_service_entry_t *entries, size_t num_entries);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  RPC
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Ask daemon to start an RPC request.
 *
 * This API blocks async on a semaphore, which can be unblocked due to errors or a response back from
 * the remote host. See the entry field for more info
 *
 * @param d The daemon
 * @param entry All info needed to execute RPC
 */
void cipher_rpc_handler(cipher_daemon_t *d, cipher_registry_rpc_entry_t *entry);

#endif  // API_H