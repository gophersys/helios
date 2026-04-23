// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Log Manager
 *
 * Manages power measurement sampling, log entry formatting, queuing,
 * and persistence to SD card.
 *
 * ASYNC ARCHITECTURE:
 * - Sampler: k_work_delayable (self-rescheduling, replaces sampler thread)
 * - Writer: dedicated thread with k_queue_get(K_FOREVER)
 * - No blocking timeouts anywhere (only K_FOREVER and K_NO_WAIT)
 */

#include "services/logger.h"
#include "hal/storage.h"
#include "hal/power_monitor.h"
#include "app/events.h"
#include "icle/app.h"

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_log, CONFIG_LOG_DEFAULT_LEVEL);

#include <zephyr/kernel.h>
#include <string.h>
#include <stdio.h>

/* Configuration */
#define LOG_QUEUE_MAX_ENTRIES    256
#define LOG_ENTRY_SLAB_COUNT     (LOG_QUEUE_MAX_ENTRIES + 16)
#define LOG_MAX_CALLBACKS        4
#define LOG_WRITER_STACK_SIZE    2048
#define LOG_WRITER_PRIORITY      4
#define LOG_MIN_INTERVAL_MS      10
#define LOG_MAX_INTERVAL_MS      60000
#define LOG_FILE_MAX_SIZE        (1024 * 1024) /* 1MB */
#define LOG_FLUSH_INTERVAL_MS    5000

/* Writer thread stack */
static K_THREAD_STACK_DEFINE(writer_stack, LOG_WRITER_STACK_SIZE);

/* Queue entry wrapper for k_queue */
struct log_queue_entry {
	void *fifo_reserved; /* Required for k_queue */
	struct icle_log_entry entry;
};

/* Sentinel entries for flush/shutdown signaling */
static struct log_queue_entry flush_sentinel;
static struct log_queue_entry shutdown_sentinel;

/* Module state */
static struct {
	bool initialized;
	bool sampling_active;
	bool writer_active;
	bool shutdown_requested;

	/* Sample interval */
	uint32_t interval_ms;

	/* Memory slab for queue entries */
	struct k_mem_slab entry_slab;
	uint8_t slab_buffer[LOG_ENTRY_SLAB_COUNT * sizeof(struct log_queue_entry)]
		__aligned(4);

	/* Sample queue */
	struct k_queue sample_queue;
	uint32_t queue_depth;
	uint32_t max_queue_depth;

	/* Sync queue for HTTP upload */
	struct k_queue sync_queue;

	/* Sampler: k_work_delayable (replaces sampler thread) */
	struct k_work_delayable sampler_work;

	/* Writer thread */
	struct k_thread writer_thread;
	k_tid_t writer_tid;

	/* Synchronization */
	struct k_mutex state_mutex;
	struct k_sem flush_sem;

	/* Statistics */
	struct icle_log_stats stats;

	/* Callbacks */
	struct {
		icle_log_sample_cb_t callback;
		void *user_data;
	} callbacks[LOG_MAX_CALLBACKS];
	uint8_t callback_count;

	/* Log format */
	enum icle_log_format format;

} log_state;

/* Forward declarations */
static void sampler_work_handler(struct k_work *work);
static void writer_thread_entry(void *p1, void *p2, void *p3);
static int queue_entry(const struct icle_log_entry *entry);
static void notify_callbacks(const struct icle_log_entry *entry);
static void writer_handle_flush(char *csv_buffer, size_t csv_size);
static int writer_write_entry(const struct log_queue_entry *qentry,
			      char *csv_buffer, size_t csv_size);
static void writer_drain_remaining(char *csv_buffer, size_t csv_size);

