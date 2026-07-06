// Standard includes
#include <errno.h>
#include <stdio.h>
#include <string.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
// #include <zephyr/net/dns_resolve.h>
// #include <zephyr/net/net_config.h>
// #include <zephyr/net/net_context.h>
// #include <zephyr/net/net_core.h>
// #include <zephyr/net/net_if.h>
// #include <zephyr/net/net_mgmt.h>
// #include <zephyr/net/socket.h>
#include <zephyr/drivers/dma.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/sys/ring_buffer.h>

// Corekinect includes
#include <corekinect/iface/iface.h>

LOG_MODULE_REGISTER(socket_client);

// Uart Device
#define UART_NODE DT_ALIAS(iface_uart)  // This has to match the entry in the .overaly file
const struct device *const uart_dev = DEVICE_DT_GET(UART_NODE);

/* this is to enable the level shifter to be able to use usart1 as the debug output */
#define COMM_EN DT_NODELABEL(comm_en)
const struct gpio_dt_spec comm_en = GPIO_DT_SPEC_GET(COMM_EN, gpios);

// Configuration
#define SERVER_IP "10.4.2.3"  // Client connects to
#define SERVER_PORT 12345

// screen -ls | grep -v "Dead" | cut -d. -f1 | awk '{print $1}' | xargs -I {} screen -S {} -X quit

// Private functions
static void print_net_addr(void);
static void socket_server(void);
static void socket_client(void);
static void uart_server(void);
static void uart_client(void);

// UART callback
uint8_t reply_buffer[1024];
volatile size_t reply_length = 0;

#define REPLY_BUFFER_SIZE 64
#define TIMEOUT K_SECONDS(5)

static struct k_timer reply_timer;
void timer_expiry_function(struct k_timer *timer_id) {
    printk("Reply not received within 5 seconds, aborting...\n");
    uart_rx_disable(uart_dev);  // Assuming uart_dev is globally accessible
}

void uart_callback(const struct device *dev, struct uart_event *evt, void *user_data) {
    switch (evt->type) {
        case UART_TX_DONE:
            printk("Transmission complete. Waiting for reply...\n");
            // Transmission done, now enable RX to wait for the reply
            uart_rx_enable(dev, reply_buffer, REPLY_BUFFER_SIZE, SYS_FOREVER_MS);
            k_timer_start(&reply_timer, TIMEOUT, K_NO_WAIT);
            break;

        case UART_RX_RDY:
            // Data received
            reply_length += evt->data.rx.len;
            printk("Received data: %.*s\n", evt->data.rx.len, &reply_buffer[reply_length - evt->data.rx.len]);
            // data was received, stop the timer
            k_timer_stop(&reply_timer);
            break;

        case UART_RX_DISABLED:
            printk("UART RX disabled\n");
            break;

        case UART_TX_ABORTED:
            printk("Transmission aborted\n");
            break;

        case UART_RX_BUF_REQUEST:
            // The driver requests a new buffer for reception
            break;

        case UART_RX_BUF_RELEASED:
            // The driver releases a buffer, no action needed for simple cases
            break;

        case UART_RX_STOPPED:
            printk("UART reception stopped: %d\n", evt->data.rx_stop.reason);
            break;

        default:
            break;
    }
}
// TODO: this example
/*-----------------------------------------------------------------------------------------------------
 *                                                                                                 Main
 *---------------------------------------------------------------------------------------------------*/
