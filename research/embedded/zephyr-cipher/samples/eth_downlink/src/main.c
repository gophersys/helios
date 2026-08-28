// Cipher daemon: downlink (server) node.
//
// Boots the cipher daemon with a single SERVER socket interface on the
// board's ethernet. The board leases an address over DHCP and advertises
// itself as cipher-server.local over mDNS, so the uplink node needs zero
// static network configuration to find it.

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include <daemon/api.h>

LOG_MODULE_REGISTER(eth_downlink);

#define CIPHER_PORT 5555

static cipher_daemon_t daemon_inst;

static cipher_daemon_config_t daemon_cfg =
{
    .device_id = 0x0001,
    .num_client_ifaces = 0,
    .num_server_ifaces = 1,
    .server_ifaces =
    {
        {
            .type = IFACE_TYPE_SOCKET,
            .link = IFACE_LINK_TYPE_SERVER,
            .port = CIPHER_PORT,
        },
    },
};

// A demo service: gives service discovery something real to broadcast, so
// cipher packets actually cross the wire (and the analyzer can decode them).
static cipher_service_entry_t demo_services[] =
{
    {
        .service =
        {
            .id = 42,
            .name = "demo-echo",
            .allowed_hops = 1,
            .ops = NULL,
            .num_ops = 0,
        },
    },
};

int main(void)
{
    LOG_INF("cipher downlink node booting (device id 0x%04x, port %d)",
            daemon_cfg.device_id, CIPHER_PORT);

    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_register_local_services(&daemon_inst, demo_services, ARRAY_SIZE(demo_services));
    cipher_daemon_start(&daemon_inst);

    while (true)
    {
        k_sleep(K_SECONDS(30));
        LOG_INF("downlink alive");
    }

    return 0;
}