int icle_log_init(void)
{
	int ret;

	if (log_state.initialized)
		return 0;

	memset(&log_state, 0, sizeof(log_state));

	/* Initialize memory slab for queue entries */
	ret = k_mem_slab_init(&log_state.entry_slab,
			      log_state.slab_buffer,
			      sizeof(struct log_queue_entry),
			      LOG_ENTRY_SLAB_COUNT);
	if (ret < 0) {
		LOG_ERR("Failed to init memory slab: %d", ret);
		return ret;
	}

	/* Initialize queues */
	k_queue_init(&log_state.sample_queue);
	k_queue_init(&log_state.sync_queue);

	/* Initialize synchronization primitives */
	ret = k_mutex_init(&log_state.state_mutex);
	if (ret < 0) {
		LOG_ERR("Failed to init mutex: %d", ret);
		return ret;
	}

	ret = k_sem_init(&log_state.flush_sem, 0, 1);
	if (ret < 0) {
		LOG_ERR("Failed to init semaphore: %d", ret);
		return ret;
	}

	/* Initialize sampler work item */
	k_work_init_delayable(&log_state.sampler_work, sampler_work_handler);

	/* Default configuration */
	log_state.interval_ms = 100;
	log_state.format = ICLE_LOG_FORMAT_BINARY;

	log_state.initialized = true;
	LOG_INF("Log manager initialized");

	return 0;
}

int icle_log_deinit(void)
{
	if (!log_state.initialized)
		return 0;

	/* Stop sampling if active */
	if (log_state.sampling_active)
		icle_log_stop_sampling();

	/* Flush remaining queue entries */
	icle_log_flush(5000);

	/* Request writer shutdown */
	if (log_state.writer_active) {
		log_state.shutdown_requested = true;
		k_queue_append(&log_state.sample_queue, &shutdown_sentinel);

		if (log_state.writer_tid != NULL)
			k_thread_join(log_state.writer_tid, K_FOREVER);
	}

	/* Clear queues */
	struct log_queue_entry *qentry;

	while ((qentry = k_queue_get(&log_state.sample_queue,
				     K_NO_WAIT)) != NULL) {
		if (qentry != &flush_sentinel && qentry != &shutdown_sentinel)
			k_mem_slab_free(&log_state.entry_slab, qentry);
	}

	log_state.initialized = false;
	LOG_INF("Log manager deinitialized");

	return 0;
}

int icle_log_start_sampling(uint32_t interval_ms)
{
	char header[128];
	int ret;
	int len;

	if (!log_state.initialized)
		return -ENODEV;

	if (interval_ms < LOG_MIN_INTERVAL_MS || interval_ms > LOG_MAX_INTERVAL_MS)
		return -EINVAL;

	k_mutex_lock(&log_state.state_mutex, K_FOREVER);

	if (log_state.sampling_active) {
		/* Already sampling, just update interval */
		log_state.interval_ms = interval_ms;
		/* Reschedule with new interval */
		k_work_reschedule(&log_state.sampler_work,
				  K_MSEC(log_state.interval_ms));
		k_mutex_unlock(&log_state.state_mutex);
		LOG_INF("Updated sample interval to %u ms", interval_ms);
		return 0;
	}

	log_state.interval_ms = interval_ms;
	log_state.shutdown_requested = false;

	/* Create log file if storage is ready */
	if (icle_storage_is_ready()) {
		ret = icle_storage_create_log(log_state.format);

		if (ret < 0) {
			LOG_WRN("Failed to create log file: %d", ret);
		} else if (log_state.format == ICLE_LOG_FORMAT_CSV) {
			len = icle_log_csv_header(header, sizeof(header));

			if (len > 0)
				icle_storage_write_log(header, len);
		}
	}

	/* Start writer thread first */
	log_state.writer_tid = k_thread_create(&log_state.writer_thread,
					       writer_stack,
					       K_THREAD_STACK_SIZEOF(writer_stack),
					       writer_thread_entry,
					       NULL, NULL, NULL,
					       LOG_WRITER_PRIORITY,
					       0,
					       K_NO_WAIT);
	if (log_state.writer_tid == NULL) {
		k_mutex_unlock(&log_state.state_mutex);
		LOG_ERR("Failed to create writer thread");
		return -ENOMEM;
	}
	k_thread_name_set(log_state.writer_tid, "log_writer");
	log_state.writer_active = true;

	/* Start sampler via k_work_delayable (replaces sampler thread) */
	log_state.sampling_active = true;
	log_state.stats.sampling_active = true;
	k_work_schedule(&log_state.sampler_work, K_MSEC(log_state.interval_ms));

	k_mutex_unlock(&log_state.state_mutex);

	LOG_INF("Sampling started at %u ms interval (work-based)", interval_ms);
	return 0;
}

