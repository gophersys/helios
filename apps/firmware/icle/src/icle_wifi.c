/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE WiFi Station Manager
 *
 * Manages WiFi STA connection, reconnection, and status.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#include "icle_wifi.h"

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_wifi, CONFIG_LOG_DEFAULT_LEVEL);

#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/net_event.h>
#include <zephyr/net/dhcpv4.h>
#include <string.h>
#include <errno.h>

/* Configuration */
#define WIFI_CONNECT_TIMEOUT_MS      30000
#define WIFI_RECONNECT_BASE_MS       1000
#define WIFI_RECONNECT_MAX_MS        60000
#define WIFI_MAX_CALLBACKS           4

/* Reconnection work queue stack */
#define RECONNECT_STACK_SIZE         1024
#define RECONNECT_THREAD_PRIORITY    7

/* Module state */
struct wifi_ctx {
	bool initialized;
	enum icle_wifi_state state;
	struct net_if *iface;

	/* Current connection parameters */
	char ssid[33];
	char psk[65];
	bool auto_reconnect;

	/* Synchronization */
	struct k_mutex state_mutex;
	struct k_sem connect_sem;

	/* Statistics */
	uint32_t connect_start_time;
	uint32_t connected_time_ms;
	uint32_t reconnect_count;
	int8_t rssi;
	uint8_t channel;
	uint8_t ip_addr[4];

	/* Reconnection backoff */
	uint32_t reconnect_delay_ms;

	/* Callbacks */
	struct {
		icle_wifi_callback_t callback;
		void *user_data;
	} callbacks[WIFI_MAX_CALLBACKS];

	/* Event callbacks */
	struct net_mgmt_event_callback wifi_cb;
	struct net_mgmt_event_callback net_cb;

	/* Reconnection work */
	struct k_work_delayable reconnect_work;
};

static struct wifi_ctx ctx;

/* Forward declarations */
static void wifi_event_handler(struct net_mgmt_event_callback *cb,
			       uint32_t mgmt_event, struct net_if *iface);
static void net_event_handler(struct net_mgmt_event_callback *cb,
			      uint32_t mgmt_event, struct net_if *iface);
static void reconnect_work_handler(struct k_work *work);

/**
 * @brief Set WiFi state with mutex protection
 */
static void set_state(enum icle_wifi_state new_state)
{
	k_mutex_lock(&ctx.state_mutex, K_FOREVER);
	ctx.state = new_state;
	k_mutex_unlock(&ctx.state_mutex);
}

/**
 * @brief Get WiFi state with mutex protection
 */
static enum icle_wifi_state get_state(void)
{
	enum icle_wifi_state state;

	k_mutex_lock(&ctx.state_mutex, K_FOREVER);
	state = ctx.state;
	k_mutex_unlock(&ctx.state_mutex);

	return state;
}

/**
 * @brief Notify all registered callbacks
 */
static void notify_callbacks(bool connected)
{
	for (int i = 0; i < WIFI_MAX_CALLBACKS; i++) {
		if (ctx.callbacks[i].callback != NULL) {
			ctx.callbacks[i].callback(connected, ctx.callbacks[i].user_data);
		}
	}
}

/**
 * @brief Handle WiFi connect result event
 */
static void handle_connect_result(struct net_if *iface,
				  const struct wifi_status *status)
{
	ARG_UNUSED(iface);

	if (status->status == 0) {
		LOG_INF("WiFi connected to SSID: %s", ctx.ssid);
		ctx.connect_start_time = k_uptime_get_32();
		ctx.reconnect_delay_ms = WIFI_RECONNECT_BASE_MS;
		set_state(ICLE_WIFI_STATE_CONNECTED);
		notify_callbacks(true);
	} else {
		LOG_ERR("WiFi connection failed: %d", status->status);
		set_state(ICLE_WIFI_STATE_DISCONNECTED);

		/* Schedule reconnection if auto-reconnect enabled */
		if (ctx.auto_reconnect && strlen(ctx.ssid) > 0) {
			LOG_INF("Scheduling reconnection in %u ms", ctx.reconnect_delay_ms);
			k_work_schedule(&ctx.reconnect_work,
					K_MSEC(ctx.reconnect_delay_ms));

			/* Exponential backoff */
			ctx.reconnect_delay_ms = MIN(ctx.reconnect_delay_ms * 2,
						     WIFI_RECONNECT_MAX_MS);
		}
	}

	k_sem_give(&ctx.connect_sem);
}

