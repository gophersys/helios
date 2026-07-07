// WiFi connectivity backend for the Zephyr connection manager.
//
// Upstream removed the built-in CONNECTIVITY_WIFI_MGMT implementation (the
// choice now defaults to "application-provided"), so we provide it here in the
// iface library. This keeps WiFi connectivity fully owned by conn_mgr and fully
// out of the application: on conn_mgr_if_connect() we associate the iface using
// credentials stored in NVS (wifi_credentials), disable power-save for low
// latency, and mark the binding persistent so conn_mgr drives (re)connection.
// The app just waits for L4 — identical to Ethernet.

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/wifi_credentials.h>
#include <zephyr/net/conn_mgr_connectivity.h>
#include <zephyr/net/conn_mgr_connectivity_impl.h>
#include <zephyr/net/conn_mgr/connectivity_wifi_mgmt.h>
#include <string.h>

LOG_MODULE_REGISTER(iface_wifi_conn, CONFIG_CK_IFACE_WIFI_CONNECTIVITY_LOG_LEVEL);

// Pick the first stored SSID. Nodes here use a single network; extend to a
// per-binding SSID if multi-network selection is needed later.
struct ssid_pick {
    char ssid[WIFI_SSID_MAX_LEN];
    size_t len;
    bool found;
};
static void pick_first_ssid(void *arg, const char *ssid, size_t ssid_len)
{
    struct ssid_pick *p = arg;
    if (!p->found && ssid_len <= sizeof(p->ssid)) {
        memcpy(p->ssid, ssid, ssid_len);
        p->len = ssid_len;
        p->found = true;
    }
}

// Disable power-save once associated (LAN RTT ~203 ms -> ~7 ms).
static struct net_mgmt_event_callback ps_cb;
static void ps_on_connect(struct net_mgmt_event_callback *cb, uint64_t evt, struct net_if *iface)
{
    ARG_UNUSED(cb);
    if (evt == NET_EVENT_WIFI_CONNECT_RESULT) {
        struct wifi_ps_params ps = { .enabled = WIFI_PS_DISABLED };
        (void)net_mgmt(NET_REQUEST_WIFI_PS, iface, &ps, sizeof(ps));
    }
}

static bool wifi_conn_has_config(struct conn_mgr_conn_binding *const binding)
{
    ARG_UNUSED(binding);
    struct ssid_pick p = {0};
    wifi_credentials_for_each_ssid(pick_first_ssid, &p);
    return p.found;
}

static int wifi_conn_connect(struct conn_mgr_conn_binding *const binding)
{
    struct ssid_pick p = {0};
    wifi_credentials_for_each_ssid(pick_first_ssid, &p);
    if (!p.found) {
        LOG_WRN("no WiFi credentials in storage — provision with 'wifi cred add'");
        return -ENOENT;
    }

    struct wifi_credentials_personal creds;
    memset(&creds, 0, sizeof(creds));
    int rc = wifi_credentials_get_by_ssid_personal_struct(p.ssid, p.len, &creds);
    if (rc) {
        LOG_ERR("failed to read stored credentials: %d", rc);
        return rc;
    }

    static struct wifi_connect_req_params params;
    memset(&params, 0, sizeof(params));
    params.ssid = (const uint8_t *)creds.header.ssid;
    params.ssid_length = creds.header.ssid_len;
    params.psk = (const uint8_t *)creds.password;
    params.psk_length = creds.password_len;
    params.security = creds.header.type;
    params.channel = WIFI_CHANNEL_ANY;
    params.band = WIFI_FREQ_BAND_2_4_GHZ;
    params.mfp = WIFI_MFP_OPTIONAL;

    LOG_INF("associating to '%.*s'", (int)params.ssid_length, params.ssid);
    return net_mgmt(NET_REQUEST_WIFI_CONNECT, binding->iface, &params, sizeof(params));
}

static int wifi_conn_disconnect(struct conn_mgr_conn_binding *const binding)
{
    return net_mgmt(NET_REQUEST_WIFI_DISCONNECT, binding->iface, NULL, 0);
}

static void wifi_conn_init(struct conn_mgr_conn_binding *const binding)
{
    net_mgmt_init_event_callback(&ps_cb, ps_on_connect, NET_EVENT_WIFI_CONNECT_RESULT);
    net_mgmt_add_event_callback(&ps_cb);
    // Persistent: conn_mgr keeps (re)connecting across drops without app help.
    conn_mgr_binding_set_flag(binding, CONN_MGR_IF_PERSISTENT, true);
}

static struct conn_mgr_conn_api wifi_conn_api = {
    .has_connection_config = wifi_conn_has_config,
    .connect = wifi_conn_connect,
    .disconnect = wifi_conn_disconnect,
    .init = wifi_conn_init,
};
CONN_MGR_CONN_DEFINE(CONNECTIVITY_WIFI_MGMT, &wifi_conn_api);
