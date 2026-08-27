#ifndef CIPHER_THREADS_H
#define CIPHER_THREADS_H

#include "daemon/daemon.h"

void cipher_ctrl_thread(void *arg0, void *arg1, void *arg2);
void cipher_sd_thread(void *arg0, void *arg1, void *arg2);
void cipher_router_thread(void *arg0, void *arg1, void *arg2);

void cipher_rpc_init(cipher_daemon_t *d);
void cipher_rpc_thread(void *arg0, void *arg1, void *arg2);
void cipher_rpc_worker_thread(void *arg0, void *arg1, void *arg2);

void cipher_event_thread(void *arg0, void *arg1, void *arg2);
void cipher_stream_thread(void *arg0, void *arg1, void *arg2);

void cipher_interface_conn_thread(void *arg0, void *arg1, void *arg2);
void cipher_interface_send_thread(void *arg0, void *arg1, void *arg2);
void cipher_interface_recv_thread(void *arg0, void *arg1, void *arg2);

#endif