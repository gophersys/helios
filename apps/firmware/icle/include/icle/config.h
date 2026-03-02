// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE ZMS-backed Configuration
 *
 * Runtime configuration stored in non-volatile storage using
 * Zephyr's ZMS (Zephyr Memory Storage) subsystem.
 */

#ifndef ICLE_CONFIG_H_
#define ICLE_CONFIG_H_

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief ICLE device configuration (ZMS-backed)
 */
struct icle_config {
	char device_id[32];           /* Unique device identifier */
	char wifi_ssid[33];           /* WiFi network SSID */
	char wifi_psk[65];            /* WiFi password */
	char backend_url[128];        /* Backend API base URL */
	uint32_t sample_interval_ms;  /* Power sampling interval */
	uint32_t heartbeat_interval_ms; /* Backend heartbeat interval */
	uint8_t log_format;           /* 0=binary, 1=csv */
	uint8_t reserved[3];          /* Alignment padding */
};

/* Default configuration values */
#define ICLE_DEFAULT_SAMPLE_INTERVAL_MS    100
#define ICLE_DEFAULT_HEARTBEAT_INTERVAL_MS 60000
#define ICLE_DEFAULT_LOG_FORMAT            1  /* CSV */
#define ICLE_DEFAULT_BACKEND_URL           "http://10.4.45.31:9001"

/**
 * @brief Initialize configuration manager
 *
 * Loads configuration from ZMS if available, otherwise uses defaults.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_config_init(void);

/**
 * @brief Get current configuration
 *
 * @param config Pointer to store configuration
 * @return 0 on success, negative errno on failure
 */
int icle_config_get(struct icle_config *config);

/**
 * @brief Set and save configuration
 *
 * @param config Configuration to save
 * @return 0 on success, negative errno on failure
 */
int icle_config_set(const struct icle_config *config);

/**
 * @brief Reset configuration to defaults
 *
 * @return 0 on success, negative errno on failure
 */
int icle_config_reset(void);

/**
 * @brief Get WiFi SSID
 *
 * @return Pointer to SSID string (static buffer)
 */
const char *icle_config_get_wifi_ssid(void);

/**
 * @brief Get WiFi password
 *
 * @return Pointer to password string (static buffer)
 */
const char *icle_config_get_wifi_psk(void);

/**
 * @brief Set WiFi credentials
 *
 * @param ssid WiFi SSID
 * @param psk WiFi password
 * @return 0 on success, negative errno on failure
 */
int icle_config_set_wifi(const char *ssid, const char *psk);

/**
 * @brief Get device ID
 *
 * @return Pointer to device ID string (static buffer)
 */
const char *icle_config_get_device_id(void);

/**
 * @brief Set device ID
 *
 * @param device_id Device identifier
 * @return 0 on success, negative errno on failure
 */
int icle_config_set_device_id(const char *device_id);

/**
 * @brief Get backend URL
 *
 * @return Pointer to backend URL string (static buffer)
 */
const char *icle_config_get_backend_url(void);

/**
 * @brief Set backend URL
 *
 * @param url Backend API URL
 * @return 0 on success, negative errno on failure
 */
int icle_config_set_backend_url(const char *url);

/**
 * @brief Get sample interval
 *
 * @return Sample interval in milliseconds
 */
uint32_t icle_config_get_sample_interval(void);

/**
 * @brief Set sample interval
 *
 * @param interval_ms Interval in milliseconds
 * @return 0 on success, negative errno on failure
 */
int icle_config_set_sample_interval(uint32_t interval_ms);

/**
 * @brief Get heartbeat interval
 *
 * @return Heartbeat interval in milliseconds
 */
uint32_t icle_config_get_heartbeat_interval(void);

/**
 * @brief Set heartbeat interval
 *
 * @param interval_ms Interval in milliseconds
 * @return 0 on success, negative errno on failure
 */
int icle_config_set_heartbeat_interval(uint32_t interval_ms);

/**
 * @brief Get log format
 *
 * @return Log format (0=binary, 1=csv)
 */
uint8_t icle_config_get_log_format(void);

/**
 * @brief Set log format
 *
 * @param format Log format (0=binary, 1=csv)
 * @return 0 on success, negative errno on failure
 */
int icle_config_set_log_format(uint8_t format);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_CONFIG_H_ */
