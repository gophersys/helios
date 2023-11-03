// Zephyr includes

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/dns_resolve.h>
#include <zephyr/net/net_config.h>
#include <zephyr/net/net_context.h>
#include <zephyr/net/net_core.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/socket.h>

#include "dns_sec/include/dns_sec.h"
// #include "dnssec/dnssec.h"

LOG_MODULE_REGISTER(app);

static void print_addresses(void);
static void dump_addrinfo(const struct addrinfo *ai);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Public
 *---------------------------------------------------------------------------------------------------*/

int main(void) {
    LOG_RAW("\n\n%s\n", "********** DNS Sec App **********");

    print_addresses();

    static struct addrinfo hints;
    struct addrinfo *res;
    // int st = getaddrinfo("mateosegura.com", NULL, &hints, &res);
    // int st = getsecaddrinfo("mateosegura.com", NULL, &hints, &res);

    int i = 0;
    while (true) {

        int st = getsecaddrinfo("sigma.blackohm.cloud", NULL, &hints, &res);
        if (st != 0) {
            LOG_ERR("Unable to resolve address, quitting\n");
        } else {
            // dump_addrinfo(res);

            // freeaddrinfo(res);
            freesecaddrinfo(res);
        }

        // st = getsecaddrinfo("mateosegura.com", NULL, &hints, &res);
        // if (st != 0) {
        //     LOG_ERR("Unable to resolve address, quitting");
        // } else {
        //     // dump_addrinfo(res);

        //     // freeaddrinfo(res);
        //     freesecaddrinfo(res);
        // }
        k_msleep(16000);
        LOG_INF("Count %d", i++);
    }

    return 0;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Helpers
 *---------------------------------------------------------------------------------------------------*/

static void print_addresses(void) {
    struct net_if *iface;
    iface = net_if_get_default();
    char buf[NET_IPV4_ADDR_LEN];

    for (size_t i = 0; i < NET_IF_MAX_IPV4_ADDR; i++) {

        LOG_INF("IP Addr: %s",
                net_addr_ntop(AF_INET,
                              &iface->config.ip.ipv4->unicast[i].address.in_addr,
                              buf, sizeof(buf)));

        LOG_INF("Subnet: %s",
                net_addr_ntop(AF_INET,
                              &iface->config.ip.ipv4->netmask,
                              buf, sizeof(buf)));
        LOG_INF("Router: %s",
                net_addr_ntop(AF_INET,
                              &iface->config.ip.ipv4->gw,
                              buf, sizeof(buf)));
    }

    const struct dns_resolve_context *ctx = dns_resolve_get_default();

    for (int i = 0; ctx->servers[i].dns_server.sa_family != AF_UNSPEC; ++i) {
        if (ctx->servers[i].dns_server.sa_family == AF_INET) {
            // If the address is IPV4, then print it
            struct sockaddr_in *dns_addr = (struct sockaddr_in *)&ctx->servers[i].dns_server;

            LOG_INF("Resolver [%d]: %s", i,
                    net_addr_ntop(AF_INET, &dns_addr->sin_addr, buf, sizeof(buf)));
        }
    }
}

void dump_addrinfo(const struct addrinfo *ai) {
    LOG_INF(
        "addrinfo @%p: ai_family=%d, ai_socktype=%d, ai_protocol=%d, "
        "sa_family=%d, sin_port=%x\n",
        ai, ai->ai_family, ai->ai_socktype, ai->ai_protocol,
        ai->ai_addr->sa_family,
        ((struct sockaddr_in *)ai->ai_addr)->sin_port);

    char buf[NET_IPV4_ADDR_LEN];

    LOG_INF("IP Addr: %s",
            net_addr_ntop(AF_INET,
                          &ai->ai_addr,
                          buf, sizeof(buf)));
}
