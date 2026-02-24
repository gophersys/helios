/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE HTTP Client Service
 *
 * HTTP client for syncing logs to Concord backend.
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
	ICLE_HTTP_STATE_IDLE,
	ICLE_HTTP_STATE_CONNECTING,
	ICLE_HTTP_STATE_SENDING,
	ICLE_HTTP_STATE_RECEIVING,
	ICLE_HTTP_STATE_ERROR,
};

/**
 * @brief HTTP response structure
 */
struct icle_http_response {
	int status_code;
	size_t content_length;
	size_t body_received;
	char content_type[64];
};

/**
 * @brief Sync result structure
 */
struct icle_sync_result {
	bool success;
	int http_status;
	size_t bytes_sent;
	uint32_t duration_ms;
	char error_msg[64];
};

/**
 * @brief Progress callback type
 */
typedef void (*icle_sync_progress_cb_t)(const char *filename,
					size_t bytes_sent,
					size_t total_bytes,
					void *user_data);

/**
 * @brief Completion callback type
 */
typedef void (*icle_sync_complete_cb_t)(const char *filename,
					const struct icle_sync_result *result,
					void *user_data);

/**
 * @brief Initialize HTTP client
 */
int icle_http_init(void);

/**
 * @brief Deinitialize HTTP client
 */
int icle_http_deinit(void);

/**
 * @brief Set backend base URL
 */
int icle_http_set_base_url(const char *base_url);

/**
 * @brief Set device ID for authentication
 */
int icle_http_set_device_id(const char *device_id);

/**
 * @brief Set API key for authentication
 */
int icle_http_set_api_key(const char *api_key);

/**
 * @brief Check if sync is in progress
 */
bool icle_http_is_syncing(void);

/**
 * @brief Cancel ongoing sync operation
 */
int icle_http_cancel_sync(void);

/**
 * @brief Get current HTTP state
 */
enum icle_http_state icle_http_get_state(void);

/**
 * @brief Set request timeout
 */
void icle_http_set_timeout(uint32_t timeout_ms);

/**
 * @brief Set retry configuration
 */
void icle_http_set_retry_config(uint8_t max_retries, uint32_t backoff_ms);

/**
 * @brief Ping backend to check connectivity
 */
int icle_http_ping(uint32_t timeout_ms);

/**
 * @brief Get HTTP state name string
 */
const char *icle_http_state_name(enum icle_http_state state);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_HTTP_H_ */
