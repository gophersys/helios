/*
 * ICLE Network Control Service - Core Implementation
 *
 * Ported from Helios runtime netctl module.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "netctl.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <errno.h>
#include <string.h>

#include "netctl_internal.h"
#include "arbiter.h"

#ifndef CONFIG_ICLE_NETCTL_LOG_LEVEL
#define CONFIG_ICLE_NETCTL_LOG_LEVEL 3
#endif

#ifndef CONFIG_ICLE_NETCTL_THREAD_PRIORITY
#define CONFIG_ICLE_NETCTL_THREAD_PRIORITY 8
#endif

LOG_MODULE_REGISTER(netctl, CONFIG_ICLE_NETCTL_LOG_LEVEL);

/*
 * Internal helpers
 */

static void netctl_emit_event(netctl_t *ctl, const netctl_event_t *event)
{
	for (uint8_t i = 0; i < ctl->subscriber_count; i++) {
		if (ctl->subscribers[i].cb != NULL) {
			ctl->subscribers[i].cb(event, ctl->subscribers[i].user_data);
		}
	}
}

static void netctl_set_state(netctl_t *ctl, netctl_iface_t iface, netctl_state_t new_state)
{
	if (iface >= NETCTL_IFACE_MAX) {
		return;
	}

	netctl_state_t old_state = ctl->iface_state[iface];
	if (old_state == new_state) {
		return;
	}

	ctl->iface_state[iface] = new_state;

	LOG_DBG("Interface %d: %d -> %d", iface, old_state, new_state);

	netctl_event_t event = {
		.type = NETCTL_EVENT_STATE_CHANGED,
		.data.state_changed = {
			.iface = iface,
			.old_state = old_state,
			.new_state = new_state,
		},
	};
	netctl_emit_event(ctl, &event);
}

/*
 * Event thread
 */

static void netctl_thread_entry(void *p1, void *p2, void *p3)
{
	netctl_t *ctl = (netctl_t *)p1;
	netctl_event_t event;

	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	LOG_DBG("Event thread started");

	while (true) {
		int ret = k_msgq_get(&ctl->event_queue, &event, K_FOREVER);
		if (ret == 0) {
			netctl_emit_event(ctl, &event);
		}
	}
}

/*
 * Public API - Lifecycle
 */

int netctl_init(netctl_t *ctl, netctl_event_cb_t cb, void *user_data)
{
	if (ctl == NULL) {
		return -EINVAL;
	}

	if (ctl->initialized) {
		LOG_WRN("Already initialized");
		return -EALREADY;
	}

	memset(ctl, 0, sizeof(*ctl));

	/* Register initial callback as first subscriber */
	if (cb != NULL) {
		ctl->subscribers[0].cb = cb;
		ctl->subscribers[0].user_data = user_data;
		ctl->subscriber_count = 1;
	}

	/* Initialize all interfaces to disabled */
	for (int i = 0; i < NETCTL_IFACE_MAX; i++) {
		ctl->iface_state[i] = NETCTL_STATE_DISABLED;
	}

	/* Initialize synchronization primitives */
	k_mutex_init(&ctl->lock);

	/* Initialize event queue */
	k_msgq_init(&ctl->event_queue, ctl->event_queue_buf,
		    sizeof(netctl_event_t), CONFIG_ICLE_NETCTL_EVENT_QUEUE_SIZE);

	/* Start event processing thread */
	ctl->thread_id = k_thread_create(
		&ctl->thread,
		ctl->thread_stack,
		K_KERNEL_STACK_SIZEOF(ctl->thread_stack),
		netctl_thread_entry,
		ctl, NULL, NULL,
		CONFIG_ICLE_NETCTL_THREAD_PRIORITY,
		0,
		K_NO_WAIT);

	(void)k_thread_name_set(ctl->thread_id, "netctl");

	/* Initialize interface-specific subsystems */
#ifdef CONFIG_ICLE_NETCTL_WIFI
	int ret = netctl_wifi_init(ctl);
	if (ret < 0) {
		LOG_ERR("WiFi init failed: %d", ret);
	} else {
		ctl->iface_state[NETCTL_IFACE_WIFI_STA] = NETCTL_STATE_IDLE;
		LOG_INF("WiFi initialized");
	}
#endif

	ctl->initialized = true;
	LOG_INF("Network control service initialized");

	return 0;
}

