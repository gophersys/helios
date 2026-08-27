#include "api.h"
#include "common.h"
#include <corekinect/iface/iface.h>

// Standard includes
#include <stdbool.h>
#include <stddef.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Private includes
#include "stack/stack.h"

LOG_MODULE_DECLARE(iface);

static bool _recv_conn_req(iface_t *iface, bool *timeout);
static bool _send_conn_ack(iface_t *iface);

bool uart_accept(iface_t *iface, bool *timeout)
{
    ASSERT_NOT_NULL(iface);
    ASSERT_NOT_NULL(iface->p_uart_dev);
    ASSERT_NOT_NULL(timeout);

    uint32_t start_time = k_uptime_get_32();

    if (!_recv_conn_req(iface, timeout))
    {
        return false;
    }

    if (!_send_conn_ack(iface))
    {
        return false;
    }

    LOG_DBG("Successful connection (%dms)", k_uptime_get_32() - start_time);

    return true;
}

static bool _recv_conn_req(iface_t *iface, bool *timeout)
{
    // 1. Await for the remote end to request a connection
    iface_packet_t *conn_req_packet = NULL;
    if (!uart_net_recv_packet(uart_get_stack(), iface->p_uart_dev, &conn_req_packet, timeout))
    {
        if (!timeout)
        {
            LOG_ERR("Could not recv connection req packet from remote end on %s", iface->p_uart_dev->name);
        }
        else
        {
            LOG_WRN("Timeout occurred trying to accept connection from remote end on device %s", iface->p_uart_dev->name);
        }

        return false;
    }

    // 2. Ensure the received packet has data
    if (conn_req_packet == NULL)
    {
        LOG_ERR("%s", "UART transport stack returned a NULL packet. This is a software bug.");
        k_fatal_halt(0);
    }

    // 3. Check if we got a connection request
    bool request = conn_req_packet->header.type == IFACE_PACKET_TYPE_CONN_REQ ? true : false;

    // 4. Free the packet from the packet buffer from the stack
    if (!uart_net_free_recv_packet(uart_get_stack(), iface->p_uart_dev, conn_req_packet))
    {
        LOG_WRN("%s", "Could not free request packet");
        return false;
    }

    if (!request)
    {
        LOG_ERR("Unexpected packet type %d from remote end on %s. Expected CONN_REQ", conn_req_packet->header.type, iface->p_uart_dev->name);
        return false;
    }

    return true;
}

static bool _send_conn_ack(iface_t *iface)
{
    // First we store the user's timeout option
    uint16_t old_timeout = 0;
    if (!uart_net_get_send_timeout(uart_get_stack(), iface->p_uart_dev, &old_timeout))
    {
        LOG_ERR("%s", "Error saving original send timeout value");
        return false;
    }

    // Set the timeout to the internal library value
    uint16_t tmp_timeout = uart_get_internal_send_timeout();
    if (!uart_net_set_opt(uart_get_stack(), iface->p_uart_dev, UART_DEV_CTX_OPT_SEND_TIMEOUT, &tmp_timeout, sizeof(tmp_timeout)))
    {
        LOG_ERR("Could not set internal send timeout for %s", iface->p_uart_dev->name);
        return false;
    }

    // To start a connection, we "request" a connection from the remote end
    iface_packet_t  conn_ack_packet =
    {
        .header = {
            .type = IFACE_PACKET_TYPE_CONN_ACK,
            .sequence_num = 0,
            .length = 0,
        },
        .p_data = NULL,
    };

    // We attempt to send the packet
    bool timeout = false;
    bool success = uart_net_send_packet(uart_get_stack(), iface->p_uart_dev, &conn_ack_packet, &timeout);

    // Set the send timeout back to the original user value
    if (!uart_net_set_opt(uart_get_stack(), iface->p_uart_dev, UART_DEV_CTX_OPT_SEND_TIMEOUT, &old_timeout, sizeof(old_timeout)))
    {
        LOG_ERR("Could not reset send timeout for %s", iface->p_uart_dev->name);
        return false;
    }

    if (!success)
    {
        LOG_ERR("Could not send connection ack packet to remote end on %s, timeout: %s, (%dms)",
                iface->p_uart_dev->name,
                timeout ? "yes" : "no",
                old_timeout);

        return false;
    }

    return true;
}