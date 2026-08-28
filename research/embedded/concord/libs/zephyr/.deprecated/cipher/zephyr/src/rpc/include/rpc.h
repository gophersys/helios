#ifndef RPC_H
#define RPC_H

#include "events.h"
#include "daemon/daemon.h"

void handle_ctrl_event(cipher_daemon_t *d);

void handle_net_packet_event(cipher_daemon_t *d);

/**
 * @brief Handle a local host request to execute a RPC in a remote host
 *
 * @param d The daemom
 */
void handle_local_request_event(cipher_daemon_t *d);

#endif