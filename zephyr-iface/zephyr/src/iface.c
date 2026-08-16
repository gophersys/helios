#include <corekinect/iface/iface.h>  //TODO: fix me to not be relative path

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Private includes
#include "socket/socket.h"
#include "uart/api.h"

LOG_MODULE_REGISTER(iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

/**
 * Use the same API definition in the header file of this module to implement a new interface, which:
 *  - Should work like a single socket connection
 *  - Should behave like a stream based transport layer
 *
 * In you implementation you need NOT to check for NULL configurations, this module asserts for this.
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Interface for TAL implementations
 */
typedef struct
{
    bool (*create)(iface_t *iface);
    bool (*set_opt)(iface_t *iface, iface_opt_t type, void *option, size_t option_size);
    bool (*connect)(iface_t *iface, bool *timeout);
    bool (*accept)(iface_t *iface, bool *timeout);
    bool (*send)(const iface_t *iface, const void *buffer, const size_t buffer_size,
                 uint16_t *send_count, bool *conn_closed, bool *timeout);
    bool (*recv)(const iface_t *iface, void *buffer, const size_t buffer_size,
                 uint16_t *recv_count, bool *conn_closed, bool *timeout);
    bool (*close)(const iface_t *iface);
} tal_interface_ops_t;

/**
 * @brief Look up table of implemented interfaces. Simplifies implementation
 *
 */
static const tal_interface_ops_t tal_ops[] =
{
#ifdef CONFIG_CK_IFACE_LIB_SOCKETS
    [IFACE_TYPE_SOCKET] = {
        .create = socket_create,
        .set_opt = socket_set_opt,
        .connect = socket_connect,
        .accept = socket_accept,
        .send = socket_send,
        .recv = socket_recv,
        .close = socket_close,
    },
#endif
#ifdef CONFIG_CK_IFACE_LIB_UART
    [IFACE_TYPE_UART] = {
        .create = uart_create,
        .set_opt = uart_set_opt,
        .connect = uart_connect,
        .accept = uart_accept,
        .send = uart_send,
        .recv = uart_recv,
        .close = uart_close,
    },
#endif
};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Check that the interface is not NULL, and that it's implemented
 *
 * @param iface The desired interface
 * @param func_name The name of the caller (__func__)
 */
static void iface_assert(const iface_t *iface, const char *func_name)
{
    __ASSERT(iface, "%s Config pointer cannot be NULL", func_name);
    __ASSERT(iface->type < IFACE_TYPE_MAX, "%s Unknown or unimplemented interface: %d",
             func_name, iface->type);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
bool iface_create(iface_t *iface)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].create(iface);
}

bool iface_set_opt(iface_t *iface, iface_opt_t type, void *option, size_t option_size)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].set_opt(iface, type, option, option_size);
}

bool iface_connect(iface_t *iface, bool *timeout)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].connect(iface, timeout);
}

bool iface_accept(iface_t *iface, bool *timeout)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].accept(iface, timeout);
}

bool iface_send(const iface_t *iface, const void *buffer, const size_t buffer_size,
                uint16_t *send_count, bool *conn_closed, bool *timeout)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].send(iface, buffer, buffer_size, send_count, conn_closed, timeout);
}

bool iface_recv(const iface_t *iface, void *buffer, const size_t buffer_size,
                uint16_t *recv_count, bool *conn_closed, bool *timeout)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].recv(iface, buffer, buffer_size, recv_count, conn_closed, timeout);
}

bool iface_close(const iface_t *iface)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].close(iface);
}