// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Network Control Service - WiFi Station Implementation
 *
 * Ported from Helios runtime netctl module.
 * FULLY ASYNC - no blocking timeouts anywhere.
 * All timeouts use k_work_delayable. Callbacks post events.
 */

#include "wifi.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/dns_resolve.h>
#include <zephyr/net/net_config.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/sys/atomic.h>

#include <errno.h>
#include <string.h>

#include "../netctl.h"
#include "../netctl_internal.h"
#include "app/events.h"
#include "icle/app.h"

#ifndef CONFIG_ICLE_NETCTL_LOG_LEVEL
#define CONFIG_ICLE_NETCTL_LOG_LEVEL 3
#endif

#ifndef CONFIG_ICLE_NETCTL_WIFI_CONNECT_TIMEOUT_SEC
#define CONFIG_ICLE_NETCTL_WIFI_CONNECT_TIMEOUT_SEC 30
#endif

#ifndef CONFIG_ICLE_NETCTL_WIFI_DISCONNECT_TIMEOUT_SEC
#define CONFIG_ICLE_NETCTL_WIFI_DISCONNECT_TIMEOUT_SEC 5
#endif

#ifndef CONFIG_ICLE_NETCTL_WIFI_SCAN_TIMEOUT_SEC
#define CONFIG_ICLE_NETCTL_WIFI_SCAN_TIMEOUT_SEC 10
#endif

LOG_MODULE_DECLARE(netctl, CONFIG_ICLE_NETCTL_LOG_LEVEL);

/*
 * WiFi management events we care about
 */
#define WIFI_MGMT_EVENTS (NET_EVENT_WIFI_SCAN_DONE |		\
			  NET_EVENT_WIFI_SCAN_RESULT |		\
			  NET_EVENT_WIFI_CONNECT_RESULT |	\
			  NET_EVENT_WIFI_DISCONNECT_RESULT |	\
			  NET_EVENT_WIFI_DISCONNECT_COMPLETE)

static void wifi_mgmt_event_handler(struct net_mgmt_event_callback *cb,
				    uint32_t mgmt_event, struct net_if *iface);

/*
 * Module state - global handle for callbacks
 */
static netctl_t *g_ctl;

/* Stored credentials for async connect flow */
static netctl_wifi_creds_t g_pending_creds;
/* atomic_t: written from API thread and timer ISR, read from callbacks */
static atomic_t g_connect_in_progress;

/*
 * Dedicated WiFi workqueue - net_mgmt calls can block for seconds
 * on ESP32, so we must NOT run them on the system workqueue (which
 * would block all other k_work items like heartbeat, timeouts, etc.)
 */
#define WIFI_WORKQ_STACK_SIZE 4096
#define WIFI_WORKQ_PRIORITY   8
static K_THREAD_STACK_DEFINE(wifi_workq_stack, WIFI_WORKQ_STACK_SIZE);
static struct k_work_q wifi_workq;
static bool wifi_workq_started;

/* Connect timeout uses k_timer (ISR context) to post netctl event */
static struct k_timer wifi_connect_timer;

/* Connect work item runs on dedicated WiFi workqueue */
static struct k_work wifi_connect_work;

/* Forward declarations */
static void connect_timeout_expiry(struct k_timer *timer);
static void wifi_connect_work_handler(struct k_work *work);

/*
 * Per-event handler functions — extracted to reduce CCN of the dispatcher.
 * Each handler is called with g_ctl guaranteed non-NULL.
 */

/**
 * @brief Handle NET_EVENT_WIFI_SCAN_RESULT — store one scan entry
 */
static void handle_scan_result(struct net_mgmt_event_callback *cb)
{
	const struct wifi_scan_result *entry =
		(const struct wifi_scan_result *)cb->info;
	netctl_event_scan_result_t *result;
	size_t copy_len;

	k_mutex_lock(&g_ctl->wifi_lock, K_FOREVER);
	if (g_ctl->wifi_scan.count < CONFIG_ICLE_NETCTL_WIFI_SCAN_MAX_RESULTS) {
		result = &g_ctl->wifi_scan.results[g_ctl->wifi_scan.count];

		memset(result, 0, sizeof(*result));
		copy_len = MIN(entry->ssid_length,
			       NETCTL_WIFI_SSID_MAX_LEN - 1);
		memcpy(result->ssid, entry->ssid, copy_len);
		result->ssid[copy_len] = '\0';
		result->rssi = entry->rssi;
		result->channel = entry->channel;
		result->security = entry->security;
		g_ctl->wifi_scan.count++;

		LOG_DBG("Scan result: %s (rssi=%d, ch=%d)",
			result->ssid, result->rssi, result->channel);
	}
	k_mutex_unlock(&g_ctl->wifi_lock);
}

