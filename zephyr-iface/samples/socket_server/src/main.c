// Standard includes
#include <errno.h>
#include <stdio.h>
#include <string.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/dns_resolve.h>
#include <zephyr/net/net_config.h>
#include <zephyr/net/net_context.h>
#include <zephyr/net/net_core.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/socket.h>

// Corekinect includes
#include <corekinect/iface/iface.h>  // <- This is how you'd include the library in your app

LOG_MODULE_REGISTER(socket_server);

// Configuration
#define SERVER_PORT 4444

// Useful networking information
static void print_net_addr(void);

int main(void)
{
    print_net_addr();

    // Server config
    iface_t server_cfg =
    {
        .type = IFACE_TYPE_SOCKET,
        .link = IFACE_LINK_TYPE_SERVER,
        .port = SERVER_PORT
    };

    while (true)
    {
        if (!iface_create(&server_cfg))
        {
            LOG_ERR("Could not create iface");
            break;
        }

        LOG_INF("Server is running and waiting for connection...");

        bool timeout = false;
        if (!iface_accept(&server_cfg, &timeout))
        {
            LOG_ERR("Error accepting connection, timeout: %s", timeout ? "yes" : "no");
            break;
        }

        bool conn_closed = false;
        while (true)
        {
            uint16_t recv_bytes = 0;
            static char buffer[1024] = {0};
            if (!iface_recv(&server_cfg, buffer, sizeof(buffer), &recv_bytes, &conn_closed, &timeout))
            {
                LOG_ERR("Could not recv, timeout: %s, conn_closed: %s", timeout ? "yes" : "no", conn_closed ? "yes" : "no");
                break;
            }

            LOG_INF("Server received: %s", buffer);
            uint16_t sent_bytes = 0;
            if (!iface_send(&server_cfg, buffer, recv_bytes, &sent_bytes, &conn_closed, &timeout))
            {
                LOG_ERR("Could not send, timeout: %s, conn_closed: %s", timeout ? "yes" : "no", conn_closed ? "yes" : "no");
                break;
            }
        }

        if (!iface_close(&server_cfg))
        {
            LOG_ERR("Could not close iface");
            break;
        }
    }

    LOG_ERR("Fatal error occurred in %s", __func__);
    k_fatal_halt(0);

}

static void print_net_addr(void)
{
    struct net_if *iface;
    iface = net_if_get_default();
    char buf[NET_IPV4_ADDR_LEN];

    for (size_t i = 0; i < NET_IF_MAX_IPV4_ADDR; i++)
    {
        // Zephyr 4.x: address moved to unicast[i].ipv4, netmask is per-address
        if (!iface->config.ip.ipv4->unicast[i].ipv4.is_used)
        {
            continue;
        }

        LOG_INF("IP Addr: %s",
                net_addr_ntop(AF_INET,
                              &iface->config.ip.ipv4->unicast[i].ipv4.address.in_addr,
                              buf, sizeof(buf)));

        LOG_INF("Subnet: %s",
                net_addr_ntop(AF_INET,
                              &iface->config.ip.ipv4->unicast[i].netmask,
                              buf, sizeof(buf)));
        LOG_INF("Router: %s",
                net_addr_ntop(AF_INET,
                              &iface->config.ip.ipv4->gw,
                              buf, sizeof(buf)));
    }

    const struct dns_resolve_context *ctx = dns_resolve_get_default();

    for (int i = 0; ctx->servers[i].dns_server.sa_family != AF_UNSPEC; ++i)
    {
        if (ctx->servers[i].dns_server.sa_family == AF_INET)
        {
            // If the address is IPV4, then print it
            struct sockaddr_in *dns_addr = (struct sockaddr_in *)&ctx->servers[i].dns_server;

            LOG_INF("Resolver [%d]: %s", i,
                    net_addr_ntop(AF_INET, &dns_addr->sin_addr, buf, sizeof(buf)));
        }
    }
}