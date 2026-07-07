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

#include <daemon/api.h>
#include <corekinect/cipher/stream.h>

LOG_MODULE_REGISTER(ota_node, LOG_LEVEL_INF);

#define CIPHER_PORT   5555
#define OTA_STREAM_ID 0x00F0   /* firmware stream (matrix streamctl uses id 1) */

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

static void ota_sink(uint16_t stream_id, uint8_t phase, const uint8_t *data, uint16_t len, void *ctx)
{
    ARG_UNUSED(ctx);
    if (stream_id != OTA_STREAM_ID) {
        return;   /* not a firmware stream — leave it to the plain reassembler */
    }

    switch (phase) {
    case CIPHER_STREAM_PHASE_START:
        if (flash_img_init(&ota_ctx) == 0) {
            ota_active = true;
            LOG_INF("OTA: receiving firmware into secondary slot");
        } else {
            LOG_ERR("OTA: flash_img_init failed");
        }
        break;

    case CIPHER_STREAM_PHASE_DATA:
        if (ota_active) {
            int rc = flash_img_buffered_write(&ota_ctx, data, len, false);
            if (rc) { LOG_ERR("OTA: write failed rc=%d", rc); ota_active = false; }
        }
        break;

    case CIPHER_STREAM_PHASE_END:
        if (ota_active) {
            bool ok = (data && len >= 1 && data[0]);
            int rc = flash_img_buffered_write(&ota_ctx, NULL, 0, true);   /* flush */
            size_t written = flash_img_bytes_written(&ota_ctx);
            ota_active = false;
            LOG_INF("OTA: wrote %u bytes to slot1, stream checksum %s, flush rc=%d",
                    (unsigned)written, ok ? "OK" : "BAD", rc);
            if (ok && rc == 0) {
                rc = boot_request_upgrade(BOOT_UPGRADE_TEST);
                LOG_INF("OTA: boot_request_upgrade rc=%d -> rebooting to swap", rc);
                k_work_schedule(&reboot_work, K_MSEC(500));
            } else {
                LOG_ERR("OTA: image rejected (checksum/flush) — slot1 discarded");
            }
        }
        break;
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

    while (true) {
        k_sleep(K_SECONDS(10));
        LOG_INF("OTA NODE %s alive (confirmed=%d)", APP_VERSION_STR, boot_is_img_confirmed());
    }
    return 0;
}
