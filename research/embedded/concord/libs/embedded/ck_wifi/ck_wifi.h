/*
 * SPDX-License-Identifier: Apache-2.0
 * CoreKinect WiFi Library
 */

#ifndef CK_WIFI_H_
#define CK_WIFI_H_

#include <zephyr/kernel.h>
#include <zephyr/net/net_if.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief WiFi connection status
 */
enum ck_wifi_status {
	CK_WIFI_STATUS_DISCONNECTED = 0,
	CK_WIFI_STATUS_CONNECTING,
	CK_WIFI_STATUS_CONNECTED,
	CK_WIFI_STATUS_ERROR,
};

/**
 * @brief WiFi connection callback
 *
 * @param status Connection status
 * @param user_data User data passed to ck_wifi_connect
 */
typedef void (*ck_wifi_callback_t)(enum ck_wifi_status status, void *user_data);

/**
 * @brief Initialize the WiFi subsystem
 *
 * @return 0 on success, negative errno on failure
 */
int ck_wifi_init(void);

/**
 * @brief Connect to a WiFi network
 *
 * Uses CONFIG_CK_WIFI_SSID and CONFIG_CK_WIFI_PSK if ssid/psk are NULL.
 *
 * @param ssid Network SSID (NULL to use Kconfig)
 * @param psk Network password (NULL to use Kconfig)
 * @param callback Optional callback for connection events
 * @param user_data User data passed to callback
 * @return 0 on success, negative errno on failure
 */
int ck_wifi_connect(const char *ssid, const char *psk,
		    ck_wifi_callback_t callback, void *user_data);

/**
 * @brief Disconnect from WiFi network
 *
 * @return 0 on success, negative errno on failure
 */
int ck_wifi_disconnect(void);

/**
 * @brief Get current WiFi status
 *
 * @return Current WiFi status
 */
enum ck_wifi_status ck_wifi_get_status(void);

/**
 * @brief Wait for WiFi connection (blocking)
 *
 * @param timeout_ms Timeout in milliseconds (K_FOREVER for infinite)
 * @return 0 if connected, -ETIMEDOUT on timeout, other negative errno on error
 */
int ck_wifi_wait_connected(k_timeout_t timeout);

/**
 * @brief Get the WiFi network interface
 *
 * @return Network interface pointer, or NULL if not initialized
 */
struct net_if *ck_wifi_get_iface(void);

#ifdef __cplusplus
}
#endif

#endif /* CK_WIFI_H_ */
