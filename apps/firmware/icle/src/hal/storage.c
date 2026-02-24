/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE SD Card Storage Manager
 *
 * Manages SD card mounting, log file operations, and rotation.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#include "hal/storage.h"

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_storage, CONFIG_LOG_DEFAULT_LEVEL);

#include <zephyr/device.h>
#include <zephyr/storage/disk_access.h>
#include <zephyr/fs/fs.h>
#include <zephyr/settings/settings.h>
#include <ff.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* SD card disk name */
#define SD_DISK_NAME "SD"

/* Mount point */
#define SD_MOUNT_POINT "/SD:"

/* Log directory path */
#define LOG_DIR_PATH SD_MOUNT_POINT "/icle/logs"

/* Sync marker directory (empty files to track sync status) */
#define SYNC_MARKER_DIR SD_MOUNT_POINT "/icle/.synced"

/* Maximum log file size (1MB) */
#define MAX_LOG_FILE_SIZE (1024 * 1024)

/* Minimum free space percentage */
#define MIN_FREE_SPACE_PERCENT 10

/* Maximum files to enumerate */
#define MAX_FILE_ENUM 64

/* FatFS mount point structure */
static FATFS fat_fs;

/* Zephyr FS mount point */
static struct fs_mount_t mp = {
	.type = FS_FATFS,
	.fs_data = &fat_fs,
	.mnt_point = SD_MOUNT_POINT,
};

/* Storage mutex for thread-safe access */
static struct k_mutex storage_mutex;

/* Current state */
static enum icle_storage_state current_state = ICLE_STORAGE_UNMOUNTED;

/* Currently open log file */
static struct fs_file_t current_log_file;
static char current_log_path[128];
static bool log_file_open;
static enum icle_log_format current_format;
static uint32_t current_file_size;

/* Initialization flag */
static bool initialized;

/**
 * @brief Ensure directory exists (create if needed)
 */
static int ensure_directory(const char *path)
{
	struct fs_dirent entry;
	int ret;

	ret = fs_stat(path, &entry);
	if (ret == 0) {
		if (entry.type == FS_DIR_ENTRY_DIR) {
			return 0;
		}
		LOG_ERR("Path exists but is not a directory: %s", path);
		return -ENOTDIR;
	}

	if (ret != -ENOENT) {
		LOG_ERR("Failed to stat %s: %d", path, ret);
		return ret;
	}

	ret = fs_mkdir(path);
	if (ret < 0 && ret != -EEXIST) {
		LOG_ERR("Failed to create directory %s: %d", path, ret);
		return ret;
	}

	LOG_DBG("Created directory: %s", path);
	return 0;
}

/**
 * @brief Initialize directory structure on SD card
 */
static int init_directory_structure(void)
{
	int ret;

	/* Create /icle directory */
	ret = ensure_directory(SD_MOUNT_POINT "/icle");
	if (ret < 0) {
		return ret;
	}

	/* Create /icle/logs directory */
	ret = ensure_directory(LOG_DIR_PATH);
	if (ret < 0) {
		return ret;
	}

	/* Create /icle/.synced directory for sync markers */
	ret = ensure_directory(SYNC_MARKER_DIR);
	if (ret < 0) {
		return ret;
	}

	return 0;
}

/**
 * @brief Generate timestamp-based filename
 */
static void generate_log_filename(char *buf, size_t buf_size,
				  enum icle_log_format format)
{
	/* Use uptime as timestamp since we may not have RTC */
	uint32_t uptime_ms = k_uptime_get_32();
	uint32_t hours = (uptime_ms / 3600000) % 24;
	uint32_t mins = (uptime_ms / 60000) % 60;
	uint32_t secs = (uptime_ms / 1000) % 60;

	/* Approximate date from boot count (would be replaced with RTC) */
	uint32_t day = 1;
	uint32_t month = 1;
	uint32_t year = 2024;

	const char *ext = (format == ICLE_LOG_FORMAT_CSV) ? "csv" : "bin";

	snprintf(buf, buf_size, "%s/%04u%02u%02u_%02u%02u%02u.%s",
		 LOG_DIR_PATH, year, month, day, hours, mins, secs, ext);
}

/**
 * @brief Check if file has been synced
 */
