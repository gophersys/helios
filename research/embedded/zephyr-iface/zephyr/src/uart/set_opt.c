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

bool uart_set_opt(iface_t *iface, iface_opt_t type, void *option, size_t option_size)
{
    ASSERT_NOT_NULL(iface);
    ASSERT_NOT_NULL(iface->p_uart_dev);
    ASSERT_NOT_NULL(option);

    switch (type)
    {
        case IFACE_OPT_SEND_TIMEOUT:
            if (!uart_net_set_opt(uart_get_stack(), iface->p_uart_dev, UART_DEV_CTX_OPT_SEND_TIMEOUT, option, option_size))
            {
                LOG_ERR("Could not set send timeout for device %s", iface->p_uart_dev->name);
                return false;
            }
            break;
        case IFACE_OPT_RECV_TIMEOUT:
            if (!uart_net_set_opt(uart_get_stack(), iface->p_uart_dev, UART_DEV_CTX_OPT_RECV_TIMEOUT, option, option_size))
            {
                LOG_ERR("Could not set recv timeout for device %s", iface->p_uart_dev->name);
                return false;
            }
            break;
        default:
            LOG_ERR("Unsupported UART option %d", type);
            return false;
    }

    return true;
}