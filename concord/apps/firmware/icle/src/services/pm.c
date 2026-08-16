// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Power Management Implementation
 *
 * Handles deep sleep entry/exit, ZMS state persistence,
 * and wake cause detection for ESP32.
 */

#include "services/pm.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_ctrl.h>
#include <zephyr/settings/settings.h>
#include <string.h>

#ifdef CONFIG_SOC_SERIES_ESP32
#include <esp_sleep.h>
#endif

LOG_MODULE_REGISTER(icle_pm, CONFIG_LOG_DEFAULT_LEVEL);

/* ZMS key for persistent state */
#define PM_ZMS_KEY "icle/pm_state"

/*
 * RTC_DATA_ATTR - survives deep sleep on ESP32.
 * On non-ESP32 platforms, these are just regular statics (reset on reboot).
 */
#ifdef CONFIG_SOC_SERIES_ESP32
static RTC_DATA_ATTR uint32_t rtc_boot_count;
static RTC_DATA_ATTR uint32_t rtc_last_state;
static RTC_DATA_ATTR uint32_t rtc_flags;
#else
static uint32_t rtc_boot_count;
static uint32_t rtc_last_state;
static uint32_t rtc_flags;
#endif

static bool pm_initialized;

int icle_pm_init(void)
{
	if (pm_initialized)
		return 0;

	rtc_boot_count++;
	pm_initialized = true;

	LOG_INF("PM initialized (boot_count=%u, rtc_last_state=%u, rtc_flags=0x%x)",
		rtc_boot_count, rtc_last_state, rtc_flags);

	return 0;
}

enum icle_wake_source icle_pm_detect_wake_cause(void)
{
#ifdef CONFIG_SOC_SERIES_ESP32
	esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();

	switch (cause) {
	case ESP_SLEEP_WAKEUP_TIMER:
		LOG_INF("Wake cause: TIMER");
		return ICLE_WAKE_TIMER;

	case ESP_SLEEP_WAKEUP_EXT0:
	case ESP_SLEEP_WAKEUP_EXT1:
		LOG_INF("Wake cause: BUTTON (ext wakeup)");
		return ICLE_WAKE_BUTTON;

	case ESP_SLEEP_WAKEUP_UNDEFINED:
	default:
		LOG_INF("Wake cause: RESET (cold boot)");
		return ICLE_WAKE_RESET;
	}
#else
	LOG_INF("Wake cause: RESET (non-ESP32)");
	return ICLE_WAKE_RESET;
#endif
}

uint32_t icle_pm_get_boot_count(void)
{
	return rtc_boot_count;
}

int icle_pm_save_state(const struct icle_pm_persist_state *state)
{
	int ret;

	if (state == NULL)
		return -EINVAL;

	ret = settings_save_one(PM_ZMS_KEY, state, sizeof(*state));
	if (ret < 0) {
		LOG_ERR("Failed to save PM state to ZMS: %d", ret);
		return ret;
	}

	/* Update RTC quick state */
	rtc_last_state = state->device_state;

	LOG_INF("PM state saved (state=%u, action=%u, wake_count=%u)",
		state->device_state, state->scheduled_action, state->wake_count);
	return 0;
}

int icle_pm_restore_state(struct icle_pm_persist_state *state)
{
	int len;
	int ret;

	if (state == NULL)
		return -EINVAL;

	len = sizeof(*state);
	ret = settings_runtime_get(PM_ZMS_KEY, state, len);

	if (ret < 0) {
		LOG_WRN("No PM state in ZMS (cold boot): %d", ret);
		memset(state, 0, sizeof(*state));
		return -ENOENT;
	}

	if (state->magic != ICLE_PM_STATE_MAGIC) {
		LOG_WRN("PM state magic mismatch: 0x%08x", state->magic);
		memset(state, 0, sizeof(*state));
		return -EINVAL;
	}

	LOG_INF("PM state restored (state=%u, action=%u, wake_count=%u)",
		state->device_state, state->scheduled_action, state->wake_count);
	return 0;
}

int icle_pm_configure_wakeup(uint32_t timer_sec, uint32_t button_gpio_mask)
{
#ifdef CONFIG_SOC_SERIES_ESP32
	if (timer_sec > 0) {
		uint64_t timer_us = (uint64_t)timer_sec * 1000000ULL;
		esp_err_t err = esp_sleep_enable_timer_wakeup(timer_us);

		if (err != ESP_OK) {
			LOG_ERR("Failed to enable timer wakeup: %d", err);
			return -EIO;
		}
		LOG_INF("Timer wakeup configured: %u seconds", timer_sec);
	}

	if (button_gpio_mask != 0) {
		esp_err_t err = esp_sleep_enable_ext1_wakeup(
			button_gpio_mask, ESP_EXT1_WAKEUP_ALL_LOW);

		if (err != ESP_OK) {
			LOG_ERR("Failed to enable ext1 wakeup: %d", err);
			return -EIO;
		}
		LOG_INF("Button wakeup configured: mask=0x%08x", button_gpio_mask);
	}

	return 0;
#else
	ARG_UNUSED(timer_sec);
	ARG_UNUSED(button_gpio_mask);
	LOG_WRN("Deep sleep wakeup not supported on this platform");
	return -ENOTSUP;
#endif
}

void icle_pm_enter_deep_sleep(void)
{
	LOG_INF("Entering deep sleep...");
	LOG_PANIC(); /* Flush log buffers */

#ifdef CONFIG_SOC_SERIES_ESP32
	esp_deep_sleep_start();
	/* Never reaches here */
#else
	LOG_WRN("Deep sleep not available, halting");
	k_sleep(K_FOREVER);
#endif

	CODE_UNREACHABLE;
}
