// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE WiFi Station Manager
 *
 * Thin wrapper around the netctl service (ported from Helios runtime).
 * Provides the icle_wifi_* API used by the state machine, delegates
 * all actual WiFi operations to netctl internally.
 */

#include "wifi.h"
#include "app/events.h"
#include "icle/app.h"

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_wifi, CONFIG_LOG_DEFAULT_LEVEL);

#include <zephyr/sys/atomic.h>
#include <string.h>
#include <errno.h>

#include "services/netctl/netctl.h"
#include "services/netctl/wifi/wifi.h"

/* Profile name for the active STA connection */
#define WIFI_PROFILE_NAME "icle_sta"

/* Module state */
static struct {
	bool initialized;
	netctl_t ctl;

	/* Stored params for reconnection */
	char ssid[33];
	char psk[65];
	/* atomic_t: written from API thread, read from reconnect_work callback */
	atomic_t auto_reconnect;

	/* Callbacks */
	struct {
		icle_wifi_callback_t callback;
		void *user_data;
	} callbacks[4];

	/* Reconnection work */
	struct k_work_delayable reconnect_work;
	uint32_t reconnect_delay_ms;
	uint32_t reconnect_count;
} ctx;

#define RECONNECT_BASE_MS  1000
#define RECONNECT_MAX_MS   60000

/* Forward declarations */
static void netctl_event_cb(const netctl_event_t *event, void *user_data);
static void reconnect_work_handler(struct k_work *work);

/*
 * Notify all registered icle_wifi callbacks
 */
static void notify_callbacks(bool connected)
{
	for (int i = 0; i < ARRAY_SIZE(ctx.callbacks); i++) {
		if (ctx.callbacks[i].callback != NULL) {
			ctx.callbacks[i].callback(connected, ctx.callbacks[i].user_data);
		}
	}
}

/*
 * netctl event callback - bridges netctl events to icle_wifi callbacks
 * and posts app events for the state machine event loop.
 */
static void netctl_event_cb(const netctl_event_t *event, void *user_data)
{
	ARG_UNUSED(user_data);

	switch (event->type) {
	case NETCTL_EVENT_CONNECTED:
		LOG_INF("netctl: connected");
		ctx.reconnect_delay_ms = RECONNECT_BASE_MS;
		ctx.reconnect_count = 0;
		notify_callbacks(true);
		icle_events_post(ICLE_EVENT_WIFI_CONNECTED);
		break;

	case NETCTL_EVENT_DISCONNECTED:
		LOG_INF("netctl: disconnected");
		notify_callbacks(false);
		icle_events_post(ICLE_EVENT_WIFI_DISCONNECTED);

		/* Auto-reconnect if enabled */
		if (atomic_get(&ctx.auto_reconnect) && ctx.ssid[0] != '\0') {
			LOG_INF("Scheduling reconnection in %u ms", ctx.reconnect_delay_ms);
			k_work_schedule(&ctx.reconnect_work,
					K_MSEC(ctx.reconnect_delay_ms));
			ctx.reconnect_delay_ms = MIN(ctx.reconnect_delay_ms * 2,
						     RECONNECT_MAX_MS);
		}
		break;

	case NETCTL_EVENT_CONNECTION_FAILED:
		LOG_WRN("netctl: connection failed (err=%d)",
			event->data.error.error_code);
		notify_callbacks(false);
		icle_events_post(ICLE_EVENT_WIFI_CONNECT_FAILED);

		/* Auto-reconnect if enabled */
		if (atomic_get(&ctx.auto_reconnect) && ctx.ssid[0] != '\0') {
			/* Reset from ERROR state so we can retry */
			netctl_reset(&ctx.ctl, NETCTL_IFACE_WIFI_STA);
			LOG_INF("Scheduling reconnection in %u ms", ctx.reconnect_delay_ms);
			k_work_schedule(&ctx.reconnect_work,
					K_MSEC(ctx.reconnect_delay_ms));
			ctx.reconnect_delay_ms = MIN(ctx.reconnect_delay_ms * 2,
						     RECONNECT_MAX_MS);
		}
		break;

	case NETCTL_EVENT_IP_ACQUIRED:
		LOG_INF("netctl: IP acquired: %s (gw: %s)",
			event->data.ip_acquired.ip_addr,
			event->data.ip_acquired.gateway);
		icle_events_post(ICLE_EVENT_WIFI_IP_ACQUIRED);
		break;

	default:
		break;
	}
}