/**
 * @brief Handle NET_EVENT_WIFI_SCAN_DONE — either start connect or signal done
 */
static void handle_scan_done(void)
{
	struct wifi_connect_req_params params;
	bool found = false;
	uint8_t security = 0;
	int ret;

	k_mutex_lock(&g_ctl->wifi_lock, K_FOREVER);
	LOG_INF("WiFi scan complete: %zu networks found", g_ctl->wifi_scan.count);
	g_ctl->wifi_scan.scan_in_progress = false;

	/*
	 * If we have a pending connect, look for the target SSID
	 * and start the connect phase.
	 */
	if (!atomic_get(&g_connect_in_progress) ||
	    g_pending_creds.ssid[0] == '\0') {
		k_mutex_unlock(&g_ctl->wifi_lock);
		/* Standalone scan - just signal done */
		k_sem_give(&g_ctl->wifi_scan.scan_done_sem);
		return;
	}

	for (size_t i = 0; i < g_ctl->wifi_scan.count; i++) {
		if (strcmp(g_ctl->wifi_scan.results[i].ssid,
			   g_pending_creds.ssid) == 0) {
			found = true;
			security = g_ctl->wifi_scan.results[i].security;
			LOG_INF("Target SSID found: %s (RSSI: %d)",
				g_pending_creds.ssid,
				g_ctl->wifi_scan.results[i].rssi);
			break;
		}
	}
	k_mutex_unlock(&g_ctl->wifi_lock);

	if (!found) {
		LOG_WRN("Target SSID not found: %s, attempting direct connect",
			g_pending_creds.ssid);
	}

	/* Determine security type */
	if (security == 0 && strlen(g_pending_creds.password) > 0)
		security = WIFI_SECURITY_TYPE_PSK;

	/* Start connect (non-blocking) */
	params = (struct wifi_connect_req_params){
		.ssid = (uint8_t *)g_pending_creds.ssid,
		.ssid_length = strlen(g_pending_creds.ssid),
		.psk = (uint8_t *)g_pending_creds.password,
		.psk_length = strlen(g_pending_creds.password),
		.security = security,
		.band = WIFI_FREQ_BAND_UNKNOWN,
		.channel = WIFI_CHANNEL_ANY,
		.mfp = WIFI_MFP_OPTIONAL,
	};

	g_ctl->wifi_connected = false;

	ret = net_mgmt(NET_REQUEST_WIFI_CONNECT, g_ctl->wifi_iface,
		       &params, sizeof(params));

	if (ret < 0) {
		LOG_ERR("WiFi connect request failed: %d", ret);
		atomic_clear(&g_connect_in_progress);
		k_timer_stop(&wifi_connect_timer);
		netctl_notify_connection_failed(g_ctl, NETCTL_IFACE_WIFI_STA, ret);
	} else {
		LOG_INF("WiFi connect started, waiting for result...");
	}
}

/**
 * @brief Handle NET_EVENT_WIFI_CONNECT_RESULT — success or failure path
 */
static void handle_connect_result(struct net_mgmt_event_callback *cb,
				  struct net_if *iface)
{
	const struct wifi_status *status = (const struct wifi_status *)cb->info;
	char ip_buf[NETCTL_IPV4_ADDR_LEN];
	char gw_buf[NETCTL_IPV4_ADDR_LEN];
	char nm_buf[NETCTL_IPV4_ADDR_LEN];
	struct net_if_ipv4 *ipv4;
	struct in_addr *addr;

	if (status->status != 0) {
		LOG_ERR("WiFi connection failed: %d", status->status);
		k_mutex_lock(&g_ctl->wifi_lock, K_FOREVER);
		g_ctl->wifi_connected = false;
		k_mutex_unlock(&g_ctl->wifi_lock);

		k_timer_stop(&wifi_connect_timer);
		atomic_clear(&g_connect_in_progress);
		netctl_notify_connection_failed(g_ctl, NETCTL_IFACE_WIFI_STA,
						status->status);
		return;
	}

