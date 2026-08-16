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

bool uart_recv(const iface_t *p_iface, void *p_buffer, const size_t buffer_size,
               uint16_t *p_recv_count, bool *p_conn_closed, bool *p_timeout)
{
    ASSERT_NOT_NULL(p_iface);
    ASSERT_NOT_NULL(p_buffer);
    ASSERT_NOT_NULL(p_recv_count);
    ASSERT_NOT_NULL(p_conn_closed);
    ASSERT_NOT_NULL(p_timeout);

    // 1. Call the UART stack to receive a complete packet on the interface
    iface_packet_t *recv_packet = NULL;
    if (!uart_net_recv_packet(uart_get_stack(), p_iface->p_uart_dev, &recv_packet, p_timeout))
    {
        uint16_t recv_timeout = 0;
        if (!uart_net_get_send_timeout(uart_get_stack(), p_iface->p_uart_dev, &recv_timeout))
        {
            LOG_WRN("%s", "Could not get recv timeout from stack");
        }

        if (!*p_timeout)
        {
            LOG_ERR("Could not recv packet frpm remote end on %s", p_iface->p_uart_dev->name);
        }
        else
        {
            LOG_WRN("Recv timeout: %d ms", recv_timeout);
        }

        return false;
    }

    // 2. Ensure the received packet has data
    if (recv_packet == NULL)
    {
        LOG_ERR("%s", "UART transport stack returned a NULL packet. This is a software bug.");
        k_fatal_halt(0);
    }

    // 3. Check if we got a valid packet type
    bool status = false;
    if (recv_packet->header.type == IFACE_PACKET_TYPE_DATA)
    {
        if (recv_packet->header.length > buffer_size)
        {
            LOG_ERR("Recv buffer size passed is only %d bytes, packet received is %d bytes", buffer_size, recv_packet->header.length);
        }

        // Copy the payload into the user buffer
        memcpy(p_buffer, recv_packet->p_data, recv_packet->header.length);
        *p_recv_count = recv_packet->header.length;
        status = true;
    }
    else if (recv_packet->header.type == IFACE_PACKET_TYPE_CLOSE_REQ)
    {
        LOG_DBG("A disconnection from the remote end was requested");
        *p_conn_closed = true;

        //TODO: Do we send a connection ACK here? how do we close the iface after?
    }

    // 4. Free the packet from the packet buffer from the stack regardless
    if (!uart_net_free_recv_packet(uart_get_stack(), p_iface->p_uart_dev, recv_packet))
    {
        LOG_WRN("%s", "Could not free receive packet buffer");
        return false;
    }

    return status;
}