#ifndef RPC_H
#define RPC_H

#include "daemon/daemon.h"

void handle_rpc_request_packet(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item);
void handle_rpc_response_packet(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item);

/**
 * @brief Handle a local host request to execute a RPC in a remote host
 *
 * @param d The daemom
 */
void handle_local_request(cipher_daemon_t *d);
void handle_rpc_event(cipher_daemon_t *d);

#endif