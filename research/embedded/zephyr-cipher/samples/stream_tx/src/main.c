// Cipher stream SENDER (uplink client).
//
// Connects to the receiver, waits for discovery, then streams a large blob and
// repeats — varying nothing here (the benchmark harness sweeps sizes). Prints
// its own send-side throughput; the receiver verifies bytes + checksum.

#include <stdlib.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <daemon/api.h>
#include <corekinect/cipher/stream.h>

LOG_MODULE_REGISTER(stream_tx);

#define CIPHER_SERVER_HOST CONFIG_CIPHER_SAMPLE_SERVER_HOST
#define CIPHER_PORT        5555
#define REMOTE_DEVICE_ID   0x0001

#ifndef STREAM_BYTES
#define STREAM_BYTES (256 * 1024)
#endif
#ifndef STREAM_CHUNK
#define STREAM_CHUNK 1000
#endif

static cipher_daemon_t daemon_inst;
static cipher_daemon_config_t daemon_cfg =
{
    .device_id = 0x0002,
    .num_client_ifaces = 1,
    .client_ifaces = {{ .type = IFACE_TYPE_SOCKET, .link = IFACE_LINK_TYPE_CLIENT,
                        .p_host = (char *)CIPHER_SERVER_HOST, .port = CIPHER_PORT }},
};

static uint8_t blob[STREAM_BYTES];

int main(void)
{
    LOG_INF("cipher STREAM sender booting (device 0x%04x -> %s:%d)",
            daemon_cfg.device_id, CIPHER_SERVER_HOST, CIPHER_PORT);

    // Fill the blob with a deterministic pattern (so the checksum is meaningful).
    for (uint32_t i = 0; i < STREAM_BYTES; i++) {
        blob[i] = (uint8_t)(i * 31 + 7);
    }

    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_daemon_start(&daemon_inst);
    k_sleep(K_SECONDS(5));  // let discovery learn the route

    for (uint16_t stream_id = 1;; stream_id++)
    {
        LOG_INF("streaming %d bytes (chunk %d)...", STREAM_BYTES, STREAM_CHUNK);
        int64_t t0 = k_uptime_get();
        int32_t sent = cipher_stream_send(&daemon_inst, REMOTE_DEVICE_ID, stream_id,
                                          blob, STREAM_BYTES, STREAM_CHUNK);
        int64_t dt = k_uptime_get() - t0;

        if (sent < 0) {
            LOG_ERR("stream send failed (%d)", sent);
        } else {
            uint32_t kib_s = dt > 0 ? (uint32_t)((int64_t)sent * 1000 / dt / 1024) : 0;
            LOG_INF("sent %d bytes in %lld ms = %u KiB/s (send side)", sent, dt, kib_s);
        }
        k_sleep(K_SECONDS(3));
    }
    return 0;
}
