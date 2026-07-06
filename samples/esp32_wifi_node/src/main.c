// Cipher node over WiFi (ESP32). Associates to the AP, waits for DHCP, then runs
// a cipher daemon as a stream sink so a peer can stream to it over WiFi. First
// cross-transport (WiFi) cell of the interop matrix.
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/net_event.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/dhcpv4.h>
#include <zephyr/net/socket.h>
#include <string.h>

#include <daemon/api.h>
#include <corekinect/cipher/stream.h>

LOG_MODULE_REGISTER(cipher_esp32, LOG_LEVEL_INF);

#define CIPHER_PORT 5555
#define COLLECTOR_HOST "10.168.0.225"
#define COLLECTOR_PORT 9999

static struct net_mgmt_event_callback wifi_cb, ipv4_cb;
static volatile bool have_ip;

static cipher_daemon_t daemon_inst;
static cipher_daemon_config_t daemon_cfg = {
    .device_id = 0x000A,   /* ESP32-A */
    .num_server_ifaces = 1,
    .server_ifaces = {{ .type = IFACE_TYPE_SOCKET, .link = IFACE_LINK_TYPE_SERVER, .port = CIPHER_PORT }},
};
static cipher_service_entry_t sink_services[] = {
    { .service = { .id = 200, .name = "sink", .allowed_hops = 1, .ops = NULL, .num_ops = 0 } },
};

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

static void wifi_evt(struct net_mgmt_event_callback *cb, uint64_t evt, struct net_if *iface)
{
    if (evt == NET_EVENT_WIFI_CONNECT_RESULT) {
        const struct wifi_status *st = cb->info;
        if (st->status) { LOG_ERR("WiFi failed %d", st->status); return; }
        struct wifi_ps_params ps = { .enabled = WIFI_PS_DISABLED };
        net_mgmt(NET_REQUEST_WIFI_PS, iface, &ps, sizeof(ps));
        net_dhcpv4_start(iface);
    }
}
static void ipv4_evt(struct net_mgmt_event_callback *cb, uint64_t evt, struct net_if *iface)
{
    if (evt != NET_EVENT_IPV4_ADDR_ADD) return;
    for (int i = 0; i < NET_IF_MAX_IPV4_ADDR; i++) {
        struct net_if_addr *a = &iface->config.ip.ipv4->unicast[i].ipv4;
        if (a->addr_type != NET_ADDR_DHCP) continue;
        char buf[NET_IPV4_ADDR_LEN];
        net_addr_ntop(AF_INET, &a->address.in_addr, buf, sizeof(buf));
        LOG_INF("WiFi DHCP IP: %s", buf);
        have_ip = true;
    }
}

int main(void)
{
    net_mgmt_init_event_callback(&wifi_cb, wifi_evt, NET_EVENT_WIFI_CONNECT_RESULT);
    net_mgmt_add_event_callback(&wifi_cb);
    net_mgmt_init_event_callback(&ipv4_cb, ipv4_evt, NET_EVENT_IPV4_ADDR_ADD);
    net_mgmt_add_event_callback(&ipv4_cb);

    struct net_if *iface = net_if_get_first_wifi();
    k_sleep(K_SECONDS(1));
    static struct wifi_connect_req_params p;
    p.ssid = (const uint8_t *)CONFIG_WIFI_SSID; p.ssid_length = strlen(CONFIG_WIFI_SSID);
    p.psk = (const uint8_t *)CONFIG_WIFI_PSK;   p.psk_length = strlen(CONFIG_WIFI_PSK);
    p.security = WIFI_SECURITY_TYPE_PSK; p.channel = WIFI_CHANNEL_ANY;
    p.band = WIFI_FREQ_BAND_2_4_GHZ; p.mfp = WIFI_MFP_OPTIONAL;
    LOG_INF("connecting to '%s'...", CONFIG_WIFI_SSID);
    net_mgmt(NET_REQUEST_WIFI_CONNECT, iface, &p, sizeof(p));

    while (!have_ip) k_sleep(K_MSEC(200));

    LOG_INF("network up — starting cipher daemon (device 0x%04x, port %d)", daemon_cfg.device_id, CIPHER_PORT);
    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_register_local_services(&daemon_inst, sink_services, ARRAY_SIZE(sink_services));
    cipher_daemon_start(&daemon_inst);
    metrics_init();

    uint32_t last = 0xFFFFFFFF;
    while (true) {
        k_sleep(K_MSEC(500));
        cipher_stream_rx_stats_t st;
        if (cipher_stream_get_last_rx(&daemon_inst, &st) && st.completion_id != last) {
            last = st.completion_id;
            uint32_t kib = st.duration_ms > 0 ? (uint32_t)((int64_t)st.received_len * 1000 / st.duration_ms / 1024) : 0;
            LOG_INF("STREAM %u bytes/%u chunks in %lld ms = %u KiB/s checksum %s",
                st.received_len, st.num_chunks, st.duration_ms, kib, st.checksum_ok ? "OK" : "BAD");
            char j[224];
            int n = snprintk(j, sizeof(j),
                "{\"kind\":\"stream\",\"node\":\"esp32a\",\"n\":%u,\"bytes\":%u,\"chunks\":%u,"
                "\"duration_ms\":%lld,\"kib_s\":%u,\"checksum_ok\":%s}",
                st.completion_id, st.received_len, st.num_chunks, st.duration_ms, kib,
                st.checksum_ok ? "true" : "false");
            metrics_emit(j, n);
        }
    }
    return 0;
}