static bool is_file_synced(const char *filename)
{
	char marker_path[128];
	struct fs_dirent entry;

	snprintf(marker_path, sizeof(marker_path), "%s/%s", SYNC_MARKER_DIR, filename);

	return (fs_stat(marker_path, &entry) == 0);
}

/**
 * @brief Extract filename from full path
 */
static const char *get_filename_from_path(const char *path)
{
	const char *name = strrchr(path, '/');
	return name ? (name + 1) : path;
}

/**
 * @brief Compare file entries by timestamp (oldest first)
 */
static int compare_file_entries(const void *a, const void *b)
{
	const struct icle_file_entry *fa = (const struct icle_file_entry *)a;
	const struct icle_file_entry *fb = (const struct icle_file_entry *)b;

	if (fa->timestamp < fb->timestamp) {
		return -1;
	}
	if (fa->timestamp > fb->timestamp) {
		return 1;
	}
	return 0;
}

/**
 * @brief Get all log files sorted by timestamp
 */
static int get_log_files_sorted(struct icle_file_entry *entries,
				size_t max_entries, bool synced_only)
{
	struct fs_dir_t dir;
	struct fs_dirent entry;
	int count = 0;
	int ret;

	fs_dir_t_init(&dir);

	ret = fs_opendir(&dir, LOG_DIR_PATH);
	if (ret < 0) {
		LOG_ERR("Failed to open log directory: %d", ret);
		return ret;
	}

	while (count < max_entries) {
		ret = fs_readdir(&dir, &entry);
		if (ret < 0) {
			LOG_ERR("Error reading directory: %d", ret);
			break;
		}

		if (entry.name[0] == '\0') {
			break; /* End of directory */
		}

		if (entry.type != FS_DIR_ENTRY_FILE) {
			continue;
		}

		/* Check file extension */
		const char *ext = strrchr(entry.name, '.');
		if (!ext || (strcmp(ext, ".bin") != 0 && strcmp(ext, ".csv") != 0)) {
			continue;
		}

		bool synced = is_file_synced(entry.name);

		if (synced_only && !synced) {
			continue;
		}

		strncpy(entries[count].name, entry.name,
			sizeof(entries[count].name) - 1);
		entries[count].name[sizeof(entries[count].name) - 1] = '\0';
		entries[count].size = entry.size;
		entries[count].synced = synced;

		/* Parse timestamp from filename (YYYYMMDD_HHMMSS) */
		unsigned int year, month, day, hour, min, sec;
		if (sscanf(entry.name, "%4u%2u%2u_%2u%2u%2u",
			   &year, &month, &day, &hour, &min, &sec) == 6) {
			entries[count].timestamp =
				((year - 2000) * 365 * 24 * 3600) +
				(month * 30 * 24 * 3600) +
				(day * 24 * 3600) +
				(hour * 3600) +
				(min * 60) +
				sec;
		} else {
			entries[count].timestamp = 0;
		}

		count++;
	}

	fs_closedir(&dir);

	/* Sort by timestamp (oldest first) */
	if (count > 1) {
		qsort(entries, count, sizeof(struct icle_file_entry),
		      compare_file_entries);
	}

	return count;
}

int icle_storage_init(void)
{
	int ret;

	if (initialized) {
		return 0;
	}

	LOG_DBG("Storage init starting...");

	/* Initialize mutex programmatically */
	k_mutex_init(&storage_mutex);

	/* Initialize file structure */
	fs_file_t_init(&current_log_file);
	log_file_open = false;
	current_log_path[0] = '\0';
	current_file_size = 0;

	current_state = ICLE_STORAGE_UNMOUNTED;
	initialized = true;

	LOG_INF("Storage subsystem initialized (no SD card mount attempted at boot)");

	/* Don't attempt mount at boot - let application trigger mount when needed
	 * This avoids blocking if SD card is not present */

	return 0;
}

int icle_storage_deinit(void)
{
	int ret;

	if (!initialized) {
		return 0;
	}

	/* Close any open log file */
	if (log_file_open) {
		icle_storage_close_log();
	}

	/* Unmount SD card */
	ret = icle_storage_unmount();

	initialized = false;
	LOG_INF("Storage subsystem deinitialized");

	return ret;
}

