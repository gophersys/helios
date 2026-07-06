// Standard includes
#include <errno.h>
#include <stdio.h>
#include <string.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>  // <- This is how you'd include the library in your app

LOG_MODULE_REGISTER(socket_server);

// Uart Device
#define UART_NODE DT_ALIAS(iface_uart)  // This has to match the entry in the .overaly file
const struct device *const uart_dev = DEVICE_DT_GET(UART_NODE);

int main(void) {
    // Server config
    iface_t server_cfg =
        {
            .type = IFACE_TYPE_UART,
            .link = IFACE_LINK_TYPE_SERVER,
            .p_uart_dev = uart_dev,
        };

    while (true) {
        if (!iface_create(&server_cfg)) {
            LOG_ERR("Could not create iface");
            break;
        }

        LOG_INF("Server is running and waiting for connection...");

        bool timeout = false;
        if (!iface_accept(&server_cfg, &timeout)) {
            LOG_ERR("Error accepting connection, timeout: %s", timeout ? "yes" : "no");
            break;
        }

        LOG_INF("Server got a connection from client");

        bool conn_closed = false;
        while (true) {
            uint16_t recv_bytes = 0;
            static char buffer[1024] = {0};
            if (!iface_recv(&server_cfg, buffer, sizeof(buffer), &recv_bytes, &conn_closed, &timeout)) {
                LOG_ERR("Could not recv, timeout: %s, conn_closed: %s", timeout ? "yes" : "no", conn_closed ? "yes" : "no");
                break;
            }

            LOG_INF("Server received: %s", buffer);
            uint16_t sent_bytes = 0;
            if (!iface_send(&server_cfg, buffer, recv_bytes, &sent_bytes, &conn_closed, &timeout)) {
                LOG_ERR("Could not send, timeout: %s, conn_closed: %s", timeout ? "yes" : "no", conn_closed ? "yes" : "no");
                break;
            }
        }

        if (!iface_close(&server_cfg)) {
            LOG_ERR("Could not close iface");
            break;
        }
    }

    LOG_ERR("Fatal error occurred in %s", __func__);
    k_fatal_halt(0);
}