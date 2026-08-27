// WiFi connectivity backend for the Zephyr connection manager.
//
// Upstream removed the built-in CONNECTIVITY_WIFI_MGMT implementation (the
// choice now defaults to "application-provided"), so the iface library provides
// a production-grade one here. Design ported from the proven netctl/wifi_sta
// station manager (Helios runtime -> icle firmware), adapted to conn_mgr:
//
//   - FULLY ASYNC: no blocking waits; every WiFi op runs on a dedicated
//     workqueue because net_mgmt calls can block for seconds on ESP32 (running
//     them on the system workqueue would stall every other k_work user).
//   - STALE-STATE CLEANUP: before each attempt the driver state is queried and
//     a half-open association is torn down first (a stuck "associating" state
//     otherwise wedges the connect forever).
//   - CONNECT TIMEOUT: an attempt that produces neither CONNECT_RESULT nor an
//     IPv4 address within the window is force-disconnected and retried.
//   - EXPONENTIAL BACKOFF RETRY: association failure, DHCP stall, or a drop
//     while the binding is persistent all schedule a reconnect (1s -> 60s).
//   - FULL EVENT COVERAGE: connect result (with status), disconnect (with
//     reason), and DHCP address acquisition are all handled + logged.
//
// PER-BINDING STATE: conn_mgr can bind this connectivity implementation to more
// than one WiFi station iface. Each binding gets its OWN context (own work
// items, own net_mgmt callback nodes, own wanted/have_ip/backoff state) from a
// static pool sized by CONFIG_CK_IFACE_WIFI_MAX_BINDINGS. A single global
// context would (a) let one iface's disconnect clobber another's wanted flag and
// (b) register the SAME net_mgmt_event_callback slist node twice, forming a
// cycle that spins the net_mgmt event thread forever. The context is reached
// from every callback/work handler via CONTAINER_OF, so nothing here is a
// file-scope singleton.
//
// Credentials live in NVS (wifi_credentials); the app never touches any of
// this — it just waits for NET_EVENT_L4_CONNECTED, identically to Ethernet.

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/net_event.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/wifi_credentials.h>
#include <zephyr/net/conn_mgr_connectivity.h>
#include <zephyr/net/conn_mgr_connectivity_impl.h>
#include <zephyr/net/conn_mgr/connectivity_wifi_mgmt.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/util.h>
#include <errno.h>
#include <string.h>

LOG_MODULE_REGISTER(iface_wifi_conn, CONFIG_CK_IFACE_WIFI_CONNECTIVITY_LOG_LEVEL);

#define CONNECT_TIMEOUT_SEC  CONFIG_CK_IFACE_WIFI_CONNECT_TIMEOUT_SEC
#define BACKOFF_BASE_MS      1000
#define BACKOFF_MAX_MS       60000

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                State
 *---------------------------------------------------------------------------------------------------*/

/* One instance per conn_mgr binding (see file header). Handlers recover it with
 * CONTAINER_OF from the embedded work item or callback node. */
struct wifi_conn_ctx {
    struct net_if *iface;              /* bound WiFi STA iface */
    atomic_t wanted;                   /* conn_mgr asked for connectivity */
    atomic_t in_progress;              /* a connect attempt is in flight */
    atomic_t have_ip;                  /* IPv4 acquired (link fully up) */
    atomic_t settled;                  /* link is up+healthy; watchdog must not tear it down */
    atomic_t backoff_ms;               /* RMW'd from 3 threads -> must be atomic */
    uint32_t attempt;                  /* wq-confined: only the connect handler writes it */

    struct k_work_delayable connect_work;  /* runs the actual net_mgmt connect */
    struct k_work ps_off_work;         /* disable power save (off the event thread) */
    struct k_work_delayable retry_work;    /* backoff re-entry */
    struct k_work_delayable timeout_work;  /* attempt watchdog */

    struct net_mgmt_event_callback wifi_cb;
    struct net_mgmt_event_callback ipv4_cb;
};

/* Per-binding contexts. A slot is claimed in wifi_conn_init() and stored in
 * binding->ctx; every handler reaches its context from there or via CONTAINER_OF. */
static struct wifi_conn_ctx ctx_pool[CONFIG_CK_IFACE_WIFI_MAX_BINDINGS];
static atomic_t ctx_pool_next;