int icle_storage_mount(void)
{
	int ret;
	uint32_t block_count;
	uint32_t block_size;

	if (!initialized) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (current_state == ICLE_STORAGE_MOUNTED) {
		k_mutex_unlock(&storage_mutex);
		return 0;
	}

	/* Initialize disk access */
	ret = disk_access_init(SD_DISK_NAME);
	if (ret < 0) {
		LOG_ERR("Disk access init failed: %d", ret);
		current_state = ICLE_STORAGE_ERROR;
		k_mutex_unlock(&storage_mutex);
		return ret;
	}

	/* Check disk status */
	ret = disk_access_status(SD_DISK_NAME);
	if (ret != DISK_STATUS_OK) {
		LOG_ERR("Disk not ready: %d", ret);
		current_state = ICLE_STORAGE_ERROR;
		k_mutex_unlock(&storage_mutex);
		return -EIO;
	}

	/* Get disk info */
	ret = disk_access_ioctl(SD_DISK_NAME, DISK_IOCTL_GET_SECTOR_COUNT,
				&block_count);
	if (ret == 0) {
		ret = disk_access_ioctl(SD_DISK_NAME, DISK_IOCTL_GET_SECTOR_SIZE,
					&block_size);
	}

	if (ret == 0) {
		LOG_INF("SD card: %u sectors, %u bytes/sector, total %u MB",
			block_count, block_size,
			(block_count * block_size) / (1024 * 1024));
	}

	/* Mount filesystem */
	ret = fs_mount(&mp);
	if (ret < 0) {
		LOG_ERR("Failed to mount SD card: %d", ret);
		current_state = ICLE_STORAGE_ERROR;
		k_mutex_unlock(&storage_mutex);
		return ret;
	}

	current_state = ICLE_STORAGE_MOUNTED;
	LOG_INF("SD card mounted at %s", SD_MOUNT_POINT);

	/* Initialize directory structure */
	ret = init_directory_structure();
	if (ret < 0) {
		LOG_ERR("Failed to create directories: %d", ret);
		/* Continue anyway - may work for reading */
	}

	k_mutex_unlock(&storage_mutex);
	return 0;
}

int icle_storage_unmount(void)
{
	int ret;

	if (!initialized) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (current_state != ICLE_STORAGE_MOUNTED) {
		k_mutex_unlock(&storage_mutex);
		return 0;
	}

	/* Close any open log file first */
	if (log_file_open) {
		fs_sync(&current_log_file);
		fs_close(&current_log_file);
		log_file_open = false;
	}

	ret = fs_unmount(&mp);
	if (ret < 0) {
		LOG_ERR("Failed to unmount SD card: %d", ret);
		k_mutex_unlock(&storage_mutex);
		return ret;
	}

	current_state = ICLE_STORAGE_UNMOUNTED;
	LOG_INF("SD card unmounted");

	k_mutex_unlock(&storage_mutex);
	return 0;
}

bool icle_storage_is_ready(void)
{
	return initialized && (current_state == ICLE_STORAGE_MOUNTED);
}

enum icle_storage_state icle_storage_get_state(void)
{
	return current_state;
}