int netctl_deinit(netctl_t *ctl)
{
	if (ctl == NULL || !ctl->initialized) {
		return -EINVAL;
	}

	/* Disconnect all interfaces */
	netctl_disconnect_all(ctl);

#ifdef CONFIG_ICLE_NETCTL_WIFI
	netctl_wifi_deinit(ctl);
#endif

	/* Abort event thread */
	k_thread_abort(ctl->thread_id);

	ctl->initialized = false;
	LOG_INF("Network control service deinitialized");

	return 0;
}

/*
 * Public API - Connection Control
 */

int netctl_connect(netctl_t *ctl, const char *profile_name)
{
	if (ctl == NULL || !ctl->initialized || profile_name == NULL) {
		return -EINVAL;
	}

	const netctl_profile_t *profile = netctl_profile_get(ctl, profile_name);
	if (profile == NULL) {
		LOG_WRN("Profile not found: %s", profile_name);
		return -ENOENT;
	}

	return netctl_connect_with_creds(ctl, profile);
}

int netctl_connect_with_creds(netctl_t *ctl, const netctl_profile_t *profile)
{
	if (ctl == NULL || !ctl->initialized || profile == NULL) {
		return -EINVAL;
	}

	int ret = -ENOTSUP;

	k_mutex_lock(&ctl->lock, K_FOREVER);

	switch (profile->iface) {
#ifdef CONFIG_ICLE_NETCTL_WIFI
	case NETCTL_IFACE_WIFI_STA:
		/* Check if already busy */
		if (ctl->iface_state[NETCTL_IFACE_WIFI_STA] == NETCTL_STATE_CONNECTING ||
		    ctl->iface_state[NETCTL_IFACE_WIFI_STA] == NETCTL_STATE_CONNECTED) {
			ret = -EBUSY;
			break;
		}
		/* Check arbiter */
		ret = netctl_arbiter_can_activate_wifi(ctl);
		if (ret < 0) {
			break;
		}
		netctl_set_state(ctl, NETCTL_IFACE_WIFI_STA, NETCTL_STATE_CONNECTING);
		ctl->active_profile = profile;
		k_mutex_unlock(&ctl->lock);

		ret = netctl_wifi_connect(ctl, &profile->credentials.wifi);

		k_mutex_lock(&ctl->lock, K_FOREVER);
		if (ret < 0) {
			netctl_set_state(ctl, NETCTL_IFACE_WIFI_STA, NETCTL_STATE_ERROR);
			ctl->active_profile = NULL;
		}
		k_mutex_unlock(&ctl->lock);
		return ret;
#endif

	default:
		ret = -EINVAL;
		break;
	}

	k_mutex_unlock(&ctl->lock);
	return ret;
}

int netctl_disconnect(netctl_t *ctl, netctl_iface_t iface)
{
	if (ctl == NULL || !ctl->initialized || iface >= NETCTL_IFACE_MAX) {
		return -EINVAL;
	}

	int ret = -ENOTSUP;

	k_mutex_lock(&ctl->lock, K_FOREVER);

	netctl_state_t state = ctl->iface_state[iface];
	if (state != NETCTL_STATE_CONNECTED && state != NETCTL_STATE_CONNECTING) {
		k_mutex_unlock(&ctl->lock);
		return -EALREADY;
	}

	switch (iface) {
#ifdef CONFIG_ICLE_NETCTL_WIFI
	case NETCTL_IFACE_WIFI_STA:
		netctl_set_state(ctl, NETCTL_IFACE_WIFI_STA, NETCTL_STATE_DISCONNECTING);
		k_mutex_unlock(&ctl->lock);

		ret = netctl_wifi_disconnect(ctl);

		k_mutex_lock(&ctl->lock, K_FOREVER);
		if (ret < 0) {
			netctl_set_state(ctl, NETCTL_IFACE_WIFI_STA, NETCTL_STATE_ERROR);
		}
		k_mutex_unlock(&ctl->lock);
		return ret;
#endif

	default:
		ret = -ENOTSUP;
		break;
	}

	k_mutex_unlock(&ctl->lock);
	return ret;
}