int icle_log_stop_sampling(void)
{
	if (!log_state.initialized)
		return -ENODEV;

	k_mutex_lock(&log_state.state_mutex, K_FOREVER);

	if (!log_state.sampling_active) {
		k_mutex_unlock(&log_state.state_mutex);
		return 0;
	}

	log_state.sampling_active = false;
	log_state.stats.sampling_active = false;

	/* Cancel sampler work */
	k_work_cancel_delayable(&log_state.sampler_work);

	k_mutex_unlock(&log_state.state_mutex);

	LOG_INF("Sampling stopped");
	return 0;
}

bool icle_log_is_sampling(void)
{
	return log_state.sampling_active;
}

int icle_log_set_interval(uint32_t interval_ms)
{
	if (interval_ms < LOG_MIN_INTERVAL_MS || interval_ms > LOG_MAX_INTERVAL_MS)
		return -EINVAL;

	k_mutex_lock(&log_state.state_mutex, K_FOREVER);
	log_state.interval_ms = interval_ms;
	k_mutex_unlock(&log_state.state_mutex);

	LOG_DBG("Interval set to %u ms", interval_ms);
	return 0;
}

uint32_t icle_log_get_interval(void)
{
	return log_state.sampling_active ? log_state.interval_ms : 0;
}

int icle_log_take_sample(struct icle_log_entry *entry)
{
	struct icle_log_entry local_entry;
	struct icle_power_data power;
	int ret;

	if (!log_state.initialized)
		return -ENODEV;

	/* Read power measurements */
	ret = icle_power_read(&power);
	if (ret < 0) {
		LOG_WRN("Power read failed: %d", ret);
		local_entry.flags = ICLE_LOG_FLAG_SENSOR_ERR;
		local_entry.voltage_uv = 0;
		local_entry.current_ua = 0;
		local_entry.power_uw = 0;
	} else {
		local_entry.flags = ICLE_LOG_FLAG_NONE;
		local_entry.voltage_uv = power.voltage_uv;
		local_entry.current_ua = power.current_ua;
		local_entry.power_uw = power.power_uw;
	}

	/* Fill timestamps */
	local_entry.timestamp_ms = k_uptime_get_32();
	local_entry.rtc_time = 0;
	local_entry.reserved[0] = 0;
	local_entry.reserved[1] = 0;
	local_entry.reserved[2] = 0;

	/* Queue the entry */
	ret = queue_entry(&local_entry);
	if (ret < 0)
		return ret;

	/* Notify callbacks */
	notify_callbacks(&local_entry);

	/* Copy to caller if requested */
	if (entry != NULL)
		memcpy(entry, &local_entry, sizeof(*entry));

	return 0;
}

int icle_log_queue_get(struct icle_log_entry *entry, uint32_t timeout_ms)
{
	struct log_queue_entry *qentry;

	if (!log_state.initialized || entry == NULL)
		return -EINVAL;

	/* Only K_FOREVER and K_NO_WAIT are safe on ESP32 */
	k_timeout_t timeout = (timeout_ms == UINT32_MAX) ? K_FOREVER : K_NO_WAIT;

	qentry = k_queue_get(&log_state.sample_queue, timeout);
	if (qentry == NULL)
		return -ETIMEDOUT;

	/* Skip sentinel entries */
	if (qentry == &flush_sentinel || qentry == &shutdown_sentinel)
		return -EAGAIN;

	/* Copy entry and free slab memory */
	memcpy(entry, &qentry->entry, sizeof(*entry));
	k_mem_slab_free(&log_state.entry_slab, qentry);

	/* Update queue depth */
	k_mutex_lock(&log_state.state_mutex, K_FOREVER);
	if (log_state.queue_depth > 0)
		log_state.queue_depth--;

	k_mutex_unlock(&log_state.state_mutex);

	return 0;
}

uint32_t icle_log_queue_depth(void)
{
	return log_state.queue_depth;
}

int icle_log_flush(uint32_t timeout_ms)
{
	if (!log_state.initialized)
		return -ENODEV;

	if (!log_state.writer_active)
		return 0;

	/*
	 * Signal writer to flush by enqueueing the flush sentinel.
	 * Writer will drain queue, flush storage, then signal flush_sem
	 * and post ICLE_EVENT_WRITER_DONE event.
	 */
	k_sem_reset(&log_state.flush_sem);
	k_queue_append(&log_state.sample_queue, &flush_sentinel);

	if (timeout_ms == 0) {
		/*
		 * Non-blocking: return immediately, caller listens for
		 * ICLE_EVENT_WRITER_DONE event. Used in shutdown path
		 * to avoid blocking the event loop.
		 */
		return 0;
	}

	/*
	 * Blocking: wait for writer to complete flush.
	 * K_FOREVER is safe on ESP32.
	 */
	k_sem_take(&log_state.flush_sem, K_FOREVER);

	return 0;
}

