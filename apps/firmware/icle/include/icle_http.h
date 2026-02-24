/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE HTTP Client
 *
 * HTTP client for syncing logs to Concord backend.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#ifndef ICLE_HTTP_H_
#define ICLE_HTTP_H_

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief HTTP client state
 */
enum icle_http_state {
	ICLE_HTTP_STATE_IDLE,       /* No active request */
	ICLE_HTTP_STATE_CONNECTING, /* TCP connection in progress */
	ICLE_HTTP_STATE_SENDING,    /* Sending request */
	ICLE_HTTP_STATE_RECEIVING,  /* Receiving response */
	ICLE_HTTP_STATE_ERROR,      /* Request failed */
};

/**
 * @brief HTTP response status
 */
struct icle_http_response {
	int status_code;        /* HTTP status code (200, 404, etc) */
	size_t content_length;  /* Response body length */
	size_t body_received;   /* Bytes of body received so far */
	char content_type[64];  /* Content-Type header value */
};

/**
 * @brief Sync result for log file upload
 */
struct icle_sync_result {
	bool success;
	int http_status;
	uint32_t bytes_sent;
	uint32_t duration_ms;
	char error_msg[64];
};

/**
 * @brief Sync progress callback
 *
 * @param filename File being synced
 * @param bytes_sent Bytes sent so far
 * @param total_bytes Total file size
 * @param user_data User context
 */
typedef void (*icle_sync_progress_cb_t)(const char *filename,
					uint32_t bytes_sent,
					uint32_t total_bytes,
					void *user_data);

/**
 * @brief Sync complete callback
 *
 * @param filename File that was synced
 * @param result Sync result
 * @param user_data User context
 */
typedef void (*icle_sync_complete_cb_t)(const char *filename,
					const struct icle_sync_result *result,
					void *user_data);

/**
 * @brief Initialize HTTP client
 *
 * Creates internal resources programmatically.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_http_init(void);

/**
 * @brief Deinitialize HTTP client
 *
 * Cancels pending requests and releases resources.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_http_deinit(void);

/**
 * @brief Set base URL for API requests
 *
 * @param base_url Base URL (e.g., "https://api.concord.local")
 * @return 0 on success, -EINVAL if URL invalid
 */
int icle_http_set_base_url(const char *base_url);

/**
 * @brief Set device ID for API authentication
 *
 * @param device_id Device identifier
 * @return 0 on success, -EINVAL if ID invalid
 */
int icle_http_set_device_id(const char *device_id);

/**
 * @brief Set API key/token for authentication
 *
 * @param api_key API key or bearer token
 * @return 0 on success, negative errno on failure
 */
int icle_http_set_api_key(const char *api_key);

/**
 * @brief Sync single log file to backend
 *
 * Uploads file via HTTP POST to configured endpoint.
 * Blocking call - returns when complete or error.
 *
 * @param filename Log file path on SD card
 * @param result Pointer to store result (can be NULL)
 * @return 0 on success, negative errno on failure
 */
int icle_http_sync_file(const char *filename, struct icle_sync_result *result);

/**
 * @brief Start async log file sync
 *
 * Non-blocking file upload. Use callbacks for progress/completion.
 *
 * @param filename Log file path
 * @return 0 if started, negative errno on failure
 */
int icle_http_sync_file_async(const char *filename);

/**
 * @brief Cancel pending sync operation
 *
 * @return 0 on success, -ENOENT if no sync in progress
 */
int icle_http_cancel_sync(void);

/**
 * @brief Check if sync is in progress
 *
 * @return true if sync operation active
 */
bool icle_http_is_syncing(void);

/**
 * @brief Wait for sync to complete
 *
 * @param timeout_ms Timeout in ms, K_FOREVER for indefinite
 * @return 0 on success, -ETIMEDOUT on timeout
 */
int icle_http_wait_sync(uint32_t timeout_ms);

/**
 * @brief Get HTTP client state
 *
 * @return Current state
 */
enum icle_http_state icle_http_get_state(void);

/**
 * @brief Register progress callback
 *
 * @param callback Progress callback
 * @param user_data User context
 */
void icle_http_set_progress_callback(icle_sync_progress_cb_t callback,
				     void *user_data);

/**
 * @brief Register completion callback
 *
 * @param callback Completion callback
 * @param user_data User context
 */
void icle_http_set_complete_callback(icle_sync_complete_cb_t callback,
				     void *user_data);

/**
 * @brief Perform health check ping to backend
 *
 * @param timeout_ms Request timeout
 * @return 0 if backend reachable, negative errno on failure
 */
int icle_http_ping(uint32_t timeout_ms);

/**
 * @brief Register device with backend
 *
 * POST device info to registration endpoint.
 *
 * @param device_id Device identifier
 * @param firmware_version Firmware version string
 * @return 0 on success, HTTP status if error response, negative errno on failure
 */
int icle_http_register_device(const char *device_id, const char *firmware_version);

/**
 * @brief Get pending configuration from backend
 *
 * Checks if backend has new configuration for this device.
 *
 * @param buffer Buffer to store config JSON
 * @param buffer_size Buffer size
 * @return Bytes received, 0 if no new config, negative errno on error
 */
int icle_http_get_config(char *buffer, size_t buffer_size);

/**
 * @brief Set connection timeout
 *
 * @param timeout_ms Connection timeout in ms
 */
void icle_http_set_timeout(uint32_t timeout_ms);

/**
 * @brief Set retry configuration
 *
 * @param max_retries Maximum retry attempts (0 = no retry)
 * @param backoff_ms Initial backoff between retries
 */
void icle_http_set_retry_config(uint8_t max_retries, uint32_t backoff_ms);

/**
 * @brief Get state name string
 *
 * @param state HTTP state
 * @return State name string
 */
const char *icle_http_state_name(enum icle_http_state state);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_HTTP_H_ */