	LOG_INF("WiFi connected");
	k_mutex_lock(&g_ctl->wifi_lock, K_FOREVER);
	g_ctl->wifi_connected = true;
	k_mutex_unlock(&g_ctl->wifi_lock);

	/*
	 * Check if we already have a valid IP (DHCP lease retained).
	 */
	ipv4 = iface->config.ip.ipv4;

	if (ipv4 == NULL ||
	    ipv4->unicast[0].ipv4.address.family != AF_INET)
		return;

	addr = &ipv4->unicast[0].ipv4.address.in_addr;

	if (addr->s_addr == 0)
		return;

	net_addr_ntop(AF_INET, addr, ip_buf, sizeof(ip_buf));
	net_addr_ntop(AF_INET, &ipv4->gw, gw_buf, sizeof(gw_buf));
	net_addr_ntop(AF_INET, &ipv4->unicast[0].netmask, nm_buf, sizeof(nm_buf));

	LOG_INF("IP already assigned (retained lease): %s", ip_buf);

	/* Cancel connect timeout - we're done */
	k_timer_stop(&wifi_connect_timer);
	atomic_clear(&g_connect_in_progress);

	netctl_notify_ip_acquired(g_ctl, NETCTL_IFACE_WIFI_STA,
				  ip_buf, gw_buf, nm_buf);
	netctl_notify_connected(g_ctl, NETCTL_IFACE_WIFI_STA);
}

/**
 * @brief Handle NET_EVENT_WIFI_DISCONNECT_RESULT / DISCONNECT_COMPLETE
 */
static void handle_disconnect(struct net_mgmt_event_callback *cb)
{
	const struct wifi_status *status = (const struct wifi_status *)cb->info;

	LOG_INF("WiFi disconnected (reason: %d)", status->status);
	k_mutex_lock(&g_ctl->wifi_lock, K_FOREVER);
	g_ctl->wifi_connected = false;
	k_mutex_unlock(&g_ctl->wifi_lock);

	atomic_clear(&g_connect_in_progress);

	k_sem_give(&g_ctl->wifi_disconnect_sem);
	netctl_notify_disconnected(g_ctl, NETCTL_IFACE_WIFI_STA);
}

/*
 * WiFi management event handler - dispatcher only (CCN <= 6).
 * Each case delegates to a focused sub-handler.
 */
static void wifi_mgmt_event_handler(struct net_mgmt_event_callback *cb,
				    uint32_t mgmt_event, struct net_if *iface)
{
	__ASSERT(!k_is_in_isr(), "WiFi callback must not run in ISR context");

	if (g_ctl == NULL) {
		LOG_WRN("WiFi event received but g_ctl is NULL");
		return;
	}

	switch (mgmt_event) {
	case NET_EVENT_WIFI_SCAN_RESULT:
		handle_scan_result(cb);
		break;

	case NET_EVENT_WIFI_SCAN_DONE:
		handle_scan_done();
		break;

	case NET_EVENT_WIFI_CONNECT_RESULT:
		handle_connect_result(cb, iface);
		break;

	case NET_EVENT_WIFI_DISCONNECT_RESULT:
	case NET_EVENT_WIFI_DISCONNECT_COMPLETE:
		handle_disconnect(cb);
		break;

	default:
		break;
	}
}

/*
 * DHCP address change handler
 */
static struct net_mgmt_event_callback dhcp_cb;