int icle_log_get_stats(struct icle_log_stats *stats)
{
	if (stats == NULL)
		return -EINVAL;

	k_mutex_lock(&log_state.state_mutex, K_FOREVER);
	memcpy(stats, &log_state.stats, sizeof(*stats));
	stats->queue_depth = log_state.queue_depth;
	stats->max_queue_depth = log_state.max_queue_depth;
	stats->sampling_active = log_state.sampling_active;
	k_mutex_unlock(&log_state.state_mutex);

	return 0;
}

void icle_log_reset_stats(void)
{
	k_mutex_lock(&log_state.state_mutex, K_FOREVER);
	memset(&log_state.stats, 0, sizeof(log_state.stats));
	log_state.max_queue_depth = log_state.queue_depth;
	k_mutex_unlock(&log_state.state_mutex);
}

int icle_log_register_callback(icle_log_sample_cb_t callback, void *user_data)
{
	if (callback == NULL)
		return -EINVAL;

	k_mutex_lock(&log_state.state_mutex, K_FOREVER);

	if (log_state.callback_count >= LOG_MAX_CALLBACKS) {
		k_mutex_unlock(&log_state.state_mutex);
		return -ENOMEM;
	}

	log_state.callbacks[log_state.callback_count].callback = callback;
	log_state.callbacks[log_state.callback_count].user_data = user_data;
	log_state.callback_count++;

	k_mutex_unlock(&log_state.state_mutex);
	return 0;
}

void icle_log_unregister_callback(icle_log_sample_cb_t callback)
{
	k_mutex_lock(&log_state.state_mutex, K_FOREVER);

	for (int i = 0; i < log_state.callback_count; i++) {
		if (log_state.callbacks[i].callback == callback) {
			for (int j = i; j < log_state.callback_count - 1; j++)
				log_state.callbacks[j] = log_state.callbacks[j + 1];

			log_state.callback_count--;
			break;
		}
	}

	k_mutex_unlock(&log_state.state_mutex);
}

int icle_log_format_csv(const struct icle_log_entry *entry, char *buffer,
			size_t buffer_size)
{
	int len;

	if (entry == NULL || buffer == NULL || buffer_size == 0)
		return -EINVAL;

	len = snprintf(buffer, buffer_size,
		       "%u,%u,%d,%d,%d,0x%02x\n",
		       entry->timestamp_ms,
		       entry->rtc_time,
		       entry->voltage_uv,
		       entry->current_ua,
		       entry->power_uw,
		       entry->flags);

	if (len < 0 || (size_t)len >= buffer_size)
		return -ENOSPC;

	return len;
}

int icle_log_csv_header(char *buffer, size_t buffer_size)
{
	int len;

	if (buffer == NULL || buffer_size == 0)
		return -EINVAL;

	len = snprintf(buffer, buffer_size,
		       "timestamp_ms,rtc_time,voltage_uv,current_ua,power_uw,flags\n");

	if (len < 0 || (size_t)len >= buffer_size)
		return -ENOSPC;

	return len;
}

/* --- Internal functions --- */

static int queue_entry(const struct icle_log_entry *entry)
{
	struct log_queue_entry *qentry;
	int ret;

	/* Allocate from memory slab */
	ret = k_mem_slab_alloc(&log_state.entry_slab, (void **)&qentry, K_NO_WAIT);
	if (ret < 0) {
		/* Queue overflow - drop oldest sample */
		LOG_WRN("Queue overflow, dropping sample");

		k_mutex_lock(&log_state.state_mutex, K_FOREVER);
		log_state.stats.samples_dropped++;
		k_mutex_unlock(&log_state.state_mutex);

		/* Try to free oldest entry */
		qentry = k_queue_get(&log_state.sample_queue, K_NO_WAIT);
		if (qentry != NULL && qentry != &flush_sentinel &&
		    qentry != &shutdown_sentinel) {
			k_mutex_lock(&log_state.state_mutex, K_FOREVER);
			if (log_state.queue_depth > 0)
				log_state.queue_depth--;

			k_mutex_unlock(&log_state.state_mutex);
			/* Reuse this entry */
		} else {
			return -ENOMEM;
		}
	}

	/* Copy entry data */
	memcpy(&qentry->entry, entry, sizeof(*entry));

	/* Mark as overflow if we had to drop */
	if (ret < 0)
		qentry->entry.flags |= ICLE_LOG_FLAG_OVERFLOW;

	/* Add to queue */
	k_queue_append(&log_state.sample_queue, qentry);

	/* Update statistics */
	k_mutex_lock(&log_state.state_mutex, K_FOREVER);
	log_state.queue_depth++;
	log_state.stats.samples_taken++;
	if (log_state.queue_depth > log_state.max_queue_depth)
		log_state.max_queue_depth = log_state.queue_depth;

	k_mutex_unlock(&log_state.state_mutex);

	return 0;
}

