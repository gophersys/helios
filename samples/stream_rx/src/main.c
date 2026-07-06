// Cipher stream RECEIVER (downlink server).
//
// Runs the daemon and accepts an uplink. Inbound STREAM packets are reassembled
// by the daemon's stream thread, which logs throughput + checksum on completion.
// A poller also prints the last completed stream's stats.

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <string.h>
#include <zephyr/net/socket.h>

#include <daemon/api.h>
#include <corekinect/cipher/stream.h>

#ifndef COLLECTOR_HOST
#define COLLECTOR_HOST "10.168.0.225"   /* k3s-w-4 node, LAN-reachable from the board */
#endif
#ifndef COLLECTOR_PORT
#define COLLECTOR_PORT 9999
#endif

// Reliable result channel: the 115200 UART drops lines under load, so stream
// stats go out over UDP to a collector on the node (which the benchmark graphs).
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

static void metrics_emit(const char *json, int len)
{
    if (metrics_sock >= 0) {
        (void)zsock_sendto(metrics_sock, json, len, 0,
                           (struct sockaddr *)&metrics_dest, sizeof(metrics_dest));
    }
}

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

/*-----------------------------------------------------------------------------------------------------
 *                                                                          On-device metrics sampler
 *---------------------------------------------------------------------------------------------------*/
// Samples system + per-thread CPU%, per-thread stack high-water, and the cipher
// daemon's packet-heap usage every ~250ms and ships each sample as one JSON line
// over UDP to the collector. Kept off the data path (its own low-priority thread)
// so it never perturbs the throughput it is measuring.

#define SAMPLE_INTERVAL_MS 250
#define MAX_TRACKED_THREADS 20

struct thread_cpu_prev
{
    const struct k_thread *tid;
    uint64_t cycles;
};
static struct thread_cpu_prev cpu_prev[MAX_TRACKED_THREADS];
static uint64_t sys_prev_active;
static uint64_t sys_prev_total;

static uint64_t prev_cycles_for(const struct k_thread *tid)
{
    for (int i = 0; i < MAX_TRACKED_THREADS; i++) {
        if (cpu_prev[i].tid == tid) {
            return cpu_prev[i].cycles;
        }
    }
    return 0;
}

static void store_cycles_for(const struct k_thread *tid, uint64_t cycles)
{
    int free_slot = -1;
    for (int i = 0; i < MAX_TRACKED_THREADS; i++) {
        if (cpu_prev[i].tid == tid) {
            cpu_prev[i].cycles = cycles;
            return;
        }
        if (free_slot < 0 && cpu_prev[i].tid == NULL) {
            free_slot = i;
        }
    }
    if (free_slot >= 0) {
        cpu_prev[free_slot].tid = tid;
        cpu_prev[free_slot].cycles = cycles;
    }
}

struct sampler_ctx
{
    char *buf;
    size_t cap;
    int len;
    uint64_t elapsed; /* system active+idle cycles this interval */
};

static void per_thread_cb(const struct k_thread *thread, void *user_data)
{
    struct sampler_ctx *ctx = user_data;

    k_thread_runtime_stats_t rt;
    if (k_thread_runtime_stats_get((struct k_thread *)thread, &rt) != 0) {
        return;
    }

    uint64_t delta = rt.execution_cycles - prev_cycles_for(thread);
    store_cycles_for(thread, rt.execution_cycles);
    uint32_t cpu_milli = ctx->elapsed ? (uint32_t)(delta * 100000 / ctx->elapsed) : 0;

    size_t unused = 0;
    (void)k_thread_stack_space_get(thread, &unused);

    const char *name = k_thread_name_get((struct k_thread *)thread);
    if (name == NULL || name[0] == '\0') {
        name = "?";
    }

    if (ctx->len < (int)ctx->cap - 96) {
        ctx->len += snprintk(ctx->buf + ctx->len, ctx->cap - ctx->len,
            "%s{\"name\":\"%s\",\"cpu_milli\":%u,\"stack_unused\":%u}",
            ctx->len && ctx->buf[ctx->len - 1] != '[' ? "," : "",
            name, cpu_milli, (unsigned)unused);
    }
}