int icle_storage_get_stats(struct icle_storage_stats *stats)
{
	struct fs_statvfs stat;
	int ret;

	if (!initialized || stats == NULL) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	stats->state = current_state;

	if (current_state != ICLE_STORAGE_MOUNTED) {
		stats->total_bytes = 0;
		stats->free_bytes = 0;
		stats->log_file_count = 0;
		stats->pending_sync_count = 0;
		stats->current_log_file[0] = '\0';
		k_mutex_unlock(&storage_mutex);
		return 0;
	}

	/* Get filesystem stats */
	ret = fs_statvfs(SD_MOUNT_POINT, &stat);
	if (ret < 0) {
		LOG_ERR("Failed to get FS stats: %d", ret);
		k_mutex_unlock(&storage_mutex);
		return ret;
	}

	stats->total_bytes = (uint64_t)stat.f_blocks * stat.f_frsize;
	stats->free_bytes = (uint64_t)stat.f_bfree * stat.f_frsize;

	/* Count log files */
	struct fs_dir_t dir;
	struct fs_dirent entry;
	uint32_t file_count = 0;
	uint32_t pending_count = 0;

	fs_dir_t_init(&dir);

	ret = fs_opendir(&dir, LOG_DIR_PATH);
	if (ret == 0) {
		while (fs_readdir(&dir, &entry) == 0 && entry.name[0] != '\0') {
			if (entry.type == FS_DIR_ENTRY_FILE) {
				const char *ext = strrchr(entry.name, '.');
				if (ext && (strcmp(ext, ".bin") == 0 ||
					    strcmp(ext, ".csv") == 0)) {
					file_count++;
					if (!is_file_synced(entry.name)) {
						pending_count++;
					}
				}
			}
		}
		fs_closedir(&dir);
	}

	stats->log_file_count = file_count;
	stats->pending_sync_count = pending_count;

	/* Current log file */
	if (log_file_open && current_log_path[0] != '\0') {
		const char *name = get_filename_from_path(current_log_path);
		strncpy(stats->current_log_file, name,
			sizeof(stats->current_log_file) - 1);
		stats->current_log_file[sizeof(stats->current_log_file) - 1] = '\0';
	} else {
		stats->current_log_file[0] = '\0';
	}

	/* Check if storage is critically low */
	if (stats->total_bytes > 0) {
		uint8_t free_percent =
			(uint8_t)((stats->free_bytes * 100) / stats->total_bytes);
		if (free_percent < MIN_FREE_SPACE_PERCENT) {
			current_state = ICLE_STORAGE_FULL;
			stats->state = ICLE_STORAGE_FULL;
		}
	}

	k_mutex_unlock(&storage_mutex);
	return 0;
}

int icle_storage_create_log(enum icle_log_format format)
{
	int ret;
	char filepath[128];

	if (!initialized) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (current_state != ICLE_STORAGE_MOUNTED) {
		LOG_ERR("Storage not mounted");
		k_mutex_unlock(&storage_mutex);
		return -ENODEV;
	}

	/* Close existing log file if open */
	if (log_file_open) {
		fs_sync(&current_log_file);
		fs_close(&current_log_file);
		log_file_open = false;
	}

	/* Generate new filename */
	generate_log_filename(filepath, sizeof(filepath), format);

	/* Create new log file */
	ret = fs_open(&current_log_file, filepath, FS_O_CREATE | FS_O_WRITE);
	if (ret < 0) {
		LOG_ERR("Failed to create log file %s: %d", filepath, ret);
		k_mutex_unlock(&storage_mutex);
		return ret;
	}

	strncpy(current_log_path, filepath, sizeof(current_log_path) - 1);
	current_log_path[sizeof(current_log_path) - 1] = '\0';
	current_format = format;
	current_file_size = 0;
	log_file_open = true;

	/* Write CSV header if CSV format */
	if (format == ICLE_LOG_FORMAT_CSV) {
		const char *header = "timestamp_ms,rtc_time,voltage_uv,current_ua,power_uw,flags\n";
		ssize_t written = fs_write(&current_log_file, header, strlen(header));
		if (written > 0) {
			current_file_size += written;
		}
	}

	LOG_INF("Created log file: %s", get_filename_from_path(filepath));

	k_mutex_unlock(&storage_mutex);
	return 0;
}

int icle_storage_write_log(const void *data, size_t len)
{
	ssize_t written;

	if (!initialized || data == NULL || len == 0) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (!log_file_open) {
		LOG_ERR("No log file open");
		k_mutex_unlock(&storage_mutex);
		return -ENOENT;
	}

	written = fs_write(&current_log_file, data, len);
	if (written < 0) {
		LOG_ERR("Failed to write to log: %d", (int)written);
		k_mutex_unlock(&storage_mutex);
		return (int)written;
	}

	current_file_size += written;

	k_mutex_unlock(&storage_mutex);
	return (int)written;
}

int icle_storage_flush_log(void)
{
	int ret;

	if (!initialized) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (!log_file_open) {
		k_mutex_unlock(&storage_mutex);
		return 0;
	}

	ret = fs_sync(&current_log_file);
	if (ret < 0) {
		LOG_ERR("Failed to flush log: %d", ret);
	}

	k_mutex_unlock(&storage_mutex);
	return ret;
}

