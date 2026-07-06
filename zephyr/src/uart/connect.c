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

/**
 * @brief This function sends a connection request to the remote end.
 *
 * @param[in] p_iface
 * @param[out] timeout
 * @return true If the packet was sent and all operations succeeded
 * @return false If any operation (timeout, send, err, etc) failed
 */
static bool _send_conn_req(iface_t *p_iface);

/**
 * @brief This function awaits for the remote end to respond back to our connection request.
 *
 * Because the expected behaviour of this function is to return almost immediately if there's
 * no remote end connected, we temporarily set the send_timeout of the uart socket to a small
 * period of time so that we can mimic the behaviour of TCP sockets on connect().
 *
 * @param[in] p_iface
 * @param[out] timeout
 * @return true If the remote end responded and all operations succeeded
 * @return false If any operation (timeout, recv err, free(), etc) failed
 */
static bool _recv_conn_ack(iface_t *p_iface, bool *timeout);

bool uart_connect(iface_t *p_iface, bool *timeout)
{
    ASSERT_NOT_NULL(p_iface);
    ASSERT_NOT_NULL(p_iface->p_uart_dev);
    ASSERT_NOT_NULL(timeout);

    uint32_t start_time = k_uptime_get_32();

    if (!_send_conn_req(p_iface))
    {
        return false;
    }

    if (!_recv_conn_ack(p_iface, timeout))
    {
        return false;
    }

    LOG_DBG("Successful connection (%dms)", k_uptime_get_32() - start_time);

    return true;
}

static bool _send_conn_req(iface_t *p_iface)
{
    // First we store the user's timeout option
    uint16_t old_timeout = 0;
    if (!uart_net_get_send_timeout(uart_get_stack(), p_iface->p_uart_dev, &old_timeout))
    {
        LOG_ERR("%s", "Error saving original send timeout value");
        return false;
    }

    // Set the timeout to the internal library value
    uint16_t tmp_timeout = uart_get_internal_send_timeout();
    if (!uart_net_set_opt(uart_get_stack(), p_iface->p_uart_dev, UART_DEV_CTX_OPT_SEND_TIMEOUT, &tmp_timeout, sizeof(tmp_timeout)))
    {
        LOG_ERR("Could not set internal send timeout for %s", p_iface->p_uart_dev->name);
        return false;
    }

    // To start a connection, we "request" a connection from the remote end
    iface_packet_t  conn_req_packet =
    {
        .header = {
            .type = IFACE_PACKET_TYPE_CONN_REQ,
            .sequence_num = 0,
            .length = 0,
        },
        .p_data = NULL,
    };

    // We attempt to send the packet
    bool timeout = false;
    bool success = uart_net_send_packet(uart_get_stack(), p_iface->p_uart_dev, &conn_req_packet, &timeout);

    // Set the send timeout back to the original user value
    if (!uart_net_set_opt(uart_get_stack(), p_iface->p_uart_dev, UART_DEV_CTX_OPT_SEND_TIMEOUT, &old_timeout, sizeof(old_timeout)))
    {
        LOG_ERR("Could not reset send timeout for %s", p_iface->p_uart_dev->name);
        return false;
    }

    if (!success)
    {
        LOG_ERR("Could not send connection request packet to remote end on %s, timeout: %s, (%dms)",
                p_iface->p_uart_dev->name,
                timeout ? "yes" : "no",
                old_timeout);

        return false;
    }

    return true;
}

static bool _recv_conn_ack(iface_t *p_iface, bool *timeout)
{
    // First we store the user's timeout option
    uint16_t old_timeout = 0;
    if (!uart_net_get_recv_timeout(uart_get_stack(), p_iface->p_uart_dev, &old_timeout))
    {
        LOG_ERR("%s", "Error saving original recv timeout value");
        return false;
    }

    // Set the timeout to the internal library value
    uint16_t tmp_timeout = uart_get_internal_recv_timeout();
    if (!uart_net_set_opt(uart_get_stack(), p_iface->p_uart_dev, UART_DEV_CTX_OPT_RECV_TIMEOUT, &tmp_timeout, sizeof(tmp_timeout)))
    {
        LOG_ERR("Could not set internal recv timeout for %s", p_iface->p_uart_dev->name);
        return false;
    }

    // Await for the remote end to acknowledge the connection
    iface_packet_t *conn_ack_packet = NULL;
    if (!uart_net_recv_packet(uart_get_stack(), p_iface->p_uart_dev, &conn_ack_packet, timeout))
    {
        if (!timeout)
        {
            LOG_ERR("Could not recv connection ack packet from remote end on %s", p_iface->p_uart_dev->name);
        }
        else
        {
            LOG_WRN("Timeout occurred trying to connect to remote end on device %s", p_iface->p_uart_dev->name);
        }

        return false;
    }

    // Ensure the received packet has data
    if (conn_ack_packet == NULL)
    {
        LOG_ERR("%s", "UART transport stack returned a NULL packet. This is a software bug.");
        k_fatal_halt(0);
    }

    // Check if we got a succesful response
    bool connected = conn_ack_packet->header.type == IFACE_PACKET_TYPE_CONN_ACK ? true : false;

    // Free the packet from the packet buffer from the stack
    if (!uart_net_free_recv_packet(uart_get_stack(), p_iface->p_uart_dev, conn_ack_packet))
    {
        LOG_WRN("%s", "Could not free ack packet");
        return false;
    }

    // Set the recv timeout back to the original user value
    if (!uart_net_set_opt(uart_get_stack(), p_iface->p_uart_dev, UART_DEV_CTX_OPT_RECV_TIMEOUT, &old_timeout, sizeof(old_timeout)))
    {
        LOG_ERR("Could not reset recv timeout for %s", p_iface->p_uart_dev->name);
        return false;
    }

    if (!connected)
    {
        LOG_ERR("Unexpected packet type %d from remote end on %s. Expected CONN_ACK", conn_ack_packet->header.type, p_iface->p_uart_dev->name);
        return false;
    }

    return true;
}