// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE OTA Update Service Implementation
 *
 * Uses ESP32 OTA partition scheme.
 */

#include "ota.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <string.h>

LOG_MODULE_REGISTER(icle_ota, CONFIG_LOG_DEFAULT_LEVEL);

/* Module state */
static struct {
	bool initialized;
	enum icle_ota_state state;
	char url[256];

	icle_ota_progress_cb_t progress_cb;
	void *progress_user_data;
	icle_ota_complete_cb_t complete_cb;
	void *complete_user_data;

	uint32_t bytes_received;
	uint32_t total_bytes;
} ota_ctx;

int icle_ota_init(void)
{
	if (ota_ctx.initialized)
		return 0;

	memset(&ota_ctx, 0, sizeof(ota_ctx));
	ota_ctx.state = ICLE_OTA_IDLE;
	ota_ctx.initialized = true;

	LOG_INF("OTA subsystem initialized");
	return 0;
}

int icle_ota_start(const char *url)
{
	if (!ota_ctx.initialized)
		return -ENODEV;

	if (url == NULL || strlen(url) >= sizeof(ota_ctx.url))
		return -EINVAL;

	if (ota_ctx.state != ICLE_OTA_IDLE)
		return -EBUSY;

	strncpy(ota_ctx.url, url, sizeof(ota_ctx.url) - 1);
	ota_ctx.state = ICLE_OTA_DOWNLOADING;
	ota_ctx.bytes_received = 0;
	ota_ctx.total_bytes = 0;

	LOG_INF("OTA update started from: %s", url);

	/* TODO: Implement actual ESP32 OTA download and flash */
	/* For now, this is a stub implementation */

	return 0;
}

int icle_ota_cancel(void)
{
	if (!ota_ctx.initialized)
		return -ENODEV;

	if (ota_ctx.state == ICLE_OTA_IDLE)
		return 0;

	LOG_INF("OTA update cancelled");
	ota_ctx.state = ICLE_OTA_IDLE;

	return 0;
}

enum icle_ota_state icle_ota_get_state(void)
{
	return ota_ctx.state;
}

bool icle_ota_is_active(void)
{
	return ota_ctx.state != ICLE_OTA_IDLE &&
	       ota_ctx.state != ICLE_OTA_COMPLETE &&
	       ota_ctx.state != ICLE_OTA_ERROR;
}

int icle_ota_set_progress_callback(icle_ota_progress_cb_t callback,
				   void *user_data)
{
	ota_ctx.progress_cb = callback;
	ota_ctx.progress_user_data = user_data;
	return 0;
}

int icle_ota_set_complete_callback(icle_ota_complete_cb_t callback,
				   void *user_data)
{
	ota_ctx.complete_cb = callback;
	ota_ctx.complete_user_data = user_data;
	return 0;
}

const char *icle_ota_state_name(enum icle_ota_state state)
{
	switch (state) {
	case ICLE_OTA_IDLE:
		return "idle";
	case ICLE_OTA_DOWNLOADING:
		return "downloading";
	case ICLE_OTA_VERIFYING:
		return "verifying";
	case ICLE_OTA_APPLYING:
		return "applying";
	case ICLE_OTA_COMPLETE:
		return "complete";
	case ICLE_OTA_ERROR:
		return "error";
	default:
		return "unknown";
	}
}

int icle_ota_mark_valid(void)
{
	if (!ota_ctx.initialized)
		return -ENODEV;

	/* TODO: Implement ESP32 OTA app valid marking */
	LOG_INF("OTA: firmware marked as valid");

	return 0;
}

int icle_ota_rollback(void)
{
	if (!ota_ctx.initialized)
		return -ENODEV;

	/* TODO: Implement ESP32 OTA rollback */
	LOG_INF("OTA: rollback requested");

	return -ENOTSUP;
}
