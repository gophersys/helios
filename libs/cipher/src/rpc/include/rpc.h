#ifndef RPC_H
#define RPC_H

#include "controller.h"
#include "daemon/daemon.h"

void handle_rpc_packet(cipher_daemon_t *d);

void handle_iface_disconnected(cipher_daemon_t *d, rpc_event_t *event);
void handle_timer_expired(cipher_daemon_t *d, rpc_event_t *event);

/**
 * @brief Handle a local host request to execute a RPC in a remote host
 *
 * @param d The daemom
 */
void handle_local_request(cipher_daemon_t *d);

#endif