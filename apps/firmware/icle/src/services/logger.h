// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Logger Service
 *
 * Power sampling, queue management, and SD card writing.
 */

#ifndef ICLE_LOGGER_H_
#define ICLE_LOGGER_H_

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>
#include "icle/types.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Log manager statistics
 */
struct icle_log_stats {
	uint32_t samples_taken;
	uint32_t samples_written;
	uint32_t samples_dropped;
	uint32_t queue_depth;
	uint32_t max_queue_depth;
	uint32_t write_errors;
	bool sampling_active;
};

/**
 * @brief Sample callback type
 */
typedef void (*icle_log_sample_cb_t)(const struct icle_log_entry *entry,
				     void *user_data);

/**
 * @brief Initialize log manager
 */
int icle_log_init(void);

/**
 * @brief Deinitialize log manager
 */
int icle_log_deinit(void);

/**
 * @brief Start power sampling
 */
int icle_log_start_sampling(uint32_t interval_ms);

/**
 * @brief Stop power sampling
 */
int icle_log_stop_sampling(void);

/**
 * @brief Check if sampling is active
 */
bool icle_log_is_sampling(void);

/**
 * @brief Set sample interval
 */
int icle_log_set_interval(uint32_t interval_ms);

/**
 * @brief Get current sample interval
 */
uint32_t icle_log_get_interval(void);

/**
 * @brief Take single sample immediately
 */
int icle_log_take_sample(struct icle_log_entry *entry);

/**
 * @brief Get next entry from queue
 */
int icle_log_queue_get(struct icle_log_entry *entry, uint32_t timeout_ms);

/**
 * @brief Get queue depth
 */
uint32_t icle_log_queue_depth(void);

/**
 * @brief Flush queue to storage
 */
int icle_log_flush(uint32_t timeout_ms);

/**
 * @brief Get log statistics
 */
int icle_log_get_stats(struct icle_log_stats *stats);

/**
 * @brief Reset statistics counters
 */
void icle_log_reset_stats(void);

/**
 * @brief Register sample callback
 */
int icle_log_register_callback(icle_log_sample_cb_t callback, void *user_data);

/**
 * @brief Unregister sample callback
 */
void icle_log_unregister_callback(icle_log_sample_cb_t callback);

/**
 * @brief Format entry as CSV string
 */
int icle_log_format_csv(const struct icle_log_entry *entry, char *buffer,
			size_t buffer_size);

/**
 * @brief Get CSV header string
 */
int icle_log_csv_header(char *buffer, size_t buffer_size);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_LOGGER_H_ */
