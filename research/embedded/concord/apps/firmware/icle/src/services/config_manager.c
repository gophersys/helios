// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Configuration Manager Implementation
 *
 * Uses Zephyr settings subsystem with ZMS backend.
 */

#include "config_manager.h"
#include "icle/config.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/settings/settings.h>
#include <string.h>

LOG_MODULE_REGISTER(icle_config, CONFIG_LOG_DEFAULT_LEVEL);

/* Settings subtree name */
#define SETTINGS_SUBTREE "icle"

/* Current configuration */
static struct icle_config current_config;
static bool initialized;
static struct k_mutex config_mutex;

/* Settings handler */
static int config_set_handler(const char *name, size_t len,
			      settings_read_cb read_cb, void *cb_arg);
static int config_export_handler(int (*cb)(const char *name,
					   const void *value, size_t val_len));

/* Settings handler structure */
SETTINGS_STATIC_HANDLER_DEFINE(icle, SETTINGS_SUBTREE, NULL,
			       config_set_handler, NULL,
			       config_export_handler);

/*
 * config_set_handler dispatch table
 *
 * Each entry maps a settings key name to the config field it populates.
 * Using a table instead of a long if-else chain keeps CCN <= 15.
 */

/** One entry in the settings dispatch table */
struct config_key_entry {
	const char *key;        /* Settings key name below the subtree */
	void       *field;      /* Pointer to the field in current_config */
	size_t      field_size; /* Max bytes to read into field */
};

/** Dispatch table — order does not matter, linear scan is fine for 7 entries */
static const struct config_key_entry config_key_table[] = {
	{ "device_id",          current_config.device_id,
	  sizeof(current_config.device_id) },
	{ "wifi_ssid",          current_config.wifi_ssid,
	  sizeof(current_config.wifi_ssid) },
	{ "wifi_psk",           current_config.wifi_psk,
	  sizeof(current_config.wifi_psk) },
	{ "backend_url",        current_config.backend_url,
	  sizeof(current_config.backend_url) },
	{ "sample_interval",    &current_config.sample_interval_ms,
	  sizeof(current_config.sample_interval_ms) },
	{ "heartbeat_interval", &current_config.heartbeat_interval_ms,
	  sizeof(current_config.heartbeat_interval_ms) },
	{ "log_format",         &current_config.log_format,
	  sizeof(current_config.log_format) },
};

/**
 * @brief Settings set handler - called during load
 *
 * Dispatches each key via config_key_table to eliminate the long if-else
 * chain and keep cyclomatic complexity below 15.
 */
static int config_set_handler(const char *name, size_t len,
			      settings_read_cb read_cb, void *cb_arg)
{
	const char *next;
	size_t i;
	ssize_t rc;

	ARG_UNUSED(len);

	for (i = 0; i < ARRAY_SIZE(config_key_table); i++) {
		if (!settings_name_steq(name, config_key_table[i].key, &next) || next)
			continue;

		/* read_cb returns ssize_t — keep as ssize_t to avoid narrowing */
		rc = read_cb(cb_arg, config_key_table[i].field,
			     config_key_table[i].field_size);

		return (rc < 0) ? (int)rc : 0;
	}

	return -ENOENT;
}

/**
 * @brief Settings export handler - called during save
 */
static int config_export_handler(int (*cb)(const char *name,
					   const void *value, size_t val_len))
{
	cb(SETTINGS_SUBTREE "/device_id",
	   current_config.device_id, strlen(current_config.device_id) + 1);
	cb(SETTINGS_SUBTREE "/wifi_ssid",
	   current_config.wifi_ssid, strlen(current_config.wifi_ssid) + 1);
	cb(SETTINGS_SUBTREE "/wifi_psk",
	   current_config.wifi_psk, strlen(current_config.wifi_psk) + 1);
	cb(SETTINGS_SUBTREE "/backend_url",
	   current_config.backend_url, strlen(current_config.backend_url) + 1);
	cb(SETTINGS_SUBTREE "/sample_interval",
	   &current_config.sample_interval_ms,
	   sizeof(current_config.sample_interval_ms));
	cb(SETTINGS_SUBTREE "/heartbeat_interval",
	   &current_config.heartbeat_interval_ms,
	   sizeof(current_config.heartbeat_interval_ms));
	cb(SETTINGS_SUBTREE "/log_format",
	   &current_config.log_format, sizeof(current_config.log_format));

	return 0;
}

/**
 * @brief Set default configuration values
 */
static void set_defaults(void)
{
	memset(&current_config, 0, sizeof(current_config));

	strncpy(current_config.device_id, CONFIG_ICLE_DEVICE_ID,
		sizeof(current_config.device_id) - 1);
	strncpy(current_config.wifi_ssid, CONFIG_ICLE_WIFI_SSID,
		sizeof(current_config.wifi_ssid) - 1);
	strncpy(current_config.wifi_psk, CONFIG_ICLE_WIFI_PSK,
		sizeof(current_config.wifi_psk) - 1);
	strncpy(current_config.backend_url, ICLE_DEFAULT_BACKEND_URL,
		sizeof(current_config.backend_url) - 1);

	current_config.sample_interval_ms = ICLE_DEFAULT_SAMPLE_INTERVAL_MS;
	current_config.heartbeat_interval_ms = ICLE_DEFAULT_HEARTBEAT_INTERVAL_MS;
	current_config.log_format = ICLE_DEFAULT_LOG_FORMAT;
}

