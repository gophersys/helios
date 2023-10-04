#ifndef RPC_H
#define RPC_H

#include "daemon/daemon.h"

void handle_remote_rpc_event(cipher_daemon_t* d);
void handle_local_rpc_event(cipher_daemon_t* d);

#endif