#ifndef SOCKET_IFACE_H
#define SOCKET_IFACE_H

#include <corekinect/iface/iface.h>

/**
 * @brief Implemented against the iface specification, using Zephyr's POSIX sockets
 */

bool socket_create(iface_t *iface);
bool socket_set_opt(iface_t *iface, iface_opt_t type, void *option, size_t option_size);
bool socket_connect(iface_t *iface, bool *timeout);
bool socket_accept(iface_t *iface, bool *timeout);
bool socket_send(const iface_t *iface, const void *buffer, const size_t buffer_size,
                 uint16_t *send_count, bool *conn_closed, bool *timeout);
bool socket_recv(const iface_t *iface, void *buffer, const size_t buffer_size,
                 uint16_t *recv_count, bool *conn_closed, bool *timeout);
bool socket_close(const iface_t *iface);

#endif  // SOCKET_IFACE_H