int icle_config_init(void)
{
	int ret;

	if (initialized)
		return 0;

	k_mutex_init(&config_mutex);

	/* Set defaults first */
	set_defaults();

	/* Initialize settings subsystem */
	ret = settings_subsys_init();
	if (ret < 0) {
		LOG_ERR("Settings init failed: %d", ret);
		/* Continue with defaults */
	} else {
		/* Load stored settings */
		ret = settings_load_subtree(SETTINGS_SUBTREE);
		if (ret < 0)
			LOG_WRN("Settings load failed: %d (using defaults)", ret);
		else
			LOG_INF("Configuration loaded from storage");
	}

	initialized = true;
	LOG_INF("Config manager initialized (device_id=%s)", current_config.device_id);

	return 0;
}

int icle_config_get(struct icle_config *config)
{
	if (config == NULL)
		return -EINVAL;

	k_mutex_lock(&config_mutex, K_FOREVER);
	memcpy(config, &current_config, sizeof(*config));
	k_mutex_unlock(&config_mutex);

	return 0;
}

int icle_config_set(const struct icle_config *config)
{
	int ret;

	if (config == NULL)
		return -EINVAL;

	k_mutex_lock(&config_mutex, K_FOREVER);
	memcpy(&current_config, config, sizeof(current_config));
	k_mutex_unlock(&config_mutex);

	/* Save to storage */
	ret = settings_save();
	if (ret < 0) {
		LOG_ERR("Settings save failed: %d", ret);
		return ret;
	}

	LOG_INF("Configuration saved");
	return 0;
}

int icle_config_reset(void)
{
	int ret;

	k_mutex_lock(&config_mutex, K_FOREVER);
	set_defaults();
	k_mutex_unlock(&config_mutex);

	/* Save defaults to storage */
	ret = settings_save();
	if (ret < 0)
		LOG_WRN("Failed to save defaults: %d", ret);

	LOG_INF("Configuration reset to defaults");
	return 0;
}

const char *icle_config_get_wifi_ssid(void)
{
	return current_config.wifi_ssid;
}

const char *icle_config_get_wifi_psk(void)
{
	return current_config.wifi_psk;
}

int icle_config_set_wifi(const char *ssid, const char *psk)
{
	if (ssid == NULL)
		return -EINVAL;

	k_mutex_lock(&config_mutex, K_FOREVER);

	strncpy(current_config.wifi_ssid, ssid,
		sizeof(current_config.wifi_ssid) - 1);
	current_config.wifi_ssid[sizeof(current_config.wifi_ssid) - 1] = '\0';

	if (psk != NULL) {
		strncpy(current_config.wifi_psk, psk,
			sizeof(current_config.wifi_psk) - 1);
		current_config.wifi_psk[sizeof(current_config.wifi_psk) - 1] = '\0';
	} else {
		current_config.wifi_psk[0] = '\0';
	}

	k_mutex_unlock(&config_mutex);

	return settings_save();
}

const char *icle_config_get_device_id(void)
{
	return current_config.device_id;
}

int icle_config_set_device_id(const char *device_id)
{
	if (device_id == NULL)
		return -EINVAL;

	k_mutex_lock(&config_mutex, K_FOREVER);
	strncpy(current_config.device_id, device_id,
		sizeof(current_config.device_id) - 1);
	current_config.device_id[sizeof(current_config.device_id) - 1] = '\0';
	k_mutex_unlock(&config_mutex);

	return settings_save();
}

const char *icle_config_get_backend_url(void)
{
	return current_config.backend_url;
}

int icle_config_set_backend_url(const char *url)
{
	if (url == NULL)
		return -EINVAL;

	k_mutex_lock(&config_mutex, K_FOREVER);
	strncpy(current_config.backend_url, url,
		sizeof(current_config.backend_url) - 1);
	current_config.backend_url[sizeof(current_config.backend_url) - 1] = '\0';
	k_mutex_unlock(&config_mutex);

	return settings_save();
}

uint32_t icle_config_get_sample_interval(void)
{
	return current_config.sample_interval_ms;
}

int icle_config_set_sample_interval(uint32_t interval_ms)
{
	k_mutex_lock(&config_mutex, K_FOREVER);
	current_config.sample_interval_ms = interval_ms;
	k_mutex_unlock(&config_mutex);

	return settings_save();
}

uint32_t icle_config_get_heartbeat_interval(void)
{
	return current_config.heartbeat_interval_ms;
}

int icle_config_set_heartbeat_interval(uint32_t interval_ms)
{
	k_mutex_lock(&config_mutex, K_FOREVER);
	current_config.heartbeat_interval_ms = interval_ms;
	k_mutex_unlock(&config_mutex);

	return settings_save();
}

uint8_t icle_config_get_log_format(void)
{
	return current_config.log_format;
}

int icle_config_set_log_format(uint8_t format)
{
	k_mutex_lock(&config_mutex, K_FOREVER);
	current_config.log_format = format;
	k_mutex_unlock(&config_mutex);

	return settings_save();
}
