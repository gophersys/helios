#include "tal.h"

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "utils.h"
#include "socket_tal.h"

LOG_MODULE_REGISTER(tal, TAL_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

/**
 * Use the same API definition in the header file of this module to implement a new interface, which:
 *  - Should work like a single socket connection
 *  - Should behave like a stream based transport layer
 *
 * In you implementation you need NOT to check for NULL interfaces, this module asserts for this.
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Interface for TAL implementations
 */
typedef struct
{
    bool (*create)(tal_interface_t *iface);
    bool (*set_opt)(tal_interface_t *iface, tal_option_type_t type, void *option, size_t option_size);
    bool (*connect)(tal_interface_t *iface, bool *timeout);
    bool (*accept)(tal_interface_t *iface, bool *timeout);
    bool (*send)(const tal_interface_t *iface, const void *buffer, const size_t buffer_size,
                 uint16_t *send_count, bool *conn_closed);
    bool (*recv)(const tal_interface_t *iface, void *buffer, const size_t buffer_size,
                 uint16_t *recv_count, bool *conn_closed);
    bool (*close)(const tal_interface_t *iface);
} tal_interface_ops_t;

/**
 * @brief Look up table of implemented interfaces. Simplifies implementation
 *
 */
static const tal_interface_ops_t tal_ops[] = {
    [TAL_INTERFACE_TYPE_SOCKET] = {
        .create = socket_create,
        .set_opt = socket_set_opt,
        .connect = socket_connect,
        .accept = socket_accept,
        .send = socket_send,
        .recv = socket_recv,
        .close = socket_close,
    },
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
static void iface_assert(const tal_interface_t *iface, const char *func_name)
{
    __ASSERT(iface, "%s Interface pointer cannot be NULL", func_name);

    // TODO: Implement UART, and change macro below to TAL_INTERFACE_TYPE_MAX
    __ASSERT(iface->type < TAL_INTERFACE_TYPE_UART, "%s Unknown or unimplemented interface: %d",
             func_name, iface->type);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
bool tal_create(tal_interface_t *iface)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].create(iface);
}

bool tal_set_opt(tal_interface_t *iface, tal_option_type_t type, void *option, size_t option_size)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].set_opt(iface, type, option, option_size);
}

bool tal_connect(tal_interface_t *iface, bool *timeout)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].connect(iface, timeout);
}

bool tal_accept(tal_interface_t *iface, bool *timeout)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].accept(iface, timeout);
}

bool tal_send(const tal_interface_t *iface, const void *buffer, const size_t buffer_size,
              uint16_t *send_count, bool *conn_closed)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].send(iface, buffer, buffer_size, send_count, conn_closed);
}

bool tal_recv(const tal_interface_t *iface, void *buffer, const size_t buffer_size,
              uint16_t *recv_count, bool *conn_closed)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].recv(iface, buffer, buffer_size, recv_count, conn_closed);
}

bool tal_close(const tal_interface_t *iface)
{
    iface_assert(iface, __func__);
    return tal_ops[iface->type].close(iface);
}