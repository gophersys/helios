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

bool uart_close(const iface_t *iface)
{
    if (!uart_net_unregister_dev(uart_get_stack(), iface->p_uart_dev))
    {
        LOG_ERR("Could not unregister device %s with transport stack", iface->p_uart_dev->name);
        return false;
    }

    return true;
}