/*
 * Reconnection work handler
 */
static void reconnect_work_handler(struct k_work *work)
{
	netctl_state_t state;
	netctl_profile_t profile;
	int ret;

	ARG_UNUSED(work);

	if (!ctx.initialized || !atomic_get(&ctx.auto_reconnect) ||
	    ctx.ssid[0] == '\0')
		return;

	if (netctl_is_online(&ctx.ctl))
		return;

	state = netctl_get_state(&ctx.ctl, NETCTL_IFACE_WIFI_STA);
	if (state == NETCTL_STATE_CONNECTING)
		return;

	/* Reset from error state if needed */
	if (state == NETCTL_STATE_ERROR)
		netctl_reset(&ctx.ctl, NETCTL_IFACE_WIFI_STA);

	LOG_INF("Attempting WiFi reconnection (attempt %u)", ++ctx.reconnect_count);

	memset(&profile, 0, sizeof(profile));
	profile.iface = NETCTL_IFACE_WIFI_STA;
	profile.priority = 0;
	strncpy(profile.name, WIFI_PROFILE_NAME, sizeof(profile.name) - 1);
	strncpy(profile.credentials.wifi.ssid, ctx.ssid,
		sizeof(profile.credentials.wifi.ssid) - 1);
	strncpy(profile.credentials.wifi.password, ctx.psk,
		sizeof(profile.credentials.wifi.password) - 1);

	ret = netctl_connect_with_creds(&ctx.ctl, &profile);
	if (ret < 0 && ret != -EBUSY) {
		LOG_ERR("Reconnection failed: %d", ret);
		/* netctl_event_cb will handle scheduling the next retry */
	}
}

/*
 * Public API
 */

int icle_wifi_init(void)
{
	int ret;

	if (ctx.initialized)
		return 0;

	memset(&ctx, 0, sizeof(ctx));

	/* Initialize reconnection work */
	k_work_init_delayable(&ctx.reconnect_work, reconnect_work_handler);
	ctx.reconnect_delay_ms = RECONNECT_BASE_MS;

	/* Initialize netctl */
	ret = netctl_init(&ctx.ctl, netctl_event_cb, NULL);
	if (ret < 0) {
		LOG_ERR("netctl init failed: %d", ret);
		return ret;
	}

	ctx.initialized = true;
	LOG_INF("WiFi subsystem initialized (via netctl)");
	return 0;
}

int icle_wifi_deinit(void)
{
	if (!ctx.initialized)
		return -ENODEV;

	k_work_cancel_delayable(&ctx.reconnect_work);

	netctl_deinit(&ctx.ctl);

	ctx.initialized = false;
	LOG_INF("WiFi subsystem deinitialized");
	return 0;
}

int icle_wifi_connect(const struct icle_wifi_params *params)
{
	netctl_profile_t profile;

	if (!ctx.initialized)
		return -ENODEV;

	if (params == NULL || params->ssid == NULL || strlen(params->ssid) == 0)
		return -EINVAL;

	/* Store connection parameters for reconnection */
	strncpy(ctx.ssid, params->ssid, sizeof(ctx.ssid) - 1);
	ctx.ssid[sizeof(ctx.ssid) - 1] = '\0';

	if (params->psk != NULL) {
		strncpy(ctx.psk, params->psk, sizeof(ctx.psk) - 1);
		ctx.psk[sizeof(ctx.psk) - 1] = '\0';
	} else {
		ctx.psk[0] = '\0';
	}

	atomic_set(&ctx.auto_reconnect, params->auto_reconnect ? 1 : 0);
	ctx.reconnect_delay_ms = RECONNECT_BASE_MS;

	/* Build a netctl profile and connect */
	memset(&profile, 0, sizeof(profile));
	profile.iface = NETCTL_IFACE_WIFI_STA;
	profile.priority = 0;
	strncpy(profile.name, WIFI_PROFILE_NAME, sizeof(profile.name) - 1);
	strncpy(profile.credentials.wifi.ssid, ctx.ssid,
		sizeof(profile.credentials.wifi.ssid) - 1);
	strncpy(profile.credentials.wifi.password, ctx.psk,
		sizeof(profile.credentials.wifi.password) - 1);

	LOG_INF("Connecting to WiFi SSID: %s (via netctl)", ctx.ssid);

	return netctl_connect_with_creds(&ctx.ctl, &profile);
}

