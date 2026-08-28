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

bool uart_send(const iface_t *p_iface, const void *p_buffer, const size_t buffer_size,
               uint16_t *p_send_count, bool *p_conn_closed, bool *p_timeout)
{
    ASSERT_NOT_NULL(p_iface);
    ASSERT_NOT_NULL(p_buffer);
    ASSERT_NOT_NULL(p_send_count);
    ASSERT_NOT_NULL(p_conn_closed);
    ASSERT_NOT_NULL(p_timeout);

    iface_packet_t  send_packet =
    {
        .header = {
            .type = IFACE_PACKET_TYPE_DATA,
            .sequence_num = 0,
            .length = buffer_size,
        },
        .p_data = (uint8_t *)p_buffer,
    };

    // We attempt to send the packet
    if (!uart_net_send_packet(uart_get_stack(), p_iface->p_uart_dev, &send_packet, p_timeout))
    {
        uint16_t send_timeout = 0;
        if (!uart_net_get_send_timeout(uart_get_stack(), p_iface->p_uart_dev, &send_timeout))
        {
            LOG_WRN("%s", "Could not get send timeout from stack");
        }

        LOG_ERR("Could not send packet to remote end on %s, timeout: %s, (%dms)", p_iface->p_uart_dev->name,
                p_timeout ? "yes" : "no",
                send_timeout);

        return false;
    }

    //TODO: p_send_count should be set correctly
    *p_send_count = buffer_size;

    return true;
}