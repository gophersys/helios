#ifndef SOCKET_TAL_H
#define SOCKET_TAL_H

#include "transport/transport.h"

/**
 * @brief Implemented against the tal interface specification, using Zephyr's POSIX sockets
 */

bool socket_create(tal_config_t *cfg);
bool socket_set_opt(tal_config_t *cfg, tal_option_type_t type, void *option, size_t option_size);
bool socket_connect(tal_config_t *cfg, bool *timeout);
bool socket_accept(tal_config_t *cfg, bool *timeout);
bool socket_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size,
                 uint16_t *send_count, bool *conn_closed, bool *timeout);
bool socket_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size,
                 uint16_t *recv_count, bool *conn_closed, bool *timeout);
bool socket_close(const tal_config_t *cfg);

#endif // SOCKET_TAL_H