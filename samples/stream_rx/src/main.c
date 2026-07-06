// Cipher stream RECEIVER (downlink server).
//
// Runs the daemon and accepts an uplink. Inbound STREAM packets are reassembled
// by the daemon's stream thread, which logs throughput + checksum on completion.
// A poller also prints the last completed stream's stats.

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <daemon/api.h>
#include <corekinect/cipher/stream.h>

LOG_MODULE_REGISTER(stream_rx);

#define CIPHER_PORT 5555

static cipher_daemon_t daemon_inst;
static cipher_daemon_config_t daemon_cfg =
{
    .device_id = 0x0001,
    .num_server_ifaces = 1,
    .server_ifaces = {{ .type = IFACE_TYPE_SOCKET, .link = IFACE_LINK_TYPE_SERVER, .port = CIPHER_PORT }},
};

// Advertised so the daemon broadcasts our presence on connect; that SD packet
// is how the sender learns the device->interface route it streams over.
static cipher_service_entry_t sink_services[] =
{
    { .service = { .id = 200, .name = "stream-sink", .allowed_hops = 1, .ops = NULL, .num_ops = 0 } },
};

int main(void)
{
    LOG_INF("cipher STREAM receiver booting (device 0x%04x, port %d)", daemon_cfg.device_id, CIPHER_PORT);
    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_register_local_services(&daemon_inst, sink_services, ARRAY_SIZE(sink_services));
    cipher_daemon_start(&daemon_inst);

    uint32_t last_seen = 0xFFFFFFFF;
    while (true)
    {
        k_sleep(K_MSEC(500));
        cipher_stream_rx_stats_t stats;
        if (cipher_stream_get_last_rx(&daemon_inst, &stats) && stats.received_len != last_seen)
        {
            last_seen = stats.received_len;
            uint32_t kib_s = stats.duration_ms > 0
                ? (uint32_t)((int64_t)stats.received_len * 1000 / stats.duration_ms / 1024) : 0;
            LOG_INF("== STREAM DONE: %u bytes / %u chunks in %lld ms = %u KiB/s | checksum %s ==",
                    stats.received_len, stats.num_chunks, stats.duration_ms, kib_s,
                    stats.checksum_ok ? "VERIFIED" : "MISMATCH");
        }
    }
    return 0;
}
