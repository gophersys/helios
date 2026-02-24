/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE WiFi Station Manager
 *
 * Manages WiFi STA connection, reconnection, and status.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#ifndef ICLE_WIFI_H_
#define ICLE_WIFI_H_

#include <zephyr/kernel.h>
#include <zephyr/net/net_if.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief WiFi connection state
 */
enum icle_wifi_state {
	ICLE_WIFI_STATE_DISABLED,    /* WiFi not initialized */
	ICLE_WIFI_STATE_DISCONNECTED,/* Initialized but not connected */
	ICLE_WIFI_STATE_CONNECTING,  /* Connection in progress */
	ICLE_WIFI_STATE_CONNECTED,   /* Connected to AP */
	ICLE_WIFI_STATE_ERROR,       /* Error state */
};

/**
 * @brief WiFi connection callback type
 *
 * @param connected true if connected, false if disconnected
 * @param user_data User-provided context
 */
typedef void (*icle_wifi_callback_t)(bool connected, void *user_data);

/**
 * @brief WiFi connection parameters
 */
struct icle_wifi_params {
	const char *ssid;
	const char *psk;
	uint32_t timeout_ms;
	bool auto_reconnect;
};

/**
 * @brief WiFi status information
 */
struct icle_wifi_status {
	enum icle_wifi_state state;
	char ssid[33];
	int8_t rssi;
	uint8_t channel;
	uint8_t ip_addr[4];
	uint32_t connected_time_ms;
	uint32_t reconnect_count;
};

/**
 * @brief Initialize WiFi subsystem
 *
 * Must be called before any other WiFi functions.
 * Creates internal synchronization primitives programmatically.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_wifi_init(void);

/**
 * @brief Deinitialize WiFi subsystem
 *
 * Disconnects and releases resources.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_wifi_deinit(void);

/**
 * @brief Connect to WiFi network
 *
 * Initiates connection to specified network. Function returns
 * immediately; use callback or icle_wifi_wait_connected() to
 * wait for result.
 *
 * @param params Connection parameters
 * @return 0 if connection initiated, negative errno on failure
 */
int icle_wifi_connect(const struct icle_wifi_params *params);

/**
 * @brief Connect with SSID/PSK strings (convenience function)
 *
 * @param ssid Network SSID
 * @param psk Network password (NULL or empty for open network)
 * @param timeout_ms Connection timeout in ms
 * @return 0 if connection initiated, negative errno on failure
 */
int icle_wifi_connect_simple(const char *ssid, const char *psk,
			     uint32_t timeout_ms);

/**
 * @brief Wait for WiFi connection
 *
 * Blocks until connected or timeout.
 *
 * @param timeout_ms Maximum wait time, K_FOREVER for indefinite
 * @return 0 if connected, -ETIMEDOUT on timeout, other negative on error
 */
int icle_wifi_wait_connected(uint32_t timeout_ms);

/**
 * @brief Disconnect from WiFi network
 *
 * @return 0 on success, negative errno on failure
 */
int icle_wifi_disconnect(void);

/**
 * @brief Check if WiFi is connected
 *
 * @return true if connected to an AP
 */
bool icle_wifi_is_connected(void);

/**
 * @brief Get current WiFi state
 *
 * @return Current WiFi state
 */
enum icle_wifi_state icle_wifi_get_state(void);

/**
 * @brief Get WiFi status information
 *
 * @param status Pointer to store status info
 * @return 0 on success, negative errno on failure
 */
int icle_wifi_get_status(struct icle_wifi_status *status);

/**
 * @brief Register connection state callback
 *
 * @param callback Callback function
 * @param user_data User context passed to callback
 * @return 0 on success, -ENOMEM if too many callbacks
 */
int icle_wifi_register_callback(icle_wifi_callback_t callback, void *user_data);

/**
 * @brief Unregister connection state callback
 *
 * @param callback Callback to remove
 */
void icle_wifi_unregister_callback(icle_wifi_callback_t callback);

/**
 * @brief Enable/disable auto-reconnect
 *
 * @param enable true to enable auto-reconnect on disconnect
 */
void icle_wifi_set_auto_reconnect(bool enable);

/**
 * @brief Get network interface
 *
 * @return Pointer to WiFi network interface, NULL if not initialized
 */
struct net_if *icle_wifi_get_iface(void);

/**
 * @brief Get WiFi state name string
 *
 * @param state WiFi state
 * @return State name string
 */
const char *icle_wifi_state_name(enum icle_wifi_state state);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_WIFI_H_ */
