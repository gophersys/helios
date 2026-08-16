#ifndef IFACE_UART_COMMON_H
#define IFACE_UART_COMMON_H

// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Private library includes
#include "stack/stack.h"

/**
 * @def ASSERT_NOT_NULL(a)
 * @brief Checks if the variable is NULL.
 *
 * @param a The variable to check.
 */
#define ASSERT_NOT_NULL(a)                                    \
    if ((a) == NULL) {                                        \
        LOG_ERR("Assertion failed in %s: %s is NULL", __func__, #a); \
        return false;                                         \
    }

uart_stack_t *uart_get_stack(void);
uart_stack_config_t *uart_get_stack_cfg(void);
uint16_t uart_get_internal_send_timeout(void);
uint16_t uart_get_internal_recv_timeout(void);

#endif // IFACE_UART_COMMON_H