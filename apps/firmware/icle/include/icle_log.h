/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE Log Manager
 *
 * Manages power measurement sampling, log entry formatting, and queuing.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#ifndef ICLE_LOG_H_
#define ICLE_LOG_H_

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Log entry status flags
 */
enum icle_log_flags {
	ICLE_LOG_FLAG_NONE        = 0,
	ICLE_LOG_FLAG_OVERFLOW    = BIT(0),  /* Sample queue overflow */
	ICLE_LOG_FLAG_SENSOR_ERR  = BIT(1),  /* Sensor read error */
	ICLE_LOG_FLAG_SYNC_POINT  = BIT(2),  /* Sync checkpoint */
	ICLE_LOG_FLAG_MODE_CHANGE = BIT(3),  /* Operating mode changed */
};

/**
 * @brief Single log entry (power measurement sample)
 */
struct icle_log_entry {
	uint32_t timestamp_ms;   /* Uptime at sample time */
	uint32_t rtc_time;       /* RTC epoch if available, 0 otherwise */
	int32_t voltage_uv;      /* Bus voltage in microvolts */
	int32_t current_ua;      /* Current in microamps */
	int32_t power_uw;        /* Power in microwatts */
	uint8_t flags;           /* Status flags */
	uint8_t reserved[3];     /* Alignment padding */
};

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
 *
 * Called for each sample if registered. Can be used for real-time display.
 *
 * @param entry The sampled log entry
 * @param user_data User-provided context
 */
typedef void (*icle_log_sample_cb_t)(const struct icle_log_entry *entry,
				     void *user_data);

/**
 * @brief Initialize log manager
 *
 * Creates sample queue and threads programmatically.
 * Does NOT use K_QUEUE_DEFINE or K_THREAD_DEFINE.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_log_init(void);

/**
 * @brief Deinitialize log manager
 *
 * Stops sampling, flushes queue, releases resources.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_log_deinit(void);

/**
 * @brief Start power sampling
 *
 * Begins periodic INA209 sampling at specified interval.
 * Samples are queued for writing to storage.
 *
 * @param interval_ms Sample interval in milliseconds
 * @return 0 on success, negative errno on failure
 */
int icle_log_start_sampling(uint32_t interval_ms);

/**
 * @brief Stop power sampling
 *
 * Stops the sampling thread. Queue continues to drain.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_log_stop_sampling(void);

/**
 * @brief Check if sampling is active
 *
 * @return true if sampling thread is running
 */
bool icle_log_is_sampling(void);

/**
 * @brief Set sample interval
 *
 * Can be called while sampling is active.
 *
 * @param interval_ms New sample interval in milliseconds
 * @return 0 on success, -EINVAL if interval invalid
 */
int icle_log_set_interval(uint32_t interval_ms);

/**
 * @brief Get current sample interval
 *
 * @return Current interval in ms, or 0 if not sampling
 */
uint32_t icle_log_get_interval(void);

/**
 * @brief Take single sample immediately
 *
 * Takes a sample outside the normal sampling interval.
 *
 * @param entry Pointer to store the sample (can be NULL)
 * @return 0 on success, negative errno on failure
 */
int icle_log_take_sample(struct icle_log_entry *entry);

/**
 * @brief Get next entry from queue (for writer thread)
 *
 * Blocks until entry available or timeout.
 *
 * @param entry Pointer to store entry
 * @param timeout_ms Timeout in ms, K_FOREVER for indefinite
 * @return 0 on success, -ETIMEDOUT on timeout, negative errno on error
 */
int icle_log_queue_get(struct icle_log_entry *entry, uint32_t timeout_ms);

/**
 * @brief Get queue depth
 *
 * @return Number of entries currently in queue
 */
uint32_t icle_log_queue_depth(void);

/**
 * @brief Flush queue to storage
 *
 * Blocks until all queued entries written.
 *
 * @param timeout_ms Maximum time to wait
 * @return 0 on success, -ETIMEDOUT if not all flushed
 */
int icle_log_flush(uint32_t timeout_ms);

/**
 * @brief Get log statistics
 *
 * @param stats Pointer to store statistics
 * @return 0 on success
 */
int icle_log_get_stats(struct icle_log_stats *stats);

/**
 * @brief Reset statistics counters
 */
void icle_log_reset_stats(void);

/**
 * @brief Register sample callback
 *
 * @param callback Callback function
 * @param user_data User context
 * @return 0 on success, -ENOMEM if too many callbacks
 */
int icle_log_register_callback(icle_log_sample_cb_t callback, void *user_data);

/**
 * @brief Unregister sample callback
 *
 * @param callback Callback to remove
 */
void icle_log_unregister_callback(icle_log_sample_cb_t callback);

/**
 * @brief Format entry as CSV string
 *
 * @param entry Entry to format
 * @param buffer Output buffer
 * @param buffer_size Buffer size
 * @return Length of formatted string, or negative errno on error
 */
int icle_log_format_csv(const struct icle_log_entry *entry, char *buffer,
			size_t buffer_size);

/**
 * @brief Get CSV header string
 *
 * @param buffer Output buffer
 * @param buffer_size Buffer size
 * @return Length of header string
 */
int icle_log_csv_header(char *buffer, size_t buffer_size);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_LOG_H_ */
