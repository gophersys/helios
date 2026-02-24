/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE SD Card Storage Manager
 *
 * Manages SD card mounting, log file operations, and rotation.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#ifndef ICLE_STORAGE_H_
#define ICLE_STORAGE_H_

#include <zephyr/kernel.h>
#include <zephyr/fs/fs.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Storage state
 */
enum icle_storage_state {
	ICLE_STORAGE_UNMOUNTED,  /* SD card not mounted */
	ICLE_STORAGE_MOUNTED,    /* SD card mounted and ready */
	ICLE_STORAGE_ERROR,      /* Mount or I/O error */
	ICLE_STORAGE_FULL,       /* SD card full (< threshold) */
};

/**
 * @brief Log file format
 */
enum icle_log_format {
	ICLE_LOG_FORMAT_BINARY = 0,  /* Compact binary format */
	ICLE_LOG_FORMAT_CSV = 1,     /* Human-readable CSV */
};

/**
 * @brief Storage statistics
 */
struct icle_storage_stats {
	enum icle_storage_state state;
	uint64_t total_bytes;
	uint64_t free_bytes;
	uint32_t log_file_count;
	uint32_t pending_sync_count;
	char current_log_file[64];
};

/**
 * @brief File entry for enumeration
 */
struct icle_file_entry {
	char name[64];
	uint32_t size;
	uint32_t timestamp;
	bool synced;
};

/**
 * @brief Initialize storage subsystem
 *
 * Initializes SPI interface and mounts SD card.
 * Creates internal mutex programmatically.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_storage_init(void);

/**
 * @brief Deinitialize storage subsystem
 *
 * Unmounts SD card and releases resources.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_storage_deinit(void);

/**
 * @brief Mount SD card
 *
 * @return 0 on success, negative errno on failure
 */
int icle_storage_mount(void);

/**
 * @brief Unmount SD card
 *
 * Flushes pending writes before unmounting.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_storage_unmount(void);

/**
 * @brief Check if storage is ready
 *
 * @return true if mounted and ready for I/O
 */
bool icle_storage_is_ready(void);

/**
 * @brief Get storage state
 *
 * @return Current storage state
 */
enum icle_storage_state icle_storage_get_state(void);

/**
 * @brief Get storage statistics
 *
 * @param stats Pointer to store statistics
 * @return 0 on success, negative errno on failure
 */
int icle_storage_get_stats(struct icle_storage_stats *stats);

/**
 * @brief Create new log file
 *
 * Creates a new log file with timestamp-based name.
 * Closes previous log file if open.
 *
 * @param format Log file format (binary or CSV)
 * @return 0 on success, negative errno on failure
 */
int icle_storage_create_log(enum icle_log_format format);

/**
 * @brief Write data to current log file
 *
 * @param data Pointer to data buffer
 * @param len Length of data in bytes
 * @return Number of bytes written, or negative errno on failure
 */
int icle_storage_write_log(const void *data, size_t len);

/**
 * @brief Flush log file buffers to SD card
 *
 * @return 0 on success, negative errno on failure
 */
int icle_storage_flush_log(void);

/**
 * @brief Close current log file
 *
 * @return 0 on success, negative errno on failure
 */
int icle_storage_close_log(void);

/**
 * @brief Check if log rotation is needed
 *
 * @param max_size_bytes Maximum log file size
 * @return true if current log exceeds max size
 */
bool icle_storage_needs_rotation(uint32_t max_size_bytes);

/**
 * @brief Rotate log file
 *
 * Closes current log and creates new one.
 *
 * @param format Format for new log file
 * @return 0 on success, negative errno on failure
 */
int icle_storage_rotate_log(enum icle_log_format format);

/**
 * @brief Get list of log files pending sync
 *
 * @param entries Array to store file entries
 * @param max_entries Maximum entries to return
 * @return Number of entries found, or negative errno on failure
 */
int icle_storage_get_pending_files(struct icle_file_entry *entries,
				   size_t max_entries);

/**
 * @brief Mark file as synced
 *
 * @param filename File to mark as synced
 * @return 0 on success, negative errno on failure
 */
int icle_storage_mark_synced(const char *filename);

/**
 * @brief Read file contents
 *
 * @param filename File to read
 * @param buffer Buffer to store contents
 * @param buffer_size Size of buffer
 * @param offset Offset in file to start reading
 * @return Bytes read, or negative errno on failure
 */
int icle_storage_read_file(const char *filename, void *buffer,
			   size_t buffer_size, size_t offset);

/**
 * @brief Delete file
 *
 * @param filename File to delete
 * @return 0 on success, negative errno on failure
 */
int icle_storage_delete_file(const char *filename);

/**
 * @brief Clean up old files when storage is low
 *
 * Deletes oldest synced files until free space > threshold.
 *
 * @param min_free_percent Minimum free space percentage
 * @return Number of files deleted, or negative errno on failure
 */
int icle_storage_cleanup(uint8_t min_free_percent);

/**
 * @brief Get storage state name string
 *
 * @param state Storage state
 * @return State name string
 */
const char *icle_storage_state_name(enum icle_storage_state state);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_STORAGE_H_ */
