// Cipher daemon: uplink (client) node.
//
// Boots the cipher daemon with a single CLIENT socket interface that
// connects to the downlink node. The peer is found by mDNS name
// (cipher-server.local) — DHCP + DNS, no static addresses anywhere.

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include <daemon/api.h>

LOG_MODULE_REGISTER(eth_uplink);

#define CIPHER_SERVER_HOST CONFIG_CIPHER_SAMPLE_SERVER_HOST
#define CIPHER_PORT 5555

static cipher_daemon_t daemon_inst;

static cipher_daemon_config_t daemon_cfg =
{
    .device_id = 0x0002,
    .num_client_ifaces = 1,
    .num_server_ifaces = 0,
    .client_ifaces =
    {
        {
            .type = IFACE_TYPE_SOCKET,
            .link = IFACE_LINK_TYPE_CLIENT,
            .p_host = (char *)CIPHER_SERVER_HOST,
            .port = CIPHER_PORT,
        },
    },
};

int main(void)
{
    LOG_INF("cipher uplink node booting (device id 0x%04x -> %s:%d)",
            daemon_cfg.device_id, CIPHER_SERVER_HOST, CIPHER_PORT);

    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_daemon_start(&daemon_inst);

    while (true)
    {
        k_sleep(K_SECONDS(30));
        LOG_INF("uplink alive");
    }

    return 0;
}