/**
 * @brief Handle WiFi disconnect event
 */
static void handle_disconnect(struct net_if *iface,
			      const struct wifi_status *status)
{
	ARG_UNUSED(iface);
	ARG_UNUSED(status);

	enum icle_wifi_state prev_state = get_state();

	if (prev_state == ICLE_WIFI_STATE_CONNECTED) {
		ctx.connected_time_ms += k_uptime_get_32() - ctx.connect_start_time;
	}

	LOG_INF("WiFi disconnected");
	set_state(ICLE_WIFI_STATE_DISCONNECTED);
	memset(ctx.ip_addr, 0, sizeof(ctx.ip_addr));
	ctx.rssi = 0;
	ctx.channel = 0;

	notify_callbacks(false);

	/* Schedule reconnection if auto-reconnect enabled */
	if (ctx.auto_reconnect && strlen(ctx.ssid) > 0) {
		LOG_INF("Scheduling reconnection in %u ms", ctx.reconnect_delay_ms);
		k_work_schedule(&ctx.reconnect_work,
				K_MSEC(ctx.reconnect_delay_ms));

		/* Exponential backoff */
		ctx.reconnect_delay_ms = MIN(ctx.reconnect_delay_ms * 2,
					     WIFI_RECONNECT_MAX_MS);
	}
}

/**
 * @brief WiFi management event handler
 */
static void wifi_event_handler(struct net_mgmt_event_callback *cb,
			       uint32_t mgmt_event, struct net_if *iface)
{
	const struct wifi_status *status;

	if (iface != ctx.iface) {
		return;
	}

	status = (const struct wifi_status *)cb->info;

	switch (mgmt_event) {
	case NET_EVENT_WIFI_CONNECT_RESULT:
		handle_connect_result(iface, status);
		break;

	case NET_EVENT_WIFI_DISCONNECT_RESULT:
		handle_disconnect(iface, status);
		break;

	default:
		break;
	}
}

/**
 * @brief Network management event handler (for IP address)
 */
static void net_event_handler(struct net_mgmt_event_callback *cb,
			      uint32_t mgmt_event, struct net_if *iface)
{
	ARG_UNUSED(cb);

	if (iface != ctx.iface) {
		return;
	}

	if (mgmt_event == NET_EVENT_IPV4_ADDR_ADD) {
		struct net_if_config *cfg = net_if_get_config(iface);

		if (cfg && cfg->ip.ipv4) {
			for (int i = 0; i < NET_IF_MAX_IPV4_ADDR; i++) {
				struct net_if_addr *addr = &cfg->ip.ipv4->unicast[i].ipv4;

				if (addr->addr_type == NET_ADDR_DHCP) {
					struct in_addr *in = &addr->address.in_addr;
					char buf[NET_IPV4_ADDR_LEN];

					memcpy(ctx.ip_addr, &in->s_addr, 4);

					LOG_INF("DHCP IP: %s",
						net_addr_ntop(AF_INET, in, buf, sizeof(buf)));
					break;
				}
			}
		}
	}
}

/**
 * @brief Reconnection work handler
 */