int icle_wifi_connect_simple(const char *ssid, const char *psk,
			     uint32_t timeout_ms)
{
	struct icle_wifi_params params = {
		.ssid = ssid,
		.psk = psk,
		.timeout_ms = timeout_ms,
		.auto_reconnect = true,
	};

	return icle_wifi_connect(&params);
}

int icle_wifi_wait_connected(uint32_t timeout_ms)
{
	ARG_UNUSED(timeout_ms);

	if (!ctx.initialized)
		return -ENODEV;

	/*
	 * Async architecture - no blocking waits.
	 * Just return current state. Callers should use
	 * ICLE_EVENT_WIFI_IP_ACQUIRED event instead.
	 */
	if (netctl_is_online(&ctx.ctl))
		return 0;

	return -ENOTCONN;
}

int icle_wifi_disconnect(void)
{
	if (!ctx.initialized)
		return -ENODEV;

	k_work_cancel_delayable(&ctx.reconnect_work);
	atomic_clear(&ctx.auto_reconnect);

	return netctl_disconnect(&ctx.ctl, NETCTL_IFACE_WIFI_STA);
}

bool icle_wifi_is_connected(void)
{
	if (!ctx.initialized)
		return false;

	return netctl_is_online(&ctx.ctl);
}

enum icle_wifi_state icle_wifi_get_state(void)
{
	netctl_state_t state;

	if (!ctx.initialized)
		return ICLE_WIFI_STATE_DISABLED;

	state = netctl_get_state(&ctx.ctl, NETCTL_IFACE_WIFI_STA);

	switch (state) {
	case NETCTL_STATE_DISABLED:
		return ICLE_WIFI_STATE_DISABLED;
	case NETCTL_STATE_IDLE:
		return ICLE_WIFI_STATE_DISCONNECTED;
	case NETCTL_STATE_CONNECTING:
		return ICLE_WIFI_STATE_CONNECTING;
	case NETCTL_STATE_CONNECTED:
		return ICLE_WIFI_STATE_CONNECTED;
	case NETCTL_STATE_DISCONNECTING:
		return ICLE_WIFI_STATE_DISCONNECTED;
	case NETCTL_STATE_ERROR:
		return ICLE_WIFI_STATE_ERROR;
	default:
		return ICLE_WIFI_STATE_DISABLED;
	}
}

int icle_wifi_get_status(struct icle_wifi_status *status)
{
	if (!ctx.initialized || status == NULL)
		return -EINVAL;

	memset(status, 0, sizeof(*status));
	status->state = icle_wifi_get_state();
	strncpy(status->ssid, ctx.ssid, sizeof(status->ssid) - 1);
	status->reconnect_count = ctx.reconnect_count;

	return 0;
}

int icle_wifi_register_callback(icle_wifi_callback_t callback, void *user_data)
{
	if (callback == NULL)
		return -EINVAL;

	for (int i = 0; i < ARRAY_SIZE(ctx.callbacks); i++) {
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
	if (callback == NULL)
		return;

	for (int i = 0; i < ARRAY_SIZE(ctx.callbacks); i++) {
		if (ctx.callbacks[i].callback == callback) {
			ctx.callbacks[i].callback = NULL;
			ctx.callbacks[i].user_data = NULL;
			return;
		}
	}
}

void icle_wifi_set_auto_reconnect(bool enable)
{
	atomic_set(&ctx.auto_reconnect, enable ? 1 : 0);

	if (!enable)
		k_work_cancel_delayable(&ctx.reconnect_work);

	LOG_INF("Auto-reconnect %s", enable ? "enabled" : "disabled");
}

struct net_if *icle_wifi_get_iface(void)
{
	if (!ctx.initialized)
		return NULL;

#ifdef CONFIG_ICLE_NETCTL_WIFI
	return ctx.ctl.wifi_iface;
#else
	return NULL;
#endif
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

	if (state < ARRAY_SIZE(state_names))
		return state_names[state];

	return "unknown";
}
