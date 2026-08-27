// One-time WiFi credential provisioner. Writes the build-supplied SSID/PSK into
// NVS (wifi_credentials), then halts. The normal firmware carries NO credentials
// and reads them from NVS via the connection manager. Run once per board; NVS
// survives subsequent application reflashes.
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/wifi.h>
#include <zephyr/net/wifi_credentials.h>
#include <string.h>

LOG_MODULE_REGISTER(wifi_provision, LOG_LEVEL_INF);

int main(void)
{
    if (strlen(CONFIG_WIFI_SSID) == 0) {
        LOG_ERR("no SSID configured — build with the creds overlay");
        return 0;
    }
    int rc = wifi_credentials_set_personal(
        CONFIG_WIFI_SSID, strlen(CONFIG_WIFI_SSID),
        WIFI_SECURITY_TYPE_PSK, NULL, 0,
        CONFIG_WIFI_PSK, strlen(CONFIG_WIFI_PSK),
        0, 0, 0);
    if (rc) {
        LOG_ERR("provisioning FAILED: %d", rc);
    } else {
        LOG_INF("provisioned NVS credentials for SSID '%s' (%d-char psk)",
                CONFIG_WIFI_SSID, (int)strlen(CONFIG_WIFI_PSK));
    }
    LOG_INF("=== PROVISION DONE — flash matrix_node next ===");
    return 0;
}