static void reconnect_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	int ret;

	enum icle_wifi_state state = get_state();

	if (state == ICLE_WIFI_STATE_CONNECTED ||
	    state == ICLE_WIFI_STATE_CONNECTING) {
		return;
	}

	if (!ctx.auto_reconnect || strlen(ctx.ssid) == 0) {
		return;
	}

	LOG_INF("Attempting WiFi reconnection (attempt %u)", ctx.reconnect_count + 1);
	ctx.reconnect_count++;

	struct icle_wifi_params params = {
		.ssid = ctx.ssid,
		.psk = ctx.psk,
		.timeout_ms = 0,  /* Non-blocking */
		.auto_reconnect = ctx.auto_reconnect,
	};

	ret = icle_wifi_connect(&params);
	if (ret < 0 && ret != -EALREADY) {
		LOG_ERR("Reconnection request failed: %d", ret);

		/* Schedule another attempt */
		k_work_schedule(&ctx.reconnect_work,
				K_MSEC(ctx.reconnect_delay_ms));
	}
}

int icle_wifi_init(void)
{
	int ret;

	if (ctx.initialized) {
		return 0;
	}

	memset(&ctx, 0, sizeof(ctx));

	/* Initialize synchronization primitives */
	ret = k_mutex_init(&ctx.state_mutex);
	if (ret < 0) {
		LOG_ERR("Failed to init state mutex: %d", ret);
		return ret;
	}

	ret = k_sem_init(&ctx.connect_sem, 0, 1);
	if (ret < 0) {
		LOG_ERR("Failed to init connect semaphore: %d", ret);
		return ret;
	}

	/* Initialize reconnection work */
	k_work_init_delayable(&ctx.reconnect_work, reconnect_work_handler);

	/* Get WiFi interface */
	ctx.iface = net_if_get_default();
	if (!ctx.iface) {
		LOG_ERR("No network interface found");
		return -ENODEV;
	}

	/* Register WiFi management callbacks */
	net_mgmt_init_event_callback(&ctx.wifi_cb,
				     wifi_event_handler,
				     NET_EVENT_WIFI_CONNECT_RESULT |
				     NET_EVENT_WIFI_DISCONNECT_RESULT);
	net_mgmt_add_event_callback(&ctx.wifi_cb);

	/* Register network management callbacks (for IP) */
	net_mgmt_init_event_callback(&ctx.net_cb,
				     net_event_handler,
				     NET_EVENT_IPV4_ADDR_ADD);
	net_mgmt_add_event_callback(&ctx.net_cb);

	ctx.state = ICLE_WIFI_STATE_DISCONNECTED;
	ctx.reconnect_delay_ms = WIFI_RECONNECT_BASE_MS;
	ctx.initialized = true;

	LOG_INF("WiFi subsystem initialized");
	return 0;
}

int icle_wifi_deinit(void)
{
	if (!ctx.initialized) {
		return -ENODEV;
	}

	/* Cancel any pending reconnection */
	k_work_cancel_delayable(&ctx.reconnect_work);

	/* Disconnect if connected */
	if (get_state() == ICLE_WIFI_STATE_CONNECTED ||
	    get_state() == ICLE_WIFI_STATE_CONNECTING) {
		icle_wifi_disconnect();
	}

	/* Remove event callbacks */
	net_mgmt_del_event_callback(&ctx.wifi_cb);
	net_mgmt_del_event_callback(&ctx.net_cb);

	ctx.initialized = false;
	ctx.state = ICLE_WIFI_STATE_DISABLED;

	LOG_INF("WiFi subsystem deinitialized");
	return 0;
}