static void notify_callbacks(const struct icle_log_entry *entry)
{
	k_mutex_lock(&log_state.state_mutex, K_FOREVER);

	for (int i = 0; i < log_state.callback_count; i++) {
		if (log_state.callbacks[i].callback != NULL) {
			log_state.callbacks[i].callback(entry,
				log_state.callbacks[i].user_data);
		}
	}

	k_mutex_unlock(&log_state.state_mutex);
}

/**
 * @brief Sampler work handler - self-rescheduling k_work_delayable
 *
 * Replaces the sampler thread. Takes one sample and reschedules
 * itself for the next interval. No blocking timeouts.
 */
static void sampler_work_handler(struct k_work *work)
{
	int ret;

	ARG_UNUSED(work);

	if (!log_state.sampling_active)
		return;

	/* Take sample */
	ret = icle_log_take_sample(NULL);

	if (ret < 0 && ret != -ENOMEM)
		LOG_WRN("Sample failed: %d", ret);

	/* Self-reschedule for next sample */
	if (log_state.sampling_active) {
		k_work_schedule(&log_state.sampler_work,
				K_MSEC(log_state.interval_ms));
	}
}

/**
 * @brief Handle the flush sentinel: drain queue, write remaining entries,
 *        flush storage, and signal completion to waiters.
 *
 * Called from writer_thread_entry when a flush_sentinel is dequeued.
 */
static void writer_handle_flush(char *csv_buffer, size_t csv_size)
{
	struct log_queue_entry *drain;
	int len;

	while ((drain = k_queue_get(&log_state.sample_queue,
				    K_NO_WAIT)) != NULL) {
		if (drain == &flush_sentinel ||
		    drain == &shutdown_sentinel)
			continue;

		k_mutex_lock(&log_state.state_mutex, K_FOREVER);
		if (log_state.queue_depth > 0)
			log_state.queue_depth--;

		k_mutex_unlock(&log_state.state_mutex);

		if (icle_storage_is_ready()) {
			if (log_state.format == ICLE_LOG_FORMAT_BINARY) {
				icle_storage_write_log(
					&drain->entry,
					sizeof(drain->entry));
			} else {
				len = icle_log_format_csv(
					&drain->entry,
					csv_buffer,
					csv_size);
				if (len > 0)
					icle_storage_write_log(
						csv_buffer, len);
			}
		}
		k_mem_slab_free(&log_state.entry_slab, drain);
	}

	if (icle_storage_is_ready())
		icle_storage_flush_log();

	/* Signal flush complete */
	k_sem_give(&log_state.flush_sem);
	icle_events_post(ICLE_EVENT_WRITER_DONE);
}

/**
 * @brief Write a single normal data entry to storage, including rotation check.
 *
 * @param qentry  Pointer to the queue entry to write (must not be a sentinel).
 * @param csv_buffer  Scratch buffer for CSV formatting.
 * @param csv_size    Size of csv_buffer in bytes.
 * @return 0 on success, negative errno on error.
 */
