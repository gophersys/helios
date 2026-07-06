#ifndef IFACE_UART_API_H
#define IFACE_UART_API_H

// Standard includes
#include <stddef.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/kernel.h>

// Corekinect includes
#include <corekinect/iface/iface.h>

/**
 * @brief Implemented against the iface specification //TODO: tf is this comment
 */

bool uart_create(iface_t *iface);
bool uart_set_opt(iface_t *iface, iface_opt_t type, void *option, size_t option_size);
bool uart_connect(iface_t *iface, bool *timeout);
bool uart_accept(iface_t *iface, bool *timeout);
bool uart_send(const iface_t *iface, const void *buffer, const size_t buffer_size,
               uint16_t *send_count, bool *conn_closed, bool *timeout);
bool uart_recv(const iface_t *iface, void *buffer, const size_t buffer_size,
               uint16_t *recv_count, bool *conn_closed, bool *timeout);
bool uart_close(const iface_t *iface);

#endif  // IFACE_UART_API_H