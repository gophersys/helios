#ifndef SOCKET_TAL_H
#define SOCKET_TAL_H

#include "tal.h"

/**
 * @brief Implemented against the tal interface specification, using Zephyr's POSIX sockets
 */

bool socket_create(tal_interface_t *iface);
bool socket_set_opt(tal_interface_t *iface, tal_option_type_t type, void *option, size_t option_size);
bool socket_connect(tal_interface_t *iface, bool *timeout);
bool socket_accept(tal_interface_t *iface, bool *timeout);
bool socket_send(const tal_interface_t *iface, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed);
bool socket_recv(const tal_interface_t *iface, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed);
bool socket_close(const tal_interface_t *iface);

#endif // SOCKET_TAL_H