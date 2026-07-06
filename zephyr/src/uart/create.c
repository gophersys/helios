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

bool uart_create(iface_t *iface)
{
    ASSERT_NOT_NULL(iface);
    ASSERT_NOT_NULL(iface->p_uart_dev);

    uart_net_init(uart_get_stack(), *uart_get_stack_cfg());

    if (!uart_net_register_dev(uart_get_stack(), iface->p_uart_dev))
    {
        LOG_ERR("Could not register device %s with transport stack", iface->p_uart_dev->name);
        return false;
    }

    return true;
}