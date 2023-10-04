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

void cipher_init_daemon(cipher_daemon_config_t *cfg, cipher_daemon_t *d);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Services
 *---------------------------------------------------------------------------------------------------*/
void cipher_register_local_services(cipher_daemon_t *d, cipher_service_entry_t *entries, size_t num_entries);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  RPC
 *---------------------------------------------------------------------------------------------------*/

#endif  // API_H