int icle_wifi_connect(const struct icle_wifi_params *params)
{
	struct wifi_connect_req_params cnx_params = {0};
	int ret;

	if (!ctx.initialized) {
		return -ENODEV;
	}

	if (params == NULL || params->ssid == NULL) {
		return -EINVAL;
	}

	if (strlen(params->ssid) == 0) {
		LOG_ERR("SSID cannot be empty");
		return -EINVAL;
	}

	enum icle_wifi_state state = get_state();

	if (state == ICLE_WIFI_STATE_CONNECTED) {
		LOG_WRN("Already connected to WiFi");
		return -EALREADY;
	}

	if (state == ICLE_WIFI_STATE_CONNECTING) {
		LOG_WRN("Connection already in progress");
		return -EBUSY;
	}

	/* Store connection parameters */
	strncpy(ctx.ssid, params->ssid, sizeof(ctx.ssid) - 1);
	ctx.ssid[sizeof(ctx.ssid) - 1] = '\0';

	if (params->psk != NULL) {
		strncpy(ctx.psk, params->psk, sizeof(ctx.psk) - 1);
		ctx.psk[sizeof(ctx.psk) - 1] = '\0';
	} else {
		ctx.psk[0] = '\0';
	}

	ctx.auto_reconnect = params->auto_reconnect;

	/* Prepare connection request */
	cnx_params.ssid = (uint8_t *)ctx.ssid;
	cnx_params.ssid_length = strlen(ctx.ssid);
	cnx_params.psk = (uint8_t *)ctx.psk;
	cnx_params.psk_length = strlen(ctx.psk);
	cnx_params.channel = WIFI_CHANNEL_ANY;
	cnx_params.security = (strlen(ctx.psk) > 0) ? WIFI_SECURITY_TYPE_PSK
						    : WIFI_SECURITY_TYPE_NONE;
	cnx_params.mfp = WIFI_MFP_OPTIONAL;

	k_sem_reset(&ctx.connect_sem);
	set_state(ICLE_WIFI_STATE_CONNECTING);

	LOG_INF("Connecting to WiFi SSID: %s", ctx.ssid);

	ret = net_mgmt(NET_REQUEST_WIFI_CONNECT, ctx.iface, &cnx_params,
		       sizeof(struct wifi_connect_req_params));
	if (ret < 0) {
		LOG_ERR("WiFi connect request failed: %d", ret);
		set_state(ICLE_WIFI_STATE_DISCONNECTED);
		return ret;
	}

	return 0;
}

int icle_wifi_connect_simple(const char *ssid, const char *psk,
			     uint32_t timeout_ms)
{
	int ret;

	struct icle_wifi_params params = {
		.ssid = ssid,
		.psk = psk,
		.timeout_ms = timeout_ms,
		.auto_reconnect = true,
	};

	ret = icle_wifi_connect(&params);
	if (ret < 0) {
		return ret;
	}

	if (timeout_ms > 0) {
		return icle_wifi_wait_connected(timeout_ms);
	}

	return 0;
}

int icle_wifi_wait_connected(uint32_t timeout_ms)
{
	int ret;
	k_timeout_t timeout;

	if (!ctx.initialized) {
		return -ENODEV;
	}

	enum icle_wifi_state state = get_state();

	if (state == ICLE_WIFI_STATE_CONNECTED) {
		return 0;
	}

	if (state != ICLE_WIFI_STATE_CONNECTING) {
		return -ENOTCONN;
	}

	if (timeout_ms == 0) {
		timeout = K_FOREVER;
	} else {
		timeout = K_MSEC(timeout_ms);
	}

	ret = k_sem_take(&ctx.connect_sem, timeout);
	if (ret == -EAGAIN) {
		LOG_ERR("WiFi connection timeout");
		return -ETIMEDOUT;
	}

	state = get_state();
	return (state == ICLE_WIFI_STATE_CONNECTED) ? 0 : -EIO;
}

int icle_wifi_disconnect(void)
{
	int ret;

	if (!ctx.initialized) {
		return -ENODEV;
	}

	/* Cancel any pending reconnection */
	k_work_cancel_delayable(&ctx.reconnect_work);

	/* Clear auto-reconnect to prevent reconnection */
	ctx.auto_reconnect = false;

	enum icle_wifi_state state = get_state();

	if (state != ICLE_WIFI_STATE_CONNECTED &&
	    state != ICLE_WIFI_STATE_CONNECTING) {
		return 0;
	}

	LOG_INF("Disconnecting from WiFi");

	ret = net_mgmt(NET_REQUEST_WIFI_DISCONNECT, ctx.iface, NULL, 0);
	if (ret < 0) {
		LOG_ERR("WiFi disconnect request failed: %d", ret);
		return ret;
	}

	set_state(ICLE_WIFI_STATE_DISCONNECTED);
	return 0;
}

