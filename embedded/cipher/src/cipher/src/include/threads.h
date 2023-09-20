#ifndef CIPHER_THREADS_H
#define CIPHER_THREADS_H

void cipher_controller_thread(void *arg0, void *arg1, void *arg2);
void cipher_sd_thread(void *arg0, void *arg1, void *arg2);
void cipher_router_thread(void *arg0, void *arg1, void *arg2);
void cipher_rpc_thread(void *arg0, void *arg1, void *arg2);
void cipher_event_thread(void *arg0, void *arg1, void *arg2);

void cipher_interface_conn_thread(void *arg0, void *arg1, void *arg2);
void cipher_interface_send_thread(void *arg0, void *arg1, void *arg2);
void cipher_interface_recv_thread(void *arg0, void *arg1, void *arg2);

#endif