int netctl_disconnect_all(netctl_t *ctl)
{
	if (ctl == NULL || !ctl->initialized) {
		return -EINVAL;
	}

	for (int i = 0; i < NETCTL_IFACE_MAX; i++) {
		if (ctl->iface_state[i] == NETCTL_STATE_CONNECTED ||
		    ctl->iface_state[i] == NETCTL_STATE_CONNECTING) {
			int ret = netctl_disconnect(ctl, (netctl_iface_t)i);
			if (ret < 0 && ret != -EALREADY) {
				LOG_WRN("Failed to disconnect iface %d: %d", i, ret);
			}
		}
	}

	return 0;
}

int netctl_reset(netctl_t *ctl, netctl_iface_t iface)
{
	if (ctl == NULL || !ctl->initialized || iface >= NETCTL_IFACE_MAX) {
		return -EINVAL;
	}

	k_mutex_lock(&ctl->lock, K_FOREVER);

	if (ctl->iface_state[iface] != NETCTL_STATE_ERROR) {
		k_mutex_unlock(&ctl->lock);
		return -EALREADY;
	}

	netctl_set_state(ctl, iface, NETCTL_STATE_IDLE);
	ctl->active_profile = NULL;

	k_mutex_unlock(&ctl->lock);

	LOG_INF("Interface %d reset to IDLE", iface);
	return 0;
}

/*
 * Public API - State Query
 */

netctl_state_t netctl_get_state(netctl_t *ctl, netctl_iface_t iface)
{
	if (ctl == NULL || !ctl->initialized || iface >= NETCTL_IFACE_MAX) {
		return NETCTL_STATE_DISABLED;
	}

	return ctl->iface_state[iface];
}

bool netctl_is_online(netctl_t *ctl)
{
	if (ctl == NULL || !ctl->initialized) {
		return false;
	}

	for (int i = 0; i < NETCTL_IFACE_MAX; i++) {
		if (ctl->iface_state[i] == NETCTL_STATE_CONNECTED) {
			return true;
		}
	}

	return false;
}

netctl_iface_t netctl_get_active_iface(netctl_t *ctl)
{
	if (ctl == NULL || !ctl->initialized) {
		return NETCTL_IFACE_MAX;
	}

	for (int i = 0; i < NETCTL_IFACE_MAX; i++) {
		if (ctl->iface_state[i] == NETCTL_STATE_CONNECTED) {
			return (netctl_iface_t)i;
		}
	}

	return NETCTL_IFACE_MAX;
}

const netctl_profile_t *netctl_get_active_profile(netctl_t *ctl)
{
	if (ctl == NULL || !ctl->initialized) {
		return NULL;
	}

	return ctl->active_profile;
}

/*
 * Public API - High-Level Convenience
 */

int netctl_request_internet(netctl_t *ctl)
{
	if (ctl == NULL || !ctl->initialized) {
		return -EINVAL;
	}

	if (ctl->profile_count == 0) {
		LOG_WRN("No profiles registered");
		return -ENOENT;
	}

	/* Find highest priority (lowest number) profile */
	const netctl_profile_t *best = NULL;
	uint8_t best_priority = UINT8_MAX;

	for (int i = 0; i < ctl->profile_count; i++) {
		if (ctl->profiles[i].priority < best_priority) {
			best_priority = ctl->profiles[i].priority;
			best = &ctl->profiles[i];
		}
	}

	if (best == NULL) {
		return -ENOENT;
	}

	return netctl_connect_with_creds(ctl, best);
}

/*
 * Public API - Event Subscription
 */

int netctl_subscribe(netctl_t *ctl, netctl_event_cb_t cb, void *user_data)
{
	if (ctl == NULL || cb == NULL) {
		return -EINVAL;
	}

	k_mutex_lock(&ctl->lock, K_FOREVER);

	if (ctl->subscriber_count >= CONFIG_ICLE_NETCTL_MAX_SUBSCRIBERS) {
		k_mutex_unlock(&ctl->lock);
		return -ENOMEM;
	}

	/* Check for duplicate */
	for (uint8_t i = 0; i < ctl->subscriber_count; i++) {
		if (ctl->subscribers[i].cb == cb) {
			k_mutex_unlock(&ctl->lock);
			return -EALREADY;
		}
	}

	ctl->subscribers[ctl->subscriber_count].cb = cb;
	ctl->subscribers[ctl->subscriber_count].user_data = user_data;
	ctl->subscriber_count++;

	k_mutex_unlock(&ctl->lock);
	return 0;
}