int icle_storage_close_log(void)
{
	int ret;

	if (!initialized) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (!log_file_open) {
		k_mutex_unlock(&storage_mutex);
		return 0;
	}

	ret = fs_sync(&current_log_file);
	if (ret < 0) {
		LOG_WRN("Sync before close failed: %d", ret);
	}

	ret = fs_close(&current_log_file);
	if (ret < 0) {
		LOG_ERR("Failed to close log: %d", ret);
		k_mutex_unlock(&storage_mutex);
		return ret;
	}

	LOG_INF("Closed log file: %s (size: %u bytes)",
		get_filename_from_path(current_log_path), current_file_size);

	log_file_open = false;
	current_log_path[0] = '\0';
	current_file_size = 0;

	k_mutex_unlock(&storage_mutex);
	return 0;
}

bool icle_storage_needs_rotation(uint32_t max_size_bytes)
{
	if (!initialized || !log_file_open) {
		return false;
	}

	return current_file_size >= max_size_bytes;
}

int icle_storage_rotate_log(enum icle_log_format format)
{
	int ret;

	if (!initialized) {
		return -EINVAL;
	}

	LOG_INF("Rotating log file");

	/* Close current file */
	ret = icle_storage_close_log();
	if (ret < 0) {
		return ret;
	}

	/* Small delay to ensure different filename.
	 * k_busy_wait instead of k_msleep - timed sleeps hang on ESP32. */
	k_busy_wait(10000);

	/* Create new file */
	return icle_storage_create_log(format);
}

int icle_storage_get_pending_files(struct icle_file_entry *entries,
				   size_t max_entries)
{
	struct icle_file_entry all_entries[MAX_FILE_ENUM];
	int total;
	int pending_count = 0;

	if (!initialized || entries == NULL || max_entries == 0) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (current_state != ICLE_STORAGE_MOUNTED) {
		k_mutex_unlock(&storage_mutex);
		return -ENODEV;
	}

	/* Get all log files sorted by timestamp */
	total = get_log_files_sorted(all_entries, MAX_FILE_ENUM, false);
	if (total < 0) {
		k_mutex_unlock(&storage_mutex);
		return total;
	}

	/* Filter to pending (unsynced) files */
	for (int i = 0; i < total && pending_count < max_entries; i++) {
		if (!all_entries[i].synced) {
			/* Skip currently open file */
			if (log_file_open &&
			    strcmp(all_entries[i].name,
				   get_filename_from_path(current_log_path)) == 0) {
				continue;
			}
			entries[pending_count++] = all_entries[i];
		}
	}

	k_mutex_unlock(&storage_mutex);
	return pending_count;
}

int icle_storage_mark_synced(const char *filename)
{
	char marker_path[128];
	struct fs_file_t marker;
	int ret;

	if (!initialized || filename == NULL) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (current_state != ICLE_STORAGE_MOUNTED) {
		k_mutex_unlock(&storage_mutex);
		return -ENODEV;
	}

	/* Create empty marker file */
	snprintf(marker_path, sizeof(marker_path), "%s/%s",
		 SYNC_MARKER_DIR, filename);

	fs_file_t_init(&marker);
	ret = fs_open(&marker, marker_path, FS_O_CREATE | FS_O_WRITE);
	if (ret < 0) {
		LOG_ERR("Failed to create sync marker: %d", ret);
		k_mutex_unlock(&storage_mutex);
		return ret;
	}

	fs_close(&marker);

	LOG_DBG("Marked as synced: %s", filename);

	k_mutex_unlock(&storage_mutex);
	return 0;
}

