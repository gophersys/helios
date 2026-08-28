// Cipher matrix node: a full-duplex cipher endpoint used at every hardware slot
// of the interop matrix. It runs a stream SINK (receive + checksum), a math RPC
// (latency probe), and a streamctl RPC ("stream N bytes to device D") so a Go
// orchestrator can drive any node->any node stream in BOTH directions.
//
// There is NO transport code here. Connectivity (WiFi, Ethernet, ...) is owned
// by the platform's connection manager; cipher_daemon_start() waits for the
// link to be ready internally. This exact main runs unchanged on an ESP32 over
// WiFi and a Nucleo over Ethernet — the only difference is the board overlay.

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>
#include <string.h>

#include <daemon/api.h>
#include <corekinect/cipher/stream.h>

LOG_MODULE_REGISTER(matrix_node, LOG_LEVEL_INF);

#define CIPHER_PORT 5555
#define COLLECTOR_HOST "10.168.0.225"
#define COLLECTOR_PORT 9999

static cipher_daemon_t daemon_inst;
static cipher_daemon_config_t daemon_cfg = {
    .device_id = CONFIG_CIPHER_DEVICE_ID,
    .num_server_ifaces = 1,
    .server_ifaces = {{ .type = IFACE_TYPE_SOCKET, .link = IFACE_LINK_TYPE_SERVER, .port = CIPHER_PORT }},
};

/*---- Matrix RPC surface: math (latency) + streamctl (trigger sends) ----*/
struct math_req_t { uint32_t a; uint32_t b; } __packed;
struct math_resp_t { uint32_t sum; } __packed;
struct sctl_req_t { uint16_t target; uint32_t size; uint16_t chunk; } __packed;
struct sctl_resp_t { int32_t sent; } __packed;

// streamctl runs the (potentially minutes-long, 100 MB+) send on a dedicated
// sender thread so the RPC returns immediately; the orchestrator watches the
// receiver's completion metric. The generated pattern send needs no buffer, so
// a node can source an arbitrarily large stream from a few bytes of RAM.
struct send_req_t { uint16_t target; uint32_t size; uint16_t chunk; };
K_MSGQ_DEFINE(send_q, sizeof(struct send_req_t), 4, 4);

static void sender_thread(void *a, void *b, void *c)
{
    ARG_UNUSED(a); ARG_UNUSED(b); ARG_UNUSED(c);
    struct send_req_t rq;
    while (1) {
        k_msgq_get(&send_q, &rq, K_FOREVER);
        LOG_INF("streamctl: streaming %u bytes -> 0x%04x", rq.size, rq.target);
        int64_t t0 = k_uptime_get();
        int32_t sent = cipher_stream_send_pattern(&daemon_inst, rq.target, 1, rq.size, rq.chunk);
        int64_t dt = k_uptime_get() - t0;
        uint32_t kib = dt > 0 ? (uint32_t)((int64_t)sent * 1000 / dt / 1024) : 0;
        LOG_INF("streamctl: sent %d bytes -> 0x%04x in %lld ms = %u KiB/s", sent, rq.target, dt, kib);
    }
}
K_THREAD_DEFINE(sender_tid, 3072, sender_thread, NULL, NULL, NULL, 6, 0, 0);

static cipher_rpc_err_t math_add_h(void *req, void *resp)
{
    const struct math_req_t *q = req;
    struct math_resp_t *r = resp;
    r->sum = q->a + q->b;
    return CIPHER_RPC_ERR_OK;
}

static cipher_rpc_err_t streamctl_h(void *req, void *resp)
{
    const struct sctl_req_t *q = req;
    struct sctl_resp_t *r = resp;
    struct send_req_t rq = { .target = q->target, .size = q->size, .chunk = q->chunk ? q->chunk : 1000 };
    r->sent = (k_msgq_put(&send_q, &rq, K_NO_WAIT) == 0) ? (int32_t)q->size : -1;
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

/*---- Reliable results channel (UDP to the node collector) ----*/
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

int main(void)
{
    LOG_INF("matrix_node booting (device 0x%04x)", CONFIG_CIPHER_DEVICE_ID);

    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_register_local_services(&daemon_inst, node_services, ARRAY_SIZE(node_services));
    cipher_daemon_start(&daemon_inst);   // waits for the platform's link internally
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
                "{\"kind\":\"stream\",\"node\":\"0x%04x\",\"n\":%u,\"bytes\":%u,\"chunks\":%u,"
                "\"duration_ms\":%lld,\"kib_s\":%u,\"checksum_ok\":%s}",
                CONFIG_CIPHER_DEVICE_ID, st.completion_id, st.received_len, st.num_chunks,
                st.duration_ms, kib, st.checksum_ok ? "true" : "false");
            metrics_emit(j, n);
        }
    }
    return 0;
}
