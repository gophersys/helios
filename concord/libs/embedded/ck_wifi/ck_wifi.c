/*
 * SPDX-License-Identifier: Apache-2.0
 * CoreKinect WiFi Library
 */

#include "ck_wifi.h"

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(ck_wifi, CONFIG_CK_WIFI_LOG_LEVEL);

#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/net_event.h>
#include <string.h>

static struct net_mgmt_event_callback wifi_mgmt_cb;
static struct net_mgmt_event_callback net_mgmt_cb;
static enum ck_wifi_status current_status = CK_WIFI_STATUS_DISCONNECTED;
static ck_wifi_callback_t user_callback;
static void *user_callback_data;
static struct k_sem wifi_connected_sem;
static bool initialized;

static void handle_wifi_connect_result(struct net_mgmt_event_callback *cb)
{
	const struct wifi_status *status = (const struct wifi_status *)cb->info;

	if (status->status) {
		LOG_ERR("WiFi connection failed: %d", status->status);
		current_status = CK_WIFI_STATUS_ERROR;
	} else {
		LOG_INF("WiFi connected");
		current_status = CK_WIFI_STATUS_CONNECTED;
		k_sem_give(&wifi_connected_sem);
	}

	if (user_callback) {
		user_callback(current_status, user_callback_data);
	}
}

static void handle_wifi_disconnect_result(struct net_mgmt_event_callback *cb)
{
	const struct wifi_status *status = (const struct wifi_status *)cb->info;

	if (status->status) {
		LOG_WRN("WiFi disconnect status: %d", status->status);
	}

	LOG_INF("WiFi disconnected");
	current_status = CK_WIFI_STATUS_DISCONNECTED;

	if (user_callback) {
		user_callback(current_status, user_callback_data);
	}
}

static void wifi_mgmt_event_handler(struct net_mgmt_event_callback *cb,
				    uint32_t mgmt_event, struct net_if *iface)
{
	switch (mgmt_event) {
	case NET_EVENT_WIFI_CONNECT_RESULT:
		handle_wifi_connect_result(cb);
		break;
	case NET_EVENT_WIFI_DISCONNECT_RESULT:
		handle_wifi_disconnect_result(cb);
		break;
	default:
		break;
	}
}

static void net_mgmt_event_handler(struct net_mgmt_event_callback *cb,
				   uint32_t mgmt_event, struct net_if *iface)
{
	if (mgmt_event == NET_EVENT_IPV4_ADDR_ADD) {
		char buf[NET_IPV4_ADDR_LEN];
		struct net_if_config *cfg = net_if_get_config(iface);

		for (int i = 0; i < NET_IF_MAX_IPV4_ADDR; i++) {
			if (cfg->ip.ipv4->unicast[i].ipv4.addr_type == NET_ADDR_DHCP) {
				LOG_INF("DHCP IP: %s",
					net_addr_ntop(AF_INET,
						      &cfg->ip.ipv4->unicast[i].ipv4.address.in_addr,
						      buf, sizeof(buf)));
				break;
			}
		}
	}
}

int ck_wifi_init(void)
{
	if (initialized) {
		return 0;
	}

	k_sem_init(&wifi_connected_sem, 0, 1);

	net_mgmt_init_event_callback(&wifi_mgmt_cb,
				     wifi_mgmt_event_handler,
				     NET_EVENT_WIFI_CONNECT_RESULT |
				     NET_EVENT_WIFI_DISCONNECT_RESULT);
	net_mgmt_add_event_callback(&wifi_mgmt_cb);

	net_mgmt_init_event_callback(&net_mgmt_cb,
				     net_mgmt_event_handler,
				     NET_EVENT_IPV4_ADDR_ADD);
	net_mgmt_add_event_callback(&net_mgmt_cb);

	initialized = true;
	LOG_INF("WiFi library initialized");
	return 0;
}

int ck_wifi_connect(const char *ssid, const char *psk,
		    ck_wifi_callback_t callback, void *user_data)
{
	struct net_if *iface;
	struct wifi_connect_req_params cnx_params = {0};
	int ret;
	int retries = 10;

	if (!initialized) {
		ret = ck_wifi_init();
		if (ret < 0) {
			return ret;
		}
	}

	/* Use Kconfig values if not provided */
	if (ssid == NULL) {
		ssid = CONFIG_CK_WIFI_SSID;
	}
	if (psk == NULL) {
		psk = CONFIG_CK_WIFI_PSK;
	}

	if (strlen(ssid) == 0) {
		LOG_ERR("WiFi SSID not configured");
		return -EINVAL;
	}

	user_callback = callback;
	user_callback_data = user_data;

	iface = net_if_get_default();
	if (!iface) {
		LOG_ERR("No network interface found");
		return -ENODEV;
	}

	cnx_params.ssid = (uint8_t *)ssid;
	cnx_params.ssid_length = strlen(ssid);
	cnx_params.psk = (uint8_t *)psk;
	cnx_params.psk_length = strlen(psk);
	cnx_params.channel = WIFI_CHANNEL_ANY;
	cnx_params.security = (strlen(psk) > 0) ? WIFI_SECURITY_TYPE_PSK
						: WIFI_SECURITY_TYPE_NONE;
	cnx_params.mfp = WIFI_MFP_OPTIONAL;

	k_sem_reset(&wifi_connected_sem);
	current_status = CK_WIFI_STATUS_CONNECTING;

	LOG_INF("Connecting to WiFi SSID: %s", ssid);

	/* Retry connection in case interface isn't ready */
	while (retries-- > 0) {
		ret = net_mgmt(NET_REQUEST_WIFI_CONNECT, iface, &cnx_params,
			       sizeof(struct wifi_connect_req_params));
		if (ret == 0) {
			break;
		}

		LOG_WRN("Connect request failed: %d, retrying...", ret);
		k_msleep(500);
	}

	if (ret != 0) {
		LOG_ERR("Failed to initiate WiFi connection: %d", ret);
		current_status = CK_WIFI_STATUS_ERROR;
		return ret;
	}

	return 0;
}

int ck_wifi_disconnect(void)
{
	struct net_if *iface;
	int ret;

	if (!initialized) {
		return -ENODEV;
	}

	iface = net_if_get_default();
	if (!iface) {
		return -ENODEV;
	}

	ret = net_mgmt(NET_REQUEST_WIFI_DISCONNECT, iface, NULL, 0);
	if (ret) {
		LOG_ERR("Disconnect request failed: %d", ret);
		return ret;
	}

	return 0;
}

enum ck_wifi_status ck_wifi_get_status(void)
{
	return current_status;
}

int ck_wifi_wait_connected(k_timeout_t timeout)
{
	if (current_status == CK_WIFI_STATUS_CONNECTED) {
		return 0;
	}

	if (current_status == CK_WIFI_STATUS_ERROR) {
		return -EIO;
	}

	int ret = k_sem_take(&wifi_connected_sem, timeout);
	if (ret == -EAGAIN) {
		return -ETIMEDOUT;
	}

	return (current_status == CK_WIFI_STATUS_CONNECTED) ? 0 : -EIO;
}

struct net_if *ck_wifi_get_iface(void)
{
	if (!initialized) {
		return NULL;
	}
	return net_if_get_default();
}