static void dhcp_event_handler(struct net_mgmt_event_callback *cb,
			       uint32_t mgmt_event, struct net_if *iface)
{
	char ip_buf[NETCTL_IPV4_ADDR_LEN];
	char gw_buf[NETCTL_IPV4_ADDR_LEN];
	char nm_buf[NETCTL_IPV4_ADDR_LEN];
	struct net_if_ipv4 *ipv4;

	__ASSERT(!k_is_in_isr(), "DHCP callback must not run in ISR context");

	if (g_ctl == NULL)
		return;

	if (mgmt_event == NET_EVENT_IPV4_ADDR_ADD) {
		ipv4 = iface->config.ip.ipv4;

		if (ipv4 == NULL)
			return;

		if (ipv4->unicast[0].ipv4.address.family != AF_INET)
			return;

		net_addr_ntop(AF_INET, &ipv4->unicast[0].ipv4.address.in_addr,
			      ip_buf, sizeof(ip_buf));
		net_addr_ntop(AF_INET, &ipv4->gw, gw_buf, sizeof(gw_buf));
		net_addr_ntop(AF_INET, &ipv4->unicast[0].netmask,
			      nm_buf, sizeof(nm_buf));

		LOG_INF("IP acquired: %s (gw: %s)", ip_buf, gw_buf);

		k_mutex_lock(&g_ctl->wifi_lock, K_FOREVER);
		g_ctl->wifi_connected = true;
		k_mutex_unlock(&g_ctl->wifi_lock);

		/* Cancel connect timeout - we have IP */
		k_timer_stop(&wifi_connect_timer);
		atomic_clear(&g_connect_in_progress);

		netctl_notify_ip_acquired(g_ctl, NETCTL_IFACE_WIFI_STA,
					  ip_buf, gw_buf, nm_buf);
		netctl_notify_connected(g_ctl, NETCTL_IFACE_WIFI_STA);
	}
}

/*
 * Timeout handlers
 */

/*
 * Connect timeout - fires from timer ISR context.
 * k_event_post is ISR-safe. We post directly to the app event system
 * because netctl_notify uses k_mutex which is not ISR-safe.
 */
static void connect_timeout_expiry(struct k_timer *timer)
{
	ARG_UNUSED(timer);

	if (!atomic_get(&g_connect_in_progress))
		return;

	atomic_clear(&g_connect_in_progress);

	/* Post directly to app event loop - ISR-safe */
	icle_events_post(ICLE_EVENT_WIFI_CONNECT_TIMEOUT);
}

/*
 * WiFi connect work handler - runs on dedicated WiFi workqueue.
 * Can safely block without affecting system workqueue.
 */
static void wifi_connect_work_handler(struct k_work *work)
{
	struct wifi_connect_req_params params;
	uint8_t security;
	int ret;

	ARG_UNUSED(work);

	if (g_ctl == NULL || !atomic_get(&g_connect_in_progress))
		return;

	/*
	 * Skip WiFi scan — go directly to connect.
	 *
	 * net_mgmt(NET_REQUEST_WIFI_SCAN) blocks the system workqueue
	 * on ESP32 for the entire scan duration (2-10s), which prevents
	 * ALL other k_work_delayable items from firing (boot timeout,
	 * heartbeat, etc.). Since we already know the SSID and password,
	 * scanning is unnecessary.
	 */
	LOG_INF("Starting direct WiFi connect to: %s", g_pending_creds.ssid);

	security = WIFI_SECURITY_TYPE_PSK;

	if (strlen(g_pending_creds.password) == 0)
		security = WIFI_SECURITY_TYPE_NONE;

	params = (struct wifi_connect_req_params){
		.ssid = (uint8_t *)g_pending_creds.ssid,
		.ssid_length = strlen(g_pending_creds.ssid),
		.psk = (uint8_t *)g_pending_creds.password,
		.psk_length = strlen(g_pending_creds.password),
		.security = security,
		.band = WIFI_FREQ_BAND_UNKNOWN,
		.channel = WIFI_CHANNEL_ANY,
		.mfp = WIFI_MFP_OPTIONAL,
	};

	g_ctl->wifi_connected = false;

	ret = net_mgmt(NET_REQUEST_WIFI_CONNECT, g_ctl->wifi_iface,
		       &params, sizeof(params));

	if (ret < 0) {
		LOG_ERR("WiFi connect request failed: %d", ret);
		atomic_clear(&g_connect_in_progress);
		k_timer_stop(&wifi_connect_timer);
		netctl_notify_connection_failed(
			g_ctl, NETCTL_IFACE_WIFI_STA, ret);
	} else {
		LOG_INF("WiFi connect started, waiting for result...");
	}
}