/* Dedicated (shared) workqueue: net_mgmt(WIFI_*) can block seconds on ESP32.
 * Work items are per-context, so bindings never touch each other's state. */
static K_THREAD_STACK_DEFINE(wifi_wq_stack, CONFIG_CK_IFACE_WIFI_WQ_STACK_SIZE);
static struct k_work_q wifi_wq;
static bool wifi_wq_started;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Credentials
 *---------------------------------------------------------------------------------------------------*/

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

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       Retry plumbing
 *---------------------------------------------------------------------------------------------------*/

static void schedule_retry(struct wifi_conn_ctx *ctx, const char *why)
{
    if (!atomic_get(&ctx->wanted)) {
        return;
    }
    atomic_clear(&ctx->in_progress);
    /* The attempt is over — disarm the watchdog so it can't fire mid-backoff. */
    k_work_cancel_delayable(&ctx->timeout_work);

    uint32_t backoff = (uint32_t)atomic_get(&ctx->backoff_ms);
    LOG_WRN("wifi: %s — retrying in %u ms (attempt %u)", why, backoff, ctx->attempt + 1);
    k_work_schedule_for_queue(&wifi_wq, &ctx->retry_work, K_MSEC(backoff));
    atomic_set(&ctx->backoff_ms, MIN(backoff * 2, BACKOFF_MAX_MS));
}

static void retry_work_handler(struct k_work *work)
{
    struct wifi_conn_ctx *ctx =
        CONTAINER_OF(k_work_delayable_from_work(work), struct wifi_conn_ctx, retry_work);

    if (atomic_get(&ctx->wanted) && !atomic_get(&ctx->have_ip) &&
        !atomic_get(&ctx->in_progress)) {
        k_work_schedule_for_queue(&wifi_wq, &ctx->connect_work, K_NO_WAIT);
    }
}

/* Disable power save from the workqueue: a net_mgmt request issued inside a
 * net_mgmt event callback fails silently, so it must run on its own thread.
 * PS costs ~200 ms RTT on the ESP32 (7 ms with it off). */
static void ps_off_work_handler(struct k_work *work)
{
    struct wifi_conn_ctx *ctx = CONTAINER_OF(work, struct wifi_conn_ctx, ps_off_work);
    struct wifi_ps_params ps = { .enabled = WIFI_PS_DISABLED };
    int rc = net_mgmt(NET_REQUEST_WIFI_PS, ctx->iface, &ps, sizeof(ps));
    LOG_INF("wifi: power save disabled (rc=%d)", rc);
}

/* Attempt watchdog: neither CONNECT_RESULT-failure nor an IP arrived in time.
 * Tear the half-open state down and go through the retry path. */
