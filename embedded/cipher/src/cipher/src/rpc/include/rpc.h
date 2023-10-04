#ifndef RPC_H
#define RPC_H

#include "daemon/daemon.h"

/**
 * @brief Handle a remote host request to execute a RPC in this host
 *
 * @param d The daemom
 */
void handle_remote_rpc_request_event(cipher_daemon_t* d);

/**
 * @brief Handle a local host request to execute a RPC in a remote host
 *
 * @param d The daemom
 */
void handle_local_rpc_request_event(cipher_daemon_t* d);

#endif