static void metrics_sampler_thread(void *a, void *b, void *c)
{
    ARG_UNUSED(a); ARG_UNUSED(b); ARG_UNUSED(c);

    while (metrics_sock < 0) {
        k_sleep(K_MSEC(200)); /* wait for metrics_init() in main */
    }

    static char buf[1024];
    while (true) {
        k_sleep(K_MSEC(SAMPLE_INTERVAL_MS));

        k_thread_runtime_stats_t all;
        if (k_thread_runtime_stats_all_get(&all) != 0) {
            continue;
        }
        uint64_t active = all.execution_cycles;
        uint64_t total = all.total_cycles;
        uint64_t elapsed = total - sys_prev_total;
        uint64_t active_delta = active - sys_prev_active;
        sys_prev_active = active;
        sys_prev_total = total;
        uint32_t sys_cpu_milli = elapsed ? (uint32_t)(active_delta * 100000 / elapsed) : 0;

        cipher_heap_stats_t heap;
        cipher_daemon_get_heap_stats(&daemon_inst, &heap);

        int len = snprintk(buf, sizeof(buf),
            "{\"kind\":\"sys\",\"ts_ms\":%lld,\"cpu_milli\":%u,"
            "\"heap_net_used\":%u,\"heap_net_max\":%u,"
            "\"heap_local_used\":%u,\"heap_local_max\":%u,\"threads\":[",
            k_uptime_get(), sys_cpu_milli,
            (unsigned)heap.net_allocated, (unsigned)heap.net_max,
            (unsigned)heap.local_allocated, (unsigned)heap.local_max);

        struct sampler_ctx ctx = { .buf = buf, .cap = sizeof(buf), .len = len, .elapsed = elapsed };
        k_thread_foreach_unlocked(per_thread_cb, &ctx);
        len = ctx.len;
        len += snprintk(buf + len, sizeof(buf) - len, "]}");

        metrics_emit(buf, len);
    }
}

K_THREAD_DEFINE(metrics_sampler, 2048, metrics_sampler_thread, NULL, NULL, NULL,
                K_LOWEST_APPLICATION_THREAD_PRIO, 0, 0);

int main(void)
{
    LOG_INF("cipher STREAM receiver booting (device 0x%04x, port %d)", daemon_cfg.device_id, CIPHER_PORT);
    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_register_local_services(&daemon_inst, sink_services, ARRAY_SIZE(sink_services));
    cipher_daemon_start(&daemon_inst);
    k_sleep(K_SECONDS(6));  // let DHCP + the network come up before opening the metrics socket
    metrics_init();

    uint32_t stream_count = 0;
    uint32_t last_seen = 0xFFFFFFFF;
    while (true)
    {
        k_sleep(K_MSEC(500));
        cipher_stream_rx_stats_t stats;
        if (cipher_stream_get_last_rx(&daemon_inst, &stats) && stats.completion_id != last_seen)
        {
            last_seen = stats.completion_id;
            uint32_t kib_s = stats.duration_ms > 0
                ? (uint32_t)((int64_t)stats.received_len * 1000 / stats.duration_ms / 1024) : 0;
            LOG_INF("== STREAM DONE: %u bytes / %u chunks in %lld ms = %u KiB/s | checksum %s ==",
                    stats.received_len, stats.num_chunks, stats.duration_ms, kib_s,
                    stats.checksum_ok ? "VERIFIED" : "MISMATCH");

            char json[256];
            int n = snprintk(json, sizeof(json),
                "{\"kind\":\"stream\",\"n\":%u,\"bytes\":%u,\"chunks\":%u,"
                "\"duration_ms\":%lld,\"kib_s\":%u,\"checksum_ok\":%s}",
                ++stream_count, stats.received_len, stats.num_chunks,
                stats.duration_ms, kib_s, stats.checksum_ok ? "true" : "false");
            metrics_emit(json, n);
        }
    }
    return 0;
}