static int wifi_ensure_clean_state(netctl_t *ctl)
{
	struct wifi_iface_status status = {0};
	int ret;

	ret = net_mgmt(NET_REQUEST_WIFI_IFACE_STATUS, ctl->wifi_iface,
		       &status, sizeof(status));
	if (ret < 0) {
		LOG_DBG("Could not get WiFi status: %d (continuing)", ret);
		return 0;
	}

	LOG_DBG("WiFi iface state: %d", status.state);

	if (status.state != WIFI_STATE_INACTIVE &&
	    status.state != WIFI_STATE_DISCONNECTED &&
	    status.state != WIFI_STATE_INTERFACE_DISABLED) {
		LOG_INF("Cleaning up stale WiFi state (%d)...", status.state);

		ret = net_mgmt(NET_REQUEST_WIFI_DISCONNECT, ctl->wifi_iface,
			       NULL, 0);
		if (ret < 0 && ret != -EALREADY)
			LOG_DBG("Cleanup disconnect returned: %d", ret);
	}

	return 0;
}

/*
 * Public API
 */

int netctl_wifi_init(netctl_t *ctl)
{
	if (ctl == NULL)
		return -EINVAL;

	ctl->wifi_iface = net_if_get_wifi_sta();
	if (ctl->wifi_iface == NULL) {
		LOG_ERR("No WiFi interface found");
		return -ENODEV;
	}

	LOG_INF("WiFi interface found: %s", ctl->wifi_iface->config.name);

	k_sem_init(&ctl->wifi_scan.scan_done_sem, 0, 1);
	k_sem_init(&ctl->wifi_connect_sem, 0, 1);
	k_sem_init(&ctl->wifi_disconnect_sem, 0, 1);
	k_sem_init(&ctl->wifi_ip_sem, 0, 1);
	k_mutex_init(&ctl->wifi_lock);

	/* Start dedicated WiFi workqueue (once) */
	if (!wifi_workq_started) {
		k_work_queue_init(&wifi_workq);
		k_work_queue_start(&wifi_workq, wifi_workq_stack,
				   K_THREAD_STACK_SIZEOF(wifi_workq_stack),
				   WIFI_WORKQ_PRIORITY, NULL);
		k_thread_name_set(&wifi_workq.thread, "wifi_wq");
		wifi_workq_started = true;
	}

	/* Initialize connect timer (ISR context) and work item */
	k_timer_init(&wifi_connect_timer, connect_timeout_expiry, NULL);
	k_work_init(&wifi_connect_work, wifi_connect_work_handler);

	g_ctl = ctl;
	atomic_clear(&g_connect_in_progress);

	net_mgmt_init_event_callback(&ctl->wifi_mgmt_cb, wifi_mgmt_event_handler,
				     WIFI_MGMT_EVENTS);
	net_mgmt_add_event_callback(&ctl->wifi_mgmt_cb);

	net_mgmt_init_event_callback(&dhcp_cb, dhcp_event_handler,
				     NET_EVENT_IPV4_ADDR_ADD);
	net_mgmt_add_event_callback(&dhcp_cb);

	ctl->wifi_connected = false;
	ctl->wifi_scan.scan_in_progress = false;
	ctl->wifi_scan.count = 0;

	LOG_INF("WiFi init complete (async mode)");

	return 0;
}

int netctl_wifi_deinit(netctl_t *ctl)
{
	bool was_connected;

	if (ctl == NULL)
		return -EINVAL;

	/* Cancel pending work */
	k_timer_stop(&wifi_connect_timer);
	k_work_cancel(&wifi_connect_work);
	atomic_clear(&g_connect_in_progress);

	k_mutex_lock(&ctl->wifi_lock, K_FOREVER);
	was_connected = ctl->wifi_connected;
	k_mutex_unlock(&ctl->wifi_lock);

	if (was_connected)
		netctl_wifi_disconnect(ctl);

	net_mgmt_del_event_callback(&ctl->wifi_mgmt_cb);
	net_mgmt_del_event_callback(&dhcp_cb);

	g_ctl = NULL;

	return 0;
}

/**
 * @brief Async WiFi connect - starts scan+connect, returns immediately
 *
 * Flow:
 *   1. Clean up stale state if needed
 *   2. Schedule scan after brief delay (lets cleanup settle)
 *   3. Schedule connect timeout (30s)
 *   4. Return 0 (or -EINPROGRESS)
 *
 * Async callbacks handle the rest:
 *   SCAN_DONE -> start connect
 *   CONNECT_RESULT -> wait for DHCP
 *   IPV4_ADDR_ADD -> cancel timeout, notify connected
 *   timeout -> notify failed
 */
