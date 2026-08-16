// Multi-instance proof: TWO complete cipher daemons in ONE process.
//
// Before the stream state moved into cipher_daemon_t, the stream module's
// file-scope statics were shared, so two daemons could not coexist. This test
// stands up a server daemon and a client daemon on loopback, streams a blob
// from the client to the server, and asserts:
//   * the SERVER's per-instance stream_state holds the completed stream, and
//   * the CLIENT's per-instance stream_state is independent (never received),
// proving each instance owns its own memory.

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <daemon/api.h>
#include <corekinect/cipher/stream.h>

LOG_MODULE_REGISTER(multi_instance);

#define PORT 6001
#define BLOB_LEN 40000
#define SRV_DEVICE 0x0001
#define CLI_DEVICE 0x0002

// Two fully independent daemon instances, each with its own threads, heaps,
// queues and (the point of this test) stream_state.
static cipher_daemon_t srv;
static cipher_daemon_t cli;

static cipher_daemon_config_t srv_cfg = {
    .device_id = SRV_DEVICE,
    .num_server_ifaces = 1,
    .server_ifaces = {{ .type = IFACE_TYPE_SOCKET, .link = IFACE_LINK_TYPE_SERVER, .port = PORT }},
};

static cipher_daemon_config_t cli_cfg = {
    .device_id = CLI_DEVICE,
    .num_client_ifaces = 1,
    .client_ifaces = {{ .type = IFACE_TYPE_SOCKET, .link = IFACE_LINK_TYPE_CLIENT,
                        .p_host = "127.0.0.1", .port = PORT }},
};

// The server advertises a sink so the client learns the route to stream over.
static cipher_service_entry_t srv_services[] = {
    { .service = { .id = 200, .name = "sink", .allowed_hops = 1, .ops = NULL, .num_ops = 0 } },
};

static uint8_t blob[BLOB_LEN];

int main(void)
{
    for (int i = 0; i < BLOB_LEN; i++) {
        blob[i] = (uint8_t)(i * 31 + 7);
    }

    LOG_INF("=== multi-instance test: two daemons in one image ===");

    cipher_daemon_init(&srv_cfg, &srv);
    cipher_register_local_services(&srv, srv_services, ARRAY_SIZE(srv_services));
    cipher_daemon_start(&srv);

    cipher_daemon_init(&cli_cfg, &cli);
    cipher_daemon_start(&cli);

    // Let the client connect + learn the route (SD broadcast) from the server.
    k_sleep(K_SECONDS(2));

    LOG_INF("client streaming %d bytes to server 0x%04x", BLOB_LEN, SRV_DEVICE);
    int32_t sent = cipher_stream_send(&cli, SRV_DEVICE, 1, blob, BLOB_LEN, 0);
    LOG_INF("cipher_stream_send returned %d", sent);

    // Give the server time to reassemble.
    k_sleep(K_SECONDS(2));

    cipher_stream_rx_stats_t srv_stats;
    cipher_stream_rx_stats_t cli_stats;
    bool srv_has = cipher_stream_get_last_rx(&srv, &srv_stats);
    bool cli_has = cipher_stream_get_last_rx(&cli, &cli_stats);

    bool pass = true;

    // The SERVER instance must hold the completed, checksum-verified stream.
    if (!srv_has || srv_stats.received_len != BLOB_LEN || !srv_stats.checksum_ok) {
        LOG_ERR("FAIL: server stream_state wrong (has=%d len=%u ok=%d)",
                srv_has, srv_has ? srv_stats.received_len : 0,
                srv_has ? srv_stats.checksum_ok : 0);
        pass = false;
    } else {
        LOG_INF("server instance: %u bytes, checksum VERIFIED", srv_stats.received_len);
    }

    // The CLIENT instance's stream_state must be INDEPENDENT — it never received
    // a stream, so its last_rx must be empty. Before the refactor both daemons
    // shared one global, so the client would have reported the server's stats.
    if (cli_has) {
        LOG_ERR("FAIL: client stream_state is NOT independent (reported len=%u) "
                "-- shared global state!", cli_stats.received_len);
        pass = false;
    } else {
        LOG_INF("client instance: stream_state independent (empty), as expected");
    }

    LOG_INF("=== MULTI-INSTANCE TEST: %s ===", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