int netctl_unsubscribe(netctl_t *ctl, netctl_event_cb_t cb)
{
	if (ctl == NULL || cb == NULL) {
		return -EINVAL;
	}

	k_mutex_lock(&ctl->lock, K_FOREVER);

	for (uint8_t i = 0; i < ctl->subscriber_count; i++) {
		if (ctl->subscribers[i].cb == cb) {
			/* Shift remaining subscribers down */
			for (uint8_t j = i; j < ctl->subscriber_count - 1; j++) {
				ctl->subscribers[j] = ctl->subscribers[j + 1];
			}
			ctl->subscriber_count--;
			memset(&ctl->subscribers[ctl->subscriber_count], 0,
			       sizeof(netctl_subscriber_t));
			k_mutex_unlock(&ctl->lock);
			return 0;
		}
	}

	k_mutex_unlock(&ctl->lock);
	return -ENOENT;
}

/*
 * Internal API - Called by interface implementations
 */

void netctl_notify_connected(netctl_t *ctl, netctl_iface_t iface)
{
	k_mutex_lock(&ctl->lock, K_FOREVER);
	netctl_set_state(ctl, iface, NETCTL_STATE_CONNECTED);
	k_mutex_unlock(&ctl->lock);

	netctl_event_t event = {
		.type = NETCTL_EVENT_CONNECTED,
		.data.state_changed = {
			.iface = iface,
			.old_state = NETCTL_STATE_CONNECTING,
			.new_state = NETCTL_STATE_CONNECTED,
		},
	};
	if (k_msgq_put(&ctl->event_queue, &event, K_NO_WAIT) != 0) {
		LOG_WRN("Event queue full, dropped event type %d", event.type);
	}
}

void netctl_notify_disconnected(netctl_t *ctl, netctl_iface_t iface)
{
	k_mutex_lock(&ctl->lock, K_FOREVER);
	netctl_set_state(ctl, iface, NETCTL_STATE_IDLE);
	ctl->active_profile = NULL;
	k_mutex_unlock(&ctl->lock);

	netctl_event_t event = {
		.type = NETCTL_EVENT_DISCONNECTED,
		.data.state_changed = {
			.iface = iface,
			.old_state = NETCTL_STATE_CONNECTED,
			.new_state = NETCTL_STATE_IDLE,
		},
	};
	if (k_msgq_put(&ctl->event_queue, &event, K_NO_WAIT) != 0) {
		LOG_WRN("Event queue full, dropped event type %d", event.type);
	}
}

void netctl_notify_connection_failed(netctl_t *ctl, netctl_iface_t iface, int error_code)
{
	k_mutex_lock(&ctl->lock, K_FOREVER);
	netctl_set_state(ctl, iface, NETCTL_STATE_ERROR);
	ctl->active_profile = NULL;
	k_mutex_unlock(&ctl->lock);

	netctl_event_t event = {
		.type = NETCTL_EVENT_CONNECTION_FAILED,
		.data.error = {
			.iface = iface,
			.error_code = error_code,
			.message = NULL,
		},
	};
	if (k_msgq_put(&ctl->event_queue, &event, K_NO_WAIT) != 0) {
		LOG_WRN("Event queue full, dropped event type %d", event.type);
	}
}

void netctl_notify_ip_acquired(netctl_t *ctl, netctl_iface_t iface,
			       const char *ip_addr, const char *gateway, const char *netmask)
{
	if (ctl == NULL || ip_addr == NULL || gateway == NULL || netmask == NULL) {
		return;
	}

	netctl_event_t event = {
		.type = NETCTL_EVENT_IP_ACQUIRED,
	};

	event.data.ip_acquired.iface = iface;
	strncpy(event.data.ip_acquired.ip_addr, ip_addr, NETCTL_IPV4_ADDR_LEN - 1);
	event.data.ip_acquired.ip_addr[NETCTL_IPV4_ADDR_LEN - 1] = '\0';
	strncpy(event.data.ip_acquired.gateway, gateway, NETCTL_IPV4_ADDR_LEN - 1);
	event.data.ip_acquired.gateway[NETCTL_IPV4_ADDR_LEN - 1] = '\0';
	strncpy(event.data.ip_acquired.netmask, netmask, NETCTL_IPV4_ADDR_LEN - 1);
	event.data.ip_acquired.netmask[NETCTL_IPV4_ADDR_LEN - 1] = '\0';

	if (k_msgq_put(&ctl->event_queue, &event, K_NO_WAIT) != 0) {
		LOG_WRN("Event queue full, dropped event type %d", event.type);
	}
}