static void timeout_work_handler(struct k_work *work)
{
    struct wifi_conn_ctx *ctx =
        CONTAINER_OF(k_work_delayable_from_work(work), struct wifi_conn_ctx, timeout_work);

    if (!atomic_get(&ctx->in_progress)) {
        return;
    }
    /* Re-check settled/have_ip immediately before issuing WIFI_DISCONNECT: DHCP
     * runs on the net_mgmt event thread and may have completed AFTER this
     * watchdog fired but before it got to run (k_work_cancel_delayable cannot
     * stop an already-dequeued handler). Without this guard the watchdog
     * force-drops a link that just came up and conn_mgr's L4_CONNECTED bounces
     * (finding #5). */
    if (atomic_get(&ctx->settled) || atomic_get(&ctx->have_ip)) {
        return;
    }
    LOG_WRN("wifi: connect attempt %u timed out after %us — cleaning up", ctx->attempt,
            CONNECT_TIMEOUT_SEC);
    (void)net_mgmt(NET_REQUEST_WIFI_DISCONNECT, ctx->iface, NULL, 0);
    schedule_retry(ctx, "connect timeout");
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Connect attempt
 *---------------------------------------------------------------------------------------------------*/

/* Query the driver and tear down any half-open state — a previous incomplete
 * attempt leaves the ESP32 driver "associating"/"associated" and a fresh
 * WIFI_CONNECT then fails or wedges. Fully async: when a teardown was issued the
 * caller reschedules itself instead of sleeping on the workqueue.
 * (Ported from netctl wifi_ensure_clean_state.) */
static bool ensure_clean_state(struct wifi_conn_ctx *ctx)
{
    struct wifi_iface_status status = {0};

    if (net_mgmt(NET_REQUEST_WIFI_IFACE_STATUS, ctx->iface, &status, sizeof(status)) < 0) {
        return false; /* can't query — proceed and let the attempt sort it out */
    }
    if (status.state != WIFI_STATE_INACTIVE && status.state != WIFI_STATE_DISCONNECTED &&
        status.state != WIFI_STATE_INTERFACE_DISABLED) {
        LOG_INF("wifi: clearing stale driver state (%d) before connect", status.state);
        (void)net_mgmt(NET_REQUEST_WIFI_DISCONNECT, ctx->iface, NULL, 0);
        return true; /* teardown issued — let it settle asynchronously */
    }
    return false;
}

static void connect_work_handler(struct k_work *work)
{
    struct wifi_conn_ctx *ctx =
        CONTAINER_OF(k_work_delayable_from_work(work), struct wifi_conn_ctx, connect_work);

    if (!atomic_get(&ctx->wanted) || atomic_get(&ctx->have_ip)) {
        return;
    }

    /* A fresh attempt (in_progress 0 -> 1) clears "settled" so the watchdog is
     * allowed to tear this attempt down. ensure_clean_state() re-entries keep
     * in_progress == 1 and do NOT reset it. */
    if (atomic_cas(&ctx->in_progress, 0, 1)) {
        atomic_clear(&ctx->settled);
    }

    /* Count AND watchdog-arm on EVERY entry, including an ensure_clean_state
     * re-entry. k_work_schedule_for_queue() is a no-op while the watchdog is
     * already pending, so the deadline stays anchored to the first entry: a
     * driver wedged in ASSOCIATING can no longer spin the 300 ms re-entry loop
     * forever with no timeout and no backoff — the watchdog fires, force-tears
     * it down, and schedule_retry() backs it off (finding #3). */
    ctx->attempt++;
    k_work_schedule_for_queue(&wifi_wq, &ctx->timeout_work, K_SECONDS(CONNECT_TIMEOUT_SEC));

    if (ensure_clean_state(ctx)) {
        /* Re-enter after the teardown settles — no blocking on the workqueue. */
        k_work_schedule_for_queue(&wifi_wq, &ctx->connect_work, K_MSEC(300));
        return;
    }

    struct ssid_pick p = {0};
    wifi_credentials_for_each_ssid(pick_first_ssid, &p);
    if (!p.found) {
        LOG_WRN("wifi: no credentials in storage — provision first");
        schedule_retry(ctx, "no stored credentials");
        return;
    }

    struct wifi_credentials_personal creds;
    memset(&creds, 0, sizeof(creds));
    if (wifi_credentials_get_by_ssid_personal_struct(p.ssid, p.len, &creds) != 0) {
        schedule_retry(ctx, "credential read failed");
        return;
    }

    static struct wifi_connect_req_params params;
    memset(&params, 0, sizeof(params));
    params.ssid = (const uint8_t *)creds.header.ssid;
    params.ssid_length = creds.header.ssid_len;
    params.psk = (const uint8_t *)creds.password;
    params.psk_length = creds.password_len;
    params.security = creds.header.type;
    params.channel = WIFI_CHANNEL_ANY;
    params.band = WIFI_FREQ_BAND_UNKNOWN;
    params.mfp = WIFI_MFP_OPTIONAL;

    LOG_INF("wifi: attempt %u: connecting to '%.*s'", ctx->attempt, (int)params.ssid_length,
            params.ssid);

    int rc = net_mgmt(NET_REQUEST_WIFI_CONNECT, ctx->iface, &params, sizeof(params));

    /* NET_REQUEST_WIFI_CONNECT blocks for seconds on ESP32. A disconnect() that
     * arrived while we were blocked has already cleared "wanted" and cancelled
     * this work — but cancellation can't unwind a running handler, so the
     * association is now proceeding behind conn_mgr's back. Re-check and undo it,
     * else L4_CONNECTED fires while conn_mgr believes the iface is down
     * (finding #2). */
    if (!atomic_get(&ctx->wanted)) {
        LOG_INF("wifi: connect cancelled mid-request — tearing down");
        (void)net_mgmt(NET_REQUEST_WIFI_DISCONNECT, ctx->iface, NULL, 0);
        k_work_cancel_delayable(&ctx->timeout_work);
        atomic_clear(&ctx->in_progress);
        return;
    }

    if (rc < 0 && rc != -EALREADY && rc != -EINPROGRESS) {
        schedule_retry(ctx, "connect request failed");
        return;
    }

    /* Watchdog stays armed (from the top of this handler) across association +
     * DHCP; on_ipv4_event cancels it once an address actually lands. */
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Events
 *---------------------------------------------------------------------------------------------------*/

static void on_wifi_event(struct net_mgmt_event_callback *cb, uint64_t evt, struct net_if *iface)
{
    struct wifi_conn_ctx *ctx = CONTAINER_OF(cb, struct wifi_conn_ctx, wifi_cb);
    if (iface != ctx->iface) {
        return;
    }
    const struct wifi_status *status = (const struct wifi_status *)cb->info;

    switch (evt) {
    case NET_EVENT_WIFI_CONNECT_RESULT:
        if (status->status != 0) {
            LOG_WRN("wifi: association failed (status %d)", status->status);
            k_work_cancel_delayable(&ctx->timeout_work);
            schedule_retry(ctx, "association failed");
        } else {
            LOG_INF("wifi: associated — waiting for DHCP");
            /* PS-off must run OFF this event thread (see ps_off_work_handler). */
            k_work_submit_to_queue(&wifi_wq, &ctx->ps_off_work);
            /* timeout_work stays armed until an IP actually lands */
        }
        break;

    case NET_EVENT_WIFI_DISCONNECT_RESULT:
    case NET_EVENT_WIFI_DISCONNECT_COMPLETE:
        LOG_INF("wifi: disconnected (reason %d)", status ? status->status : -1);
        atomic_clear(&ctx->have_ip);
        atomic_clear(&ctx->settled);
        if (atomic_get(&ctx->wanted) && !atomic_get(&ctx->in_progress)) {
            /* Link dropped after being up: persistent binding -> reconnect. */
            schedule_retry(ctx, "link dropped");
        }
        break;

    default:
        break;
    }
}

static void on_ipv4_event(struct net_mgmt_event_callback *cb, uint64_t evt, struct net_if *iface)
{
    struct wifi_conn_ctx *ctx = CONTAINER_OF(cb, struct wifi_conn_ctx, ipv4_cb);
    if (evt != NET_EVENT_IPV4_ADDR_ADD || iface != ctx->iface) {
        return;
    }
    char ip[NET_IPV4_ADDR_LEN] = "?";
    struct net_if_ipv4 *ipv4 = iface->config.ip.ipv4;
    if (ipv4 != NULL) {
        net_addr_ntop(AF_INET, &ipv4->unicast[0].ipv4.address.in_addr, ip, sizeof(ip));
    }
    LOG_INF("wifi: IPv4 acquired: %s (attempt %u)", ip, ctx->attempt);

    /* Mark "settled" BEFORE have_ip so a watchdog already dequeued on the wq
     * observes the healthy link and aborts its teardown (finding #5). */
    atomic_set(&ctx->settled, 1);
    atomic_set(&ctx->have_ip, 1);
    atomic_clear(&ctx->in_progress);
    atomic_set(&ctx->backoff_ms, BACKOFF_BASE_MS); /* healthy link resets the backoff */
    k_work_cancel_delayable(&ctx->timeout_work);
    k_work_cancel_delayable(&ctx->retry_work);
    /* conn_mgr raises NET_EVENT_L4_CONNECTED from this same address event. */
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     conn_mgr binding
 *---------------------------------------------------------------------------------------------------*/

static bool wifi_conn_has_config(struct conn_mgr_conn_binding *const binding)
{
    ARG_UNUSED(binding);
    struct ssid_pick p = {0};
    wifi_credentials_for_each_ssid(pick_first_ssid, &p);
    return p.found;
}

static int wifi_conn_connect(struct conn_mgr_conn_binding *const binding)
{
    struct wifi_conn_ctx *ctx = binding->ctx;
    if (ctx == NULL) {
        return -ENODEV;
    }
    ctx->iface = binding->iface;
    atomic_set(&ctx->wanted, 1);
    atomic_set(&ctx->backoff_ms, BACKOFF_BASE_MS);
    /* Async: the attempt runs on the WiFi workqueue; failures self-retry with
     * backoff, so conn_mgr never sees a fatal error for a transient problem. */
    k_work_schedule_for_queue(&wifi_wq, &ctx->connect_work, K_NO_WAIT);
    return 0;
}

static int wifi_conn_disconnect(struct conn_mgr_conn_binding *const binding)
{
    struct wifi_conn_ctx *ctx = binding->ctx;
    if (ctx == NULL) {
        return -ENODEV;
    }
    /* Clear ONLY this binding's wanted flag and cancel ONLY its work items. */
    atomic_clear(&ctx->wanted);
    /* Cancel the in-flight connect too: a queued/pending attempt would otherwise
     * still associate and raise L4_CONNECTED after conn_mgr asked us to stop
     * (finding #2 — the already-running-handler case is caught by the
     * post-request "wanted" re-check in connect_work_handler). */
    k_work_cancel_delayable(&ctx->connect_work);
    k_work_cancel_delayable(&ctx->retry_work);
    k_work_cancel_delayable(&ctx->timeout_work);
    atomic_clear(&ctx->in_progress);
    return net_mgmt(NET_REQUEST_WIFI_DISCONNECT, binding->iface, NULL, 0);
}

static void wifi_conn_init(struct conn_mgr_conn_binding *const binding)
{
    atomic_val_t idx = atomic_inc(&ctx_pool_next);
    if (idx >= CONFIG_CK_IFACE_WIFI_MAX_BINDINGS) {
        LOG_ERR("wifi: binding pool exhausted (max %d) — raise CK_IFACE_WIFI_MAX_BINDINGS",
                CONFIG_CK_IFACE_WIFI_MAX_BINDINGS);
        binding->ctx = NULL;
        return;
    }

    struct wifi_conn_ctx *ctx = &ctx_pool[idx];
    binding->ctx = ctx;
    ctx->iface = binding->iface;
    atomic_set(&ctx->backoff_ms, BACKOFF_BASE_MS);

    if (!wifi_wq_started) {
        k_work_queue_init(&wifi_wq);
        k_work_queue_start(&wifi_wq, wifi_wq_stack, K_THREAD_STACK_SIZEOF(wifi_wq_stack),
                           CONFIG_CK_IFACE_WIFI_WQ_PRIORITY, NULL);
        k_thread_name_set(&wifi_wq.thread, "wifi_conn_wq");
        wifi_wq_started = true;
    }

    k_work_init_delayable(&ctx->connect_work, connect_work_handler);
    k_work_init(&ctx->ps_off_work, ps_off_work_handler);
    k_work_init_delayable(&ctx->retry_work, retry_work_handler);
    k_work_init_delayable(&ctx->timeout_work, timeout_work_handler);

    /* Each binding owns its OWN callback nodes — registering a shared node twice
     * would splice an slist onto itself and hang the net_mgmt event thread. */
    net_mgmt_init_event_callback(&ctx->wifi_cb, on_wifi_event,
                                 NET_EVENT_WIFI_CONNECT_RESULT |
                                 NET_EVENT_WIFI_DISCONNECT_RESULT |
                                 NET_EVENT_WIFI_DISCONNECT_COMPLETE);
    net_mgmt_add_event_callback(&ctx->wifi_cb);

    net_mgmt_init_event_callback(&ctx->ipv4_cb, on_ipv4_event, NET_EVENT_IPV4_ADDR_ADD);
    net_mgmt_add_event_callback(&ctx->ipv4_cb);

    /* Persistent: this backend keeps reconnecting across drops without app help. */
    conn_mgr_binding_set_flag(binding, CONN_MGR_IF_PERSISTENT, true);
}

static struct conn_mgr_conn_api wifi_conn_api = {
    .has_connection_config = wifi_conn_has_config,
    .connect = wifi_conn_connect,
    .disconnect = wifi_conn_disconnect,
    .init = wifi_conn_init,
};
CONN_MGR_CONN_DEFINE(CONNECTIVITY_WIFI_MGMT, &wifi_conn_api);
