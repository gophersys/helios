#ifndef SOCKET_TAL_H
#define SOCKET_TAL_H

#include "tal.h"

bool socket_connect(tal_config_t *cfg);
bool socket_accept(tal_config_t *cfg);
bool socket_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed);
bool socket_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed);
bool socket_close(const tal_config_t *cfg);

#endif // SOCKET_TAL_H