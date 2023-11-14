// Zephyr includes
#include <dns_sec.h>


#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <tinycrypt/constants.h>
#include <tinycrypt/ecc.h>
#include <tinycrypt/ecc_dsa.h>
#include <tinycrypt/sha256.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/dns_resolve.h>
#include <zephyr/net/net_config.h>
#include <zephyr/net/net_context.h>
#include <zephyr/net/net_core.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/socket.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>

// #include "dnssec/dnssec.h"

LOG_MODULE_REGISTER(app);

#define GPIO_LABEL green_led
#define GPIO_NODE DT_NODELABEL(GPIO_LABEL)

const struct device *gpio_dev;
static const struct gpio_dt_spec gpiod = GPIO_DT_SPEC_GET(GPIO_NODE, gpios);

// static void print_addresses(void);
// void dump_addrinfo(const struct addrinfo *ai);
static void print_addresses(void);
static void dump_addrinfo(const struct addrinfo *ai);

bool hash(uint8_t *hash, const uint8_t *data, size_t data_size, dnssec_hash_algo_t hash_algo)
{
    __ASSERT(data, "NULL data pointer passed");
    __ASSERT(hash, "NULL hash pointer passed");

    if (hash_algo != DNSSEC_HASH_SHA256)
    {
        // Handle unsupported hash algorithm or add support for other types
        LOG_WRN("Unsupported hash algorithm");
        return false;
    }

    struct tc_sha256_state_struct sha256_ctx;

    if (tc_sha256_init(&sha256_ctx) == TC_CRYPTO_FAIL)
    {
        LOG_WRN("Could not initialize tinycrypt library");
        return false;
    }

    if (tc_sha256_update(&sha256_ctx, data, data_size) == TC_CRYPTO_FAIL)
    {
        LOG_WRN("Could not update tinycrypt context");
        return false;
    }

    if (tc_sha256_final(hash, &sha256_ctx) == TC_CRYPTO_FAIL)
    {
        LOG_WRN("Could not hash data");
        return false;
    }

    return true;
}

bool verify(const uint8_t *public_key, const uint8_t *message_hash, size_t hash_size,
            const uint8_t *signature, dnssec_curve_type_t curve_type)
{
    if (curve_type != DNSSEC_CURVE_SECP256R1)
    {
        // Handle unsupported curve type or add support for other types
        return false;
    }

    uECC_Curve curve = uECC_secp256r1();
    return uECC_verify(public_key, message_hash, hash_size, signature, curve) == TC_CRYPTO_SUCCESS;
}

static dnssec_crypto_functions_t custom_crypto_funcs =
{
    .hash_function = hash,
    .verify_function = verify,
};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Public
 *---------------------------------------------------------------------------------------------------*/
int main(void) {

    int ret;
     if (!gpio_is_ready_dt(&gpiod))
    {
        LOG_ERR("GPIO port isn't ready");
        return -3;
    }
    ret = gpio_pin_configure_dt(&gpiod, GPIO_OUTPUT_ACTIVE);
	if (ret < 0) {
		return 0;
	}

    while(1)
    {
        gpio_pin_toggle(gpiod.port, gpiod.pin);
        k_msleep(1000);
    }
    

    return 0;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Helpers
 *---------------------------------------------------------------------------------------------------*/

// static void print_addresses(void) {
//     struct net_if *iface;
//     iface = net_if_get_default();
//     char buf[NET_IPV4_ADDR_LEN];

//     for (size_t i = 0; i < NET_IF_MAX_IPV4_ADDR; i++) {

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

//     for (int i = 0; ctx->servers[i].dns_server.sa_family != AF_UNSPEC; ++i) {
//         if (ctx->servers[i].dns_server.sa_family == AF_INET) {
//             // If the address is IPV4, then print it
//             struct sockaddr_in *dns_addr = (struct sockaddr_in *)&ctx->servers[i].dns_server;

//             LOG_INF("Resolver [%d]: %s", i,
//                     net_addr_ntop(AF_INET, &dns_addr->sin_addr, buf, sizeof(buf)));
//         }
//     }
// }

// void dump_addrinfo(const struct addrinfo *ai) {
//     LOG_INF(
//         "addrinfo @%p: ai_family=%d, ai_socktype=%d, ai_protocol=%d, "
//         "sa_family=%d, sin_port=%x\n",
//         ai, ai->ai_family, ai->ai_socktype, ai->ai_protocol,
//         ai->ai_addr->sa_family,
//         ((struct sockaddr_in *)ai->ai_addr)->sin_port);

//     char buf[NET_IPV4_ADDR_LEN];

//     LOG_INF("IP Addr: %s",
//             net_addr_ntop(AF_INET,
//                           &ai->ai_addr,
//                           buf, sizeof(buf)));
// }