bool icle_wifi_is_connected(void)
{
	return get_state() == ICLE_WIFI_STATE_CONNECTED;
}

enum icle_wifi_state icle_wifi_get_state(void)
{
	return get_state();
}

int icle_wifi_get_status(struct icle_wifi_status *status)
{
	if (!ctx.initialized) {
		return -ENODEV;
	}

	if (status == NULL) {
		return -EINVAL;
	}

	k_mutex_lock(&ctx.state_mutex, K_FOREVER);

	status->state = ctx.state;
	strncpy(status->ssid, ctx.ssid, sizeof(status->ssid) - 1);
	status->ssid[sizeof(status->ssid) - 1] = '\0';
	status->rssi = ctx.rssi;
	status->channel = ctx.channel;
	memcpy(status->ip_addr, ctx.ip_addr, sizeof(status->ip_addr));
	status->reconnect_count = ctx.reconnect_count;

	if (ctx.state == ICLE_WIFI_STATE_CONNECTED) {
		status->connected_time_ms = ctx.connected_time_ms +
					    (k_uptime_get_32() - ctx.connect_start_time);
	} else {
		status->connected_time_ms = ctx.connected_time_ms;
	}

	k_mutex_unlock(&ctx.state_mutex);

	/* Update RSSI if connected */
	if (status->state == ICLE_WIFI_STATE_CONNECTED && ctx.iface != NULL) {
		struct wifi_iface_status wifi_status = {0};
		int ret;

		ret = net_mgmt(NET_REQUEST_WIFI_IFACE_STATUS, ctx.iface,
			       &wifi_status, sizeof(wifi_status));
		if (ret == 0) {
			status->rssi = wifi_status.rssi;
			status->channel = wifi_status.channel;
			ctx.rssi = wifi_status.rssi;
			ctx.channel = wifi_status.channel;
		}
	}

	return 0;
}

int icle_wifi_register_callback(icle_wifi_callback_t callback, void *user_data)
{
	if (!ctx.initialized) {
		return -ENODEV;
	}

	if (callback == NULL) {
		return -EINVAL;
	}

	for (int i = 0; i < WIFI_MAX_CALLBACKS; i++) {
		if (ctx.callbacks[i].callback == NULL) {
			ctx.callbacks[i].callback = callback;
			ctx.callbacks[i].user_data = user_data;
			return 0;
		}
	}

	LOG_ERR("No free callback slots");
	return -ENOMEM;
}

void icle_wifi_unregister_callback(icle_wifi_callback_t callback)
{
	if (!ctx.initialized || callback == NULL) {
		return;
	}

	for (int i = 0; i < WIFI_MAX_CALLBACKS; i++) {
		if (ctx.callbacks[i].callback == callback) {
			ctx.callbacks[i].callback = NULL;
			ctx.callbacks[i].user_data = NULL;
			return;
		}
	}
}

void icle_wifi_set_auto_reconnect(bool enable)
{
	if (!ctx.initialized) {
		return;
	}

	ctx.auto_reconnect = enable;

	if (!enable) {
		/* Cancel any pending reconnection */
		k_work_cancel_delayable(&ctx.reconnect_work);
	}

	LOG_INF("Auto-reconnect %s", enable ? "enabled" : "disabled");
}

struct net_if *icle_wifi_get_iface(void)
{
	if (!ctx.initialized) {
		return NULL;
	}

	return ctx.iface;
}

const char *icle_wifi_state_name(enum icle_wifi_state state)
{
	static const char * const state_names[] = {
		[ICLE_WIFI_STATE_DISABLED] = "disabled",
		[ICLE_WIFI_STATE_DISCONNECTED] = "disconnected",
		[ICLE_WIFI_STATE_CONNECTING] = "connecting",
		[ICLE_WIFI_STATE_CONNECTED] = "connected",
		[ICLE_WIFI_STATE_ERROR] = "error",
	};

	if (state < ARRAY_SIZE(state_names)) {
		return state_names[state];
	}

	return "unknown";
}
