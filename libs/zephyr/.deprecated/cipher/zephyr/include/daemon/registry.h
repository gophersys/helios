#ifndef REGISTRY_H
#define REGISTRY_H

// Cipher includes
#include <corekinect/cipher/config.h>
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/service.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Services
 *---------------------------------------------------------------------------------------------------*/


/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  RPC
 *---------------------------------------------------------------------------------------------------*/
bool cipher_rpc_exists(cipher_daemon_t *d, cipher_registry_rpc_entry_t *entry);
bool cipher_rpc_entry_register(cipher_daemon_t *d, cipher_registry_rpc_entry_t *entry);
cipher_registry_rpc_entry_t *cipher_rpc_get_entry(cipher_daemon_t *d, uint16_t service_id, uint16_t op_id);
void cipher_rpc_entry_unregister(cipher_daemon_t *d, cipher_registry_rpc_entry_t *entry);
cipher_ops_entry_t *find_op_in_registry(cipher_daemon_t *d, cipher_header_t *header);

#endif