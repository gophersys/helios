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
static struct k_sem connect_result;   /* given on each WiFi CONNECT_RESULT */
static volatile int connect_status;   /* 0 = associated, else failure reason */

static cipher_daemon_t daemon_inst;
static cipher_daemon_config_t daemon_cfg = {
    .device_id = 0x000A,   /* ESP32-A */
    .num_server_ifaces = 1,
    .server_ifaces = {{ .type = IFACE_TYPE_SOCKET, .link = IFACE_LINK_TYPE_SERVER, .port = CIPHER_PORT }},
};
// ---- Matrix RPC surface: math (latency probe) + streamctl (trigger sends) ----
struct math_req_t { uint32_t a; uint32_t b; } __packed;
struct math_resp_t { uint32_t sum; } __packed;
struct sctl_req_t { uint16_t target; uint32_t size; uint16_t chunk; } __packed;
struct sctl_resp_t { int32_t sent; } __packed;

static uint8_t bench_buf[CONFIG_BENCH_PAYLOAD_SIZE];

static cipher_rpc_err_t math_add_h(void *req, void *resp)
{
    const struct math_req_t *q = req;
    struct math_resp_t *r = resp;
    r->sum = q->a + q->b;
    return CIPHER_RPC_ERR_OK;
}

// Stream min(size, bench_buf) bytes to `target`. Lets the Go orchestrator fire
// any node->any node stream, so every matrix cell can be driven in BOTH
// directions (incl. micro<->micro where Go is neither endpoint).
static cipher_rpc_err_t streamctl_h(void *req, void *resp)
{
    const struct sctl_req_t *q = req;
    struct sctl_resp_t *r = resp;
    uint32_t n = q->size > sizeof(bench_buf) ? sizeof(bench_buf) : q->size;
    uint16_t chunk = q->chunk ? q->chunk : 1000;
    r->sent = cipher_stream_send(&daemon_inst, q->target, 1, bench_buf, n, chunk);
    return CIPHER_RPC_ERR_OK;
}

static cipher_ops_entry_t math_ops[] = {
    { .id = 1, .type = CIPHER_OPS_TYPE_RPC, .name = "add",
      .op = { .rpc = { .request_size = sizeof(struct math_req_t),
                       .response_size = sizeof(struct math_resp_t),
                       .handler = math_add_h, .supports_parallelism = false } } },
};
static cipher_ops_entry_t sctl_ops[] = {
    { .id = 1, .type = CIPHER_OPS_TYPE_RPC, .name = "send",
      .op = { .rpc = { .request_size = sizeof(struct sctl_req_t),
                       .response_size = sizeof(struct sctl_resp_t),
                       .handler = streamctl_h, .supports_parallelism = false } } },
};
static cipher_service_entry_t node_services[] = {
    { .service = { .id = 200, .name = "sink", .allowed_hops = 1, .ops = NULL, .num_ops = 0 } },
    { .service = { .id = 100, .name = "math", .allowed_hops = 1, .ops = math_ops, .num_ops = 1 } },
    { .service = { .id = 101, .name = "sctl", .allowed_hops = 1, .ops = sctl_ops, .num_ops = 1 } },
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
        connect_status = st->status;
        if (st->status == 0) {
            struct wifi_ps_params ps = { .enabled = WIFI_PS_DISABLED };
            net_mgmt(NET_REQUEST_WIFI_PS, iface, &ps, sizeof(ps));
            net_dhcpv4_start(iface);
        }
        k_sem_give(&connect_result);
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

    k_sem_init(&connect_result, 0, 1);
    struct net_if *iface = net_if_get_first_wifi();
    k_sleep(K_SECONDS(1));
    static struct wifi_connect_req_params p;
    p.ssid = (const uint8_t *)CONFIG_WIFI_SSID; p.ssid_length = strlen(CONFIG_WIFI_SSID);
    p.psk = (const uint8_t *)CONFIG_WIFI_PSK;   p.psk_length = strlen(CONFIG_WIFI_PSK);
    p.security = WIFI_SECURITY_TYPE_PSK; p.channel = WIFI_CHANNEL_ANY;
    p.band = WIFI_FREQ_BAND_2_4_GHZ; p.mfp = WIFI_MFP_OPTIONAL;

    // Retry until associated + DHCP, with EXPONENTIAL BACKOFF. A single patient
    // attempt reliably associates; hammering the AP with rapid retries makes a
    // consumer router rate-limit the MAC (every attempt then returns
    // CONN_TIMEOUT). Backing off gives both the driver and the AP time to
    // recover, so across a continuous reflash loop a fresh flash always comes up
    // on WiFi without intervention.
    int backoff_s = 5;
    for (int attempt = 1; !have_ip; attempt++) {
        LOG_INF("WiFi connect attempt %d to '%s'...", attempt, CONFIG_WIFI_SSID);
        k_sem_reset(&connect_result);
        connect_status = -1;
        net_mgmt(NET_REQUEST_WIFI_CONNECT, iface, &p, sizeof(p));
        if (k_sem_take(&connect_result, K_SECONDS(25)) == 0 && connect_status == 0) {
            for (int i = 0; i < 75 && !have_ip; i++) {
                k_sleep(K_MSEC(200));   /* associated — wait for the DHCP lease */
            }
        }
        if (have_ip) {
            break;
        }
        LOG_WRN("WiFi attempt %d failed (status=%d) — backoff %ds", attempt, connect_status, backoff_s);
        net_mgmt(NET_REQUEST_WIFI_DISCONNECT, iface, NULL, 0);
        k_sleep(K_SECONDS(backoff_s));
        if (backoff_s < 30) {
            backoff_s += 5;    /* 5,10,15,20,25,30,30... */
        }
    }

    LOG_INF("network up — starting cipher daemon (device 0x%04x, port %d)", daemon_cfg.device_id, CIPHER_PORT);
    for (size_t i = 0; i < sizeof(bench_buf); i++) {
        bench_buf[i] = (uint8_t)(i * 31 + 7);   /* deterministic payload for streamctl sends */
    }
    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_register_local_services(&daemon_inst, node_services, ARRAY_SIZE(node_services));
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
