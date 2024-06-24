#include "config.h"

// Zephyr includes
#include <zephyr/device.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Uart device
#define UART_NODE DT_ALIAS(iface_uart)
static const struct device *const _p_uart_dev = DEVICE_DT_GET(UART_NODE);

cipher_daemon_config_t *get_daemon_config(void)
{
    static cipher_daemon_config_t _config =
    {
        .num_server_ifaces = 1,
        .server_ifaces = {
            {
                .type = IFACE_TYPE_UART,
                .link = IFACE_LINK_TYPE_SERVER,
                .p_uart_dev = _p_uart_dev,
            }
        },
    };

    return &_config;
}