int icle_storage_read_file(const char *filename, void *buffer,
			   size_t buffer_size, size_t offset)
{
	char filepath[128];
	struct fs_file_t file;
	ssize_t bytes_read;
	int ret;

	if (!initialized || filename == NULL || buffer == NULL) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (current_state != ICLE_STORAGE_MOUNTED) {
		k_mutex_unlock(&storage_mutex);
		return -ENODEV;
	}

	/* Build full path */
	snprintf(filepath, sizeof(filepath), "%s/%s", LOG_DIR_PATH, filename);

	fs_file_t_init(&file);
	ret = fs_open(&file, filepath, FS_O_READ);
	if (ret < 0) {
		LOG_ERR("Failed to open file %s: %d", filename, ret);
		k_mutex_unlock(&storage_mutex);
		return ret;
	}

	/* Seek to offset */
	if (offset > 0) {
		ret = fs_seek(&file, offset, FS_SEEK_SET);
		if (ret < 0) {
			LOG_ERR("Failed to seek: %d", ret);
			fs_close(&file);
			k_mutex_unlock(&storage_mutex);
			return ret;
		}
	}

	/* Read data */
	bytes_read = fs_read(&file, buffer, buffer_size);
	if (bytes_read < 0) {
		LOG_ERR("Failed to read file: %d", (int)bytes_read);
		fs_close(&file);
		k_mutex_unlock(&storage_mutex);
		return (int)bytes_read;
	}

	fs_close(&file);

	k_mutex_unlock(&storage_mutex);
	return (int)bytes_read;
}

int icle_storage_delete_file(const char *filename)
{
	char filepath[128];
	char marker_path[128];
	int ret;

	if (!initialized || filename == NULL) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (current_state != ICLE_STORAGE_MOUNTED) {
		k_mutex_unlock(&storage_mutex);
		return -ENODEV;
	}

	/* Delete log file */
	snprintf(filepath, sizeof(filepath), "%s/%s", LOG_DIR_PATH, filename);
	ret = fs_unlink(filepath);
	if (ret < 0 && ret != -ENOENT) {
		LOG_ERR("Failed to delete file %s: %d", filename, ret);
		k_mutex_unlock(&storage_mutex);
		return ret;
	}

	/* Also delete sync marker if exists */
	snprintf(marker_path, sizeof(marker_path), "%s/%s",
		 SYNC_MARKER_DIR, filename);
	fs_unlink(marker_path); /* Ignore errors */

	LOG_INF("Deleted file: %s", filename);

	k_mutex_unlock(&storage_mutex);
	return 0;
}

int icle_storage_cleanup(uint8_t min_free_percent)
{
	struct icle_file_entry entries[MAX_FILE_ENUM];
	struct icle_storage_stats stats;
	int total_files;
	int deleted = 0;
	int ret;

	if (!initialized) {
		return -EINVAL;
	}

	k_mutex_lock(&storage_mutex, K_FOREVER);

	if (current_state != ICLE_STORAGE_MOUNTED) {
		k_mutex_unlock(&storage_mutex);
		return -ENODEV;
	}

	/* Get all synced files (safe to delete) sorted oldest first */
	total_files = get_log_files_sorted(entries, MAX_FILE_ENUM, true);
	if (total_files < 0) {
		k_mutex_unlock(&storage_mutex);
		return total_files;
	}

	k_mutex_unlock(&storage_mutex);

	/* Delete oldest synced files until we have enough space */
	for (int i = 0; i < total_files; i++) {
		/* Check current free space */
		ret = icle_storage_get_stats(&stats);
		if (ret < 0) {
			return deleted > 0 ? deleted : ret;
		}

		if (stats.total_bytes == 0) {
			break;
		}

		uint8_t free_percent =
			(uint8_t)((stats.free_bytes * 100) / stats.total_bytes);

		if (free_percent >= min_free_percent) {
			LOG_INF("Cleanup complete: %u%% free (deleted %d files)",
				free_percent, deleted);
			break;
		}

		/* Delete this file */
		ret = icle_storage_delete_file(entries[i].name);
		if (ret == 0) {
			deleted++;
			LOG_DBG("Cleanup: deleted %s", entries[i].name);
		}
	}

	if (deleted > 0) {
		LOG_INF("Storage cleanup: deleted %d old files", deleted);
	}

	return deleted;
}

const char *icle_storage_state_name(enum icle_storage_state state)
{
	switch (state) {
	case ICLE_STORAGE_UNMOUNTED:
		return "unmounted";
	case ICLE_STORAGE_MOUNTED:
		return "mounted";
	case ICLE_STORAGE_ERROR:
		return "error";
	case ICLE_STORAGE_FULL:
		return "full";
	default:
		return "unknown";
	}
}