static int writer_write_entry(const struct log_queue_entry *qentry,
			      char *csv_buffer, size_t csv_size)
{
	int ret = 0;
	int len;

	if (!icle_storage_is_ready())
		return 0;

	/* Check for rotation */
	if (icle_storage_needs_rotation(LOG_FILE_MAX_SIZE)) {
		ret = icle_storage_rotate_log(log_state.format);
		if (ret < 0) {
			LOG_WRN("Log rotation failed: %d", ret);
		} else if (log_state.format == ICLE_LOG_FORMAT_CSV) {
			len = icle_log_csv_header(csv_buffer, csv_size);

			if (len > 0)
				icle_storage_write_log(csv_buffer, len);
		}
	}

	/* Write entry */
	if (log_state.format == ICLE_LOG_FORMAT_BINARY) {
		ret = icle_storage_write_log(&qentry->entry,
					     sizeof(qentry->entry));
	} else {
		len = icle_log_format_csv(&qentry->entry,
					  csv_buffer, csv_size);
		if (len > 0)
			ret = icle_storage_write_log(csv_buffer, len);
		else
			ret = len;
	}

	if (ret < 0) {
		k_mutex_lock(&log_state.state_mutex, K_FOREVER);
		log_state.stats.write_errors++;
		k_mutex_unlock(&log_state.state_mutex);
		LOG_WRN("Write failed: %d", ret);
	} else {
		k_mutex_lock(&log_state.state_mutex, K_FOREVER);
		log_state.stats.samples_written++;
		k_mutex_unlock(&log_state.state_mutex);
	}

	return ret;
}

/**
 * @brief Drain all remaining entries from the queue on shutdown.
 *
 * Called once after the writer loop exits to flush any entries that
 * arrived between the shutdown_sentinel and the queue becoming empty.
 */
static void writer_drain_remaining(char *csv_buffer, size_t csv_size)
{
	struct log_queue_entry *qentry;
	int len;

	while ((qentry = k_queue_get(&log_state.sample_queue,
				     K_NO_WAIT)) != NULL) {
		if (qentry == &flush_sentinel || qentry == &shutdown_sentinel)
			continue;

		if (icle_storage_is_ready()) {
			if (log_state.format == ICLE_LOG_FORMAT_BINARY) {
				icle_storage_write_log(&qentry->entry,
						       sizeof(qentry->entry));
			} else {
				len = icle_log_format_csv(&qentry->entry,
							  csv_buffer,
							  csv_size);
				if (len > 0)
					icle_storage_write_log(csv_buffer, len);
			}
		}
		k_mem_slab_free(&log_state.entry_slab, qentry);
	}
}

/**
 * @brief Writer thread - blocks on k_queue_get(K_FOREVER)
 *
 * K_FOREVER is safe on ESP32 (only timed waits hang).
 * Uses sentinel entries for flush/shutdown signaling.
 */
static void writer_thread_entry(void *p1, void *p2, void *p3)
{
	char csv_buffer[128];
	uint32_t last_flush;
	uint32_t now;

	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	LOG_INF("Writer thread started");

	last_flush = k_uptime_get_32();

	while (!log_state.shutdown_requested) {
		struct log_queue_entry *qentry;

		/* Block until an entry is available - K_FOREVER is safe */
		qentry = k_queue_get(&log_state.sample_queue, K_FOREVER);

		if (qentry == NULL) {
			/* Shouldn't happen with K_FOREVER, but handle it */
			continue;
		}

		/* Check for shutdown sentinel */
		if (qentry == &shutdown_sentinel)
			break;

		/* Check for flush sentinel */
		if (qentry == &flush_sentinel) {
			writer_handle_flush(csv_buffer, sizeof(csv_buffer));
			continue;
		}

		/* Normal data entry - update queue depth */
		k_mutex_lock(&log_state.state_mutex, K_FOREVER);
		if (log_state.queue_depth > 0)
			log_state.queue_depth--;

		k_mutex_unlock(&log_state.state_mutex);

		/* Write to storage */
		writer_write_entry(qentry, csv_buffer, sizeof(csv_buffer));

		/* Free slab memory */
		k_mem_slab_free(&log_state.entry_slab, qentry);

		/* Periodic flush */
		now = k_uptime_get_32();

		if (now - last_flush >= LOG_FLUSH_INTERVAL_MS) {
			if (icle_storage_is_ready())
				icle_storage_flush_log();

			last_flush = now;
		}
	}

	/* Final drain on shutdown */
	writer_drain_remaining(csv_buffer, sizeof(csv_buffer));

	if (icle_storage_is_ready()) {
		icle_storage_flush_log();
		icle_storage_close_log();
	}

	log_state.writer_active = false;
	LOG_INF("Writer thread exiting");
}
