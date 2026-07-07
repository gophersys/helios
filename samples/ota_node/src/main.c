// Cipher OTA node: receives a firmware image as a cipher STREAM and applies it
// as an MCUboot A/B update. The daemon is transport-agnostic (WiFi on ESP32,
// Ethernet on Nucleo — connectivity is owned by the connection manager); the
// only OTA-specific piece is a stream RX sink that writes the incoming bytes
// straight into the secondary flash slot via Zephyr's flash_img DFU API, then
// requests an MCUboot swap. After the swap the new image self-confirms on boot.
//
// Flow: server streams firmware (stream id = OTA_STREAM_ID) -> START:flash_img_init
// -> DATA:flash_img_buffered_write(slot1) -> END(checksum OK):flush +
// boot_request_upgrade(TEST) + reboot -> MCUboot swaps slot1<->slot0 -> new image.

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/dfu/flash_img.h>
#include <zephyr/dfu/mcuboot.h>
#include <zephyr/net/socket.h>
#include <string.h>

#include <daemon/api.h>
#include <corekinect/cipher/stream.h>

LOG_MODULE_REGISTER(ota_node, LOG_LEVEL_INF);

#define CIPHER_PORT   5555
#define OTA_STREAM_ID 0x00F0   /* firmware stream (matrix streamctl uses id 1) */
#define COLLECTOR_HOST "10.168.0.225"
#define COLLECTOR_PORT 9999

/* Reliable results channel: serial drops lines under stream load, so OTA
 * progress is reported over UDP to the node collector. */
static int metrics_sock = -1;
static struct sockaddr_in metrics_dest;
static void metrics_init(void)
{
    metrics_sock = zsock_socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    memset(&metrics_dest, 0, sizeof(metrics_dest));
    metrics_dest.sin_family = AF_INET;
    metrics_dest.sin_port = htons(COLLECTOR_PORT);
    zsock_inet_pton(AF_INET, COLLECTOR_HOST, &metrics_dest.sin_addr);
}
static void metrics_emit(const char *j, int n)
{
    if (metrics_sock >= 0)
        (void)zsock_sendto(metrics_sock, j, n, 0, (struct sockaddr *)&metrics_dest, sizeof(metrics_dest));
}

#ifndef APP_VERSION_STR
#define APP_VERSION_STR "v1"
#endif

static cipher_daemon_t daemon_inst;
static cipher_daemon_config_t daemon_cfg = {
    .device_id = CONFIG_CIPHER_DEVICE_ID,
    .num_server_ifaces = 1,
    .server_ifaces = {{ .type = IFACE_TYPE_SOCKET, .link = IFACE_LINK_TYPE_SERVER, .port = CIPHER_PORT }},
};

/* A minimal service so the daemon accepts client connections + their streams. */
static cipher_service_entry_t node_services[] = {
    { .service = { .id = 200, .name = "sink", .allowed_hops = 1, .ops = NULL, .num_ops = 0 } },
};

/*---- OTA stream sink: firmware bytes -> secondary slot -> swap ----*/
static struct flash_img_context ota_ctx;
static bool ota_active;
static struct k_work_delayable reboot_work;

static void do_reboot(struct k_work *w) { ARG_UNUSED(w); sys_reboot(SYS_REBOOT_COLD); }

static uint32_t ota_chunks;
static int ota_last_write_rc;

static void ota_sink(uint16_t stream_id, uint8_t phase, const uint8_t *data, uint16_t len, void *ctx)
{
    ARG_UNUSED(ctx);
    char j[192];
    int n;
    if (stream_id != OTA_STREAM_ID) {
        return;   /* not a firmware stream — leave it to the plain reassembler */
    }

    switch (phase) {
    case CIPHER_STREAM_PHASE_START: {
        int rc = flash_img_init(&ota_ctx);
        ota_active = (rc == 0);
        ota_chunks = 0;
        ota_last_write_rc = 0;
        n = snprintk(j, sizeof(j), "{\"kind\":\"ota\",\"node\":\"0x%04x\",\"phase\":\"start\",\"init_rc\":%d}",
                     CONFIG_CIPHER_DEVICE_ID, rc);
        metrics_emit(j, n);
        break;
    }

    case CIPHER_STREAM_PHASE_DATA:
        if (ota_active) {
            int rc = flash_img_buffered_write(&ota_ctx, data, len, false);
            ota_chunks++;
            if (rc) { ota_last_write_rc = rc; ota_active = false; }
        }
        break;

    case CIPHER_STREAM_PHASE_END: {
        bool ok = (data && len >= 1 && data[0]);
        int flush_rc = ota_active ? flash_img_buffered_write(&ota_ctx, NULL, 0, true) : -1;
        size_t written = ota_active ? flash_img_bytes_written(&ota_ctx) : 0;
        int upgrade_rc = -999;
        if (ota_active && ok && flush_rc == 0) {
            /* PERMANENT: swap sticks on the next boot (no confirm handshake
             * needed). Switch to BOOT_UPGRADE_TEST + a post-self-test
             * boot_write_img_confirmed() for revert-on-failure in production. */
            upgrade_rc = boot_request_upgrade(BOOT_UPGRADE_PERMANENT);
        }
        n = snprintk(j, sizeof(j),
            "{\"kind\":\"ota\",\"node\":\"0x%04x\",\"phase\":\"end\",\"active\":%d,\"chunks\":%u,"
            "\"written\":%u,\"csum_ok\":%s,\"write_rc\":%d,\"flush_rc\":%d,\"upgrade_rc\":%d}",
            CONFIG_CIPHER_DEVICE_ID, ota_active, ota_chunks, (unsigned)written,
            ok ? "true" : "false", ota_last_write_rc, flush_rc, upgrade_rc);
        metrics_emit(j, n);
        ota_active = false;
        if (upgrade_rc == 0) {
            k_work_schedule(&reboot_work, K_MSEC(800));   /* let the UDP report flush */
        }
        break;
    }
    }
}

int main(void)
{
    /* A freshly-swapped image boots in TEST mode; confirm it so MCUboot keeps
     * it (a real product would confirm only after a self-test passes). */
    if (!boot_is_img_confirmed()) {
        int rc = boot_write_img_confirmed();
        LOG_INF("confirmed running image rc=%d", rc);
    }
    LOG_INF("==== OTA NODE %s (device 0x%04x) ====", APP_VERSION_STR, CONFIG_CIPHER_DEVICE_ID);

    k_work_init_delayable(&reboot_work, do_reboot);

    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_register_local_services(&daemon_inst, node_services, ARRAY_SIZE(node_services));
    cipher_stream_set_rx_sink(&daemon_inst, ota_sink, NULL);
    cipher_daemon_start(&daemon_inst);   /* waits for the link internally */
    metrics_init();

    while (true) {
        k_sleep(K_SECONDS(10));
        LOG_INF("OTA NODE %s alive (confirmed=%d)", APP_VERSION_STR, boot_is_img_confirmed());
    }
    return 0;
}