int netctl_wifi_connect(netctl_t *ctl, const netctl_wifi_creds_t *creds)
{
	if (ctl == NULL || creds == NULL || ctl->wifi_iface == NULL)
		return -EINVAL;

	if (creds->ssid[0] == '\0') {
		LOG_ERR("SSID cannot be empty");
		return -EINVAL;
	}

	if (atomic_get(&g_connect_in_progress)) {
		LOG_WRN("Connect already in progress");
		return -EBUSY;
	}

	LOG_INF("Starting async WiFi connect to: %s", creds->ssid);

	/* Store credentials for use by async callbacks */
	memcpy(&g_pending_creds, creds, sizeof(g_pending_creds));
	atomic_set(&g_connect_in_progress, 1);

	/* Clean up stale state */
	wifi_ensure_clean_state(ctl);

	/*
	 * Submit connect work to dedicated WiFi workqueue.
	 * This runs net_mgmt calls on a separate thread so the
	 * system workqueue stays free for other work items.
	 */
	k_work_submit_to_queue(&wifi_workq, &wifi_connect_work);

	/* Start connect timeout timer (ISR context, always fires) */
	k_timer_start(&wifi_connect_timer,
		      K_SECONDS(CONFIG_ICLE_NETCTL_WIFI_CONNECT_TIMEOUT_SEC),
		      K_NO_WAIT);

	return 0;
}

int netctl_wifi_disconnect(netctl_t *ctl)
{
	bool connected;
	int ret;

	if (ctl == NULL || ctl->wifi_iface == NULL)
		return -EINVAL;

	/* Cancel any pending connect */
	k_timer_stop(&wifi_connect_timer);
	k_work_cancel(&wifi_connect_work);
	atomic_clear(&g_connect_in_progress);

	k_mutex_lock(&ctl->wifi_lock, K_FOREVER);
	connected = ctl->wifi_connected;
	k_mutex_unlock(&ctl->wifi_lock);

	if (!connected) {
		LOG_DBG("WiFi not connected");
		return -EALREADY;
	}

	LOG_INF("Disconnecting from WiFi...");

	ret = net_mgmt(NET_REQUEST_WIFI_DISCONNECT, ctl->wifi_iface,
		       NULL, 0);
	if (ret < 0) {
		LOG_ERR("Failed to request WiFi disconnection: %d", ret);
		/* Force state update */
		k_mutex_lock(&ctl->wifi_lock, K_FOREVER);
		ctl->wifi_connected = false;
		k_mutex_unlock(&ctl->wifi_lock);
		return ret;
	}

	return 0;
}

int netctl_wifi_scan(netctl_t *ctl)
{
	int ret;

	if (ctl == NULL || ctl->wifi_iface == NULL)
		return -EINVAL;

	k_mutex_lock(&ctl->wifi_lock, K_FOREVER);
	if (ctl->wifi_scan.scan_in_progress) {
		k_mutex_unlock(&ctl->wifi_lock);
		LOG_WRN("Scan already in progress");
		return -EBUSY;
	}

	LOG_INF("Starting WiFi scan...");

	k_sem_reset(&ctl->wifi_scan.scan_done_sem);
	ctl->wifi_scan.count = 0;
	ctl->wifi_scan.scan_in_progress = true;
	k_mutex_unlock(&ctl->wifi_lock);

	ret = net_mgmt(NET_REQUEST_WIFI_SCAN, ctl->wifi_iface, NULL, 0);

	if (ret < 0) {
		LOG_ERR("Failed to request WiFi scan: %d", ret);
		k_mutex_lock(&ctl->wifi_lock, K_FOREVER);
		ctl->wifi_scan.scan_in_progress = false;
		k_mutex_unlock(&ctl->wifi_lock);
		return ret;
	}

	LOG_INF("Scan started, waiting for results...");
	return 0;
}

int netctl_wifi_get_scan_results(netctl_t *ctl, netctl_event_scan_result_t *results,
				 size_t max_results, size_t *count)
{
	size_t copy_count;

	if (ctl == NULL || results == NULL || count == NULL)
		return -EINVAL;

	k_mutex_lock(&ctl->wifi_lock, K_FOREVER);
	copy_count = MIN(max_results, ctl->wifi_scan.count);

	memcpy(results, ctl->wifi_scan.results,
	       copy_count * sizeof(netctl_event_scan_result_t));
	*count = copy_count;
	k_mutex_unlock(&ctl->wifi_lock);

	return 0;
}
