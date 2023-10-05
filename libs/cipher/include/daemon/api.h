#ifndef API_H
#define API_H

#include <stdbool.h>
#include <zephyr/kernel.h>

// CoreKinect includes
#include "config/daemon.h"
#include "config/default.h"
#include "daemon/daemon.h"
#include "transport/transport.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/

void cipher_daemon_init(cipher_daemon_config_t *cfg, cipher_daemon_t *d);

void cipher_daemon_start(cipher_daemon_t *d);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Services
 *---------------------------------------------------------------------------------------------------*/
void cipher_register_local_services(cipher_daemon_t *d, cipher_service_entry_t *entries, size_t num_entries);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  RPC
 *---------------------------------------------------------------------------------------------------*/
void cipher_remote_rpc_handler(cipher_daemon_t *d, cipher_rpc_entry_t *entry);

#endif  // API_H