int main(void) {
    // if (!device_is_ready(uart_dev))
    // {
    //     LOG_ERR("UART device not ready");
    // }
    if (!gpio_is_ready_dt(&comm_en))  // make sure that the GPIO device is ready
    {
        LOG_ERR("COMM_EN GPIO device not ready");
    }
    if (gpio_pin_configure(comm_en.port, comm_en.pin, GPIO_OUTPUT_LOW))  // configure the GPIO pin as output and set it low
    {
        LOG_ERR("COMM_EN GPIO pin configure failed");
    }
    // // print_net_addr();

    // // Sockets
    // // socket_server();
    // // socket_client();

    gpio_pin_set(comm_en.port, comm_en.pin, 1);  // set the GPIO pin high to enable the level shifter

    // LOG_INF("Hello World!");

    // char msg[] = "Hello from client\n";
    // int err;

    // k_timer_init(&reply_timer, timer_expiry_function, NULL);

    // // Set the callback function
    // uart_callback_set(uart_dev, uart_callback, NULL);

    // printk("Sending message over USART2...\n");

    // // Transmit the message
    // err = uart_tx(uart_dev, (const uint8_t *)msg, sizeof(msg), SYS_FOREVER_MS);
    // if (err)
    // {
    //     printk("Failed to start UART transmission (err: %d)\n", err);
    // }
    // k_msleep(10000);
    // Uart
    // uart_server();
    // volatile int i = 0;
    // while (true)
    // {
    //     LOG_INF("Hello world %i", i++);
    //     k_msleep(2000);
    // }

    uart_client();
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Helpers
 *---------------------------------------------------------------------------------------------------*/
// static void print_net_addr(void)
// {
//     struct net_if *iface;
//     iface = net_if_get_default();
//     char buf[NET_IPV4_ADDR_LEN];

//     for (size_t i = 0; i < NET_IF_MAX_IPV4_ADDR; i++)
//     {

//         LOG_INF("IP Addr: %s",
//                 net_addr_ntop(AF_INET,
//                               &iface->config.ip.ipv4->unicast[i].address.in_addr,
//                               buf, sizeof(buf)));

//         LOG_INF("Subnet: %s",
//                 net_addr_ntop(AF_INET,
//                               &iface->config.ip.ipv4->netmask,
//                               buf, sizeof(buf)));
//         LOG_INF("Router: %s",
//                 net_addr_ntop(AF_INET,
//                               &iface->config.ip.ipv4->gw,
//                               buf, sizeof(buf)));
//     }

//     const struct dns_resolve_context *ctx = dns_resolve_get_default();

//     for (int i = 0; ctx->servers[i].dns_server.sa_family != AF_UNSPEC; ++i)
//     {
//         if (ctx->servers[i].dns_server.sa_family == AF_INET)
//         {
//             // If the address is IPV4, then print it
//             struct sockaddr_in *dns_addr = (struct sockaddr_in *)&ctx->servers[i].dns_server;

//             LOG_INF("Resolver [%d]: %s", i,
//                     net_addr_ntop(AF_INET, &dns_addr->sin_addr, buf, sizeof(buf)));
//         }
//     }
// }

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Sockets
 *---------------------------------------------------------------------------------------------------*/

static void socket_client(void) {
    iface_t client_cfg =
        {
            .type = IFACE_TYPE_SOCKET,
            .link = IFACE_LINK_TYPE_CLIENT,
            .p_host = SERVER_IP,
            .port = SERVER_PORT,
        };

    while (true) {
        if (!iface_create(&client_cfg)) {
            LOG_ERR("Could not create iface");
            break;
        }

        LOG_INF("Client is connecting to server...");

        bool timeout = false;
        if (!iface_connect(&client_cfg, &timeout)) {
            LOG_ERR("Could not connect, timeout: %s", timeout ? "yes" : "no");
            break;
        }

        LOG_INF("Connected succesfully!");

        bool conn_closed = false;
        uint8_t count = 0;
        while (count < 3) {
            char message[] = "Hello from client";
            LOG_INF("Client sending: %s", message);

            uint16_t sent_bytes = 0;
            if (!iface_send(&client_cfg, message, sizeof(message), &sent_bytes, &conn_closed, &timeout)) {
                LOG_ERR("Could not send, timeout: %s, conn_closed: %s", timeout ? "yes" : "no", conn_closed ? "yes" : "no");
                break;
            }

            uint16_t recv_bytes = 0;
            static char buffer[1024] = {0};
            if (!iface_recv(&client_cfg, buffer, sizeof(buffer), &recv_bytes, &conn_closed, &timeout)) {
                LOG_ERR("Could not recv, timeout: %s, conn_closed: %s", timeout ? "yes" : "no", conn_closed ? "yes" : "no");
                break;
            }

            LOG_INF("Client received: %s", buffer);
            count++;
            k_msleep(1000);
        }

        if (!iface_close(&client_cfg)) {
            LOG_ERR("Could not close iface");
            break;
        }

        k_msleep(1000);
    }

    LOG_ERR("Fatal error occurred in %s", __func__);
    k_fatal_halt(0);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                 UART
 *---------------------------------------------------------------------------------------------------*/
static void uart_server(void) {
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

        LOG_INF("Client connected!");

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

static void uart_client(void) {
    iface_t client_cfg =
        {
            .type = IFACE_TYPE_UART,
            .link = IFACE_LINK_TYPE_CLIENT,
            .p_uart_dev = uart_dev,
        };

    while (true) {
        if (!iface_create(&client_cfg)) {
            LOG_ERR("Could not create iface");
            break;
        }

        LOG_INF("Client is connecting to server...");

        bool timeout = false;
        if (!iface_connect(&client_cfg, &timeout)) {
            LOG_ERR("Could not connect, timeout: %s", timeout ? "yes" : "no");
            break;
        }

        LOG_INF("Connected succesfully!");

        // Main loop (echo)
        bool conn_closed = false;
        uint8_t count = 0;
        while (count < 10) {
            char message[] = "Hello from client";
            LOG_INF("Client sending: %s", message);

            uint16_t sent_bytes = 0;
            if (!iface_send(&client_cfg, message, sizeof(message), &sent_bytes, &conn_closed, &timeout)) {
                LOG_ERR("Could not send, timeout: %s, conn_closed: %s", timeout ? "yes" : "no", conn_closed ? "yes" : "no");
                break;
            }

            LOG_INF("Sent %d bytes", sent_bytes);

            uint16_t recv_bytes = 0;
            static char buffer[1024] = {0};
            if (!iface_recv(&client_cfg, buffer, sizeof(buffer), &recv_bytes, &conn_closed, &timeout)) {
                LOG_ERR("Could not recv, timeout: %s, conn_closed: %s", timeout ? "yes" : "no", conn_closed ? "yes" : "no");
                break;
            }

            LOG_INF("Client received: %s", buffer);
            count++;

            k_msleep(1000);
        }

        if (!iface_close(&client_cfg)) {
            LOG_ERR("Could not close iface");
            break;
        }

        k_msleep(1000);
    }

    LOG_ERR("Fatal error occurred in %s", __func__);
    k_fatal_halt(0);
}