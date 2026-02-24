/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE Power Management Implementation
 *
 * Manages device power states including deep sleep, wake sources,
 * and RTC memory preservation for the ESP32-WROOM-32.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#include "icle_power_monitor.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_pm, CONFIG_LOG_DEFAULT_LEVEL);

#include <zephyr/drivers/gpio.h>
#include <zephyr/pm/pm.h>
#include <zephyr/pm/policy.h>
#include <errno.h>
#include <string.h>

#ifdef CONFIG_SOC_SERIES_ESP32
#include <soc/rtc.h>
#include <esp_sleep.h>
#include <esp_system.h>
#include <driver/rtc_io.h>
#include <rom/rtc.h>
#endif

/* Button GPIO for wake source - defined in board DTS */
#define BUTTON_NODE DT_ALIAS(sw0)

#if DT_NODE_HAS_STATUS(BUTTON_NODE, okay)
static const struct gpio_dt_spec button_gpio = GPIO_DT_SPEC_GET(BUTTON_NODE, gpios);
#endif

/* RTC memory magic for validation */
#define RTC_STATE_MAGIC ICLE_RTC_STATE_MAGIC

/* Power management state (renamed to avoid conflict with Zephyr pm_state enum) */
struct icle_pm_state {
	bool initialized;
	enum icle_wake_source wake_source;
	bool gpio_wake_enabled;
	bool timer_wake_enabled;
	uint32_t timer_wake_ms;
	struct icle_rtc_state rtc_state;
	bool rtc_state_valid;
	struct k_mutex state_mutex;
	struct k_timer idle_timer;
	uint32_t idle_timeout_ms;
};

static struct icle_pm_state pm_ctx;

/* RTC memory section for ESP32 - preserved across deep sleep */
#ifdef CONFIG_SOC_SERIES_ESP32
static RTC_DATA_ATTR struct icle_rtc_state rtc_memory_state;
#else
/* Fallback for non-ESP32 targets (simulation/testing) */
static struct icle_rtc_state rtc_memory_state;
#endif

/* Forward declarations */
static void idle_timer_handler(struct k_timer *timer);
static int detect_wake_source(void);
static int load_rtc_state(void);

/**
 * @brief Initialize power management subsystem
 */
int icle_pm_init(void)
{
	int ret;

	if (pm_ctx.initialized) {
		return 0;
	}

	/* Initialize state mutex */
	ret = k_mutex_init(&pm_ctx.state_mutex);
	if (ret != 0) {
		LOG_ERR("Failed to init PM mutex: %d", ret);
		return ret;
	}

	/* Initialize idle timer programmatically */
	k_timer_init(&pm_ctx.idle_timer, idle_timer_handler, NULL);
	pm_ctx.idle_timeout_ms = 0;

	/* Detect wake source */
	ret = detect_wake_source();
	if (ret < 0) {
		LOG_WRN("Could not detect wake source: %d", ret);
		pm_ctx.wake_source = ICLE_WAKE_UNKNOWN;
	}

	/* Load RTC state if valid */
	ret = load_rtc_state();
	if (ret == 0) {
		pm_ctx.rtc_state_valid = true;
		pm_ctx.rtc_state.boot_count++;
		LOG_INF("RTC state loaded, boot_count=%u, last_mode=%u",
			pm_ctx.rtc_state.boot_count,
			pm_ctx.rtc_state.last_mode);
	} else {
		/* First boot or corrupted RTC - initialize fresh */
		pm_ctx.rtc_state_valid = false;
		memset(&pm_ctx.rtc_state, 0, sizeof(pm_ctx.rtc_state));
		pm_ctx.rtc_state.magic = RTC_STATE_MAGIC;
		pm_ctx.rtc_state.boot_count = 1;
		LOG_INF("Fresh boot, initializing RTC state");
	}

#if DT_NODE_HAS_STATUS(BUTTON_NODE, okay)
	if (!gpio_is_ready_dt(&button_gpio)) {
		LOG_WRN("Button GPIO not ready for wake config");
	}
#endif

	pm_ctx.initialized = true;
	LOG_INF("Power management initialized, wake_source=%s",
		icle_pm_wake_source_name(pm_ctx.wake_source));

	return 0;
}

/**
 * @brief Detect the wake source for current boot
 */
static int detect_wake_source(void)
{
#ifdef CONFIG_SOC_SERIES_ESP32
	esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();

	switch (cause) {
	case ESP_SLEEP_WAKEUP_EXT0:
	case ESP_SLEEP_WAKEUP_EXT1:
	case ESP_SLEEP_WAKEUP_GPIO:
		pm_ctx.wake_source = ICLE_WAKE_BUTTON;
		break;
	case ESP_SLEEP_WAKEUP_TIMER:
		pm_ctx.wake_source = ICLE_WAKE_TIMER;
		break;
	case ESP_SLEEP_WAKEUP_UNDEFINED:
	default:
		/* Check reset reason for more details */
		RESET_REASON reset_reason = rtc_get_reset_reason(0);
		if (reset_reason == POWERON_RESET || reset_reason == RTCWDT_RTC_RESET) {
			pm_ctx.wake_source = ICLE_WAKE_RESET;
		} else {
			pm_ctx.wake_source = ICLE_WAKE_UNKNOWN;
		}
		break;
	}

	return 0;
#else
	/* Non-ESP32: assume power-on reset */
	pm_ctx.wake_source = ICLE_WAKE_RESET;
	return 0;
#endif
}

/**
 * @brief Load RTC state from RTC memory
 */
static int load_rtc_state(void)
{
	if (rtc_memory_state.magic != RTC_STATE_MAGIC) {
		LOG_DBG("RTC state magic invalid: 0x%08x", rtc_memory_state.magic);
		return -EINVAL;
	}

	memcpy(&pm_ctx.rtc_state, &rtc_memory_state, sizeof(pm_ctx.rtc_state));
	return 0;
}

/**
 * @brief Get the wake source for current boot
 */
enum icle_wake_source icle_pm_get_wake_source(void)
{
	return pm_ctx.wake_source;
}

/**
 * @brief Get RTC-preserved state
 */
int icle_pm_get_rtc_state(struct icle_rtc_state *state)
{
	if (state == NULL) {
		return -EINVAL;
	}

	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	k_mutex_lock(&pm_ctx.state_mutex, K_FOREVER);
	memcpy(state, &pm_ctx.rtc_state, sizeof(*state));
	k_mutex_unlock(&pm_ctx.state_mutex);

	return pm_ctx.rtc_state_valid ? 0 : -EINVAL;
}

/**
 * @brief Save state to RTC memory before sleep
 */
int icle_pm_save_rtc_state(const struct icle_rtc_state *state)
{
	if (state == NULL) {
		return -EINVAL;
	}

	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	k_mutex_lock(&pm_ctx.state_mutex, K_FOREVER);

	/* Copy to local state */
	memcpy(&pm_ctx.rtc_state, state, sizeof(pm_ctx.rtc_state));

	/* Ensure magic is set */
	pm_ctx.rtc_state.magic = RTC_STATE_MAGIC;

	/* Copy to RTC memory */
	memcpy(&rtc_memory_state, &pm_ctx.rtc_state, sizeof(rtc_memory_state));

	pm_ctx.rtc_state_valid = true;

	k_mutex_unlock(&pm_ctx.state_mutex);

	LOG_DBG("RTC state saved: mode=%u, boot_count=%u",
		state->last_mode, state->boot_count);

	return 0;
}

/**
 * @brief Configure wake sources for deep sleep
 */
int icle_pm_configure_wake(bool gpio_wake, bool timer_wake, uint32_t timer_ms)
{
	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	k_mutex_lock(&pm_ctx.state_mutex, K_FOREVER);

	pm_ctx.gpio_wake_enabled = gpio_wake;
	pm_ctx.timer_wake_enabled = timer_wake;
	pm_ctx.timer_wake_ms = timer_ms;

	k_mutex_unlock(&pm_ctx.state_mutex);

#ifdef CONFIG_SOC_SERIES_ESP32
	/* Configure ESP32 wake sources */
	if (gpio_wake) {
#if DT_NODE_HAS_STATUS(BUTTON_NODE, okay)
		gpio_num_t gpio_num = button_gpio.pin;

		/* Configure GPIO as RTC GPIO for wake */
		esp_err_t err = esp_sleep_enable_ext0_wakeup(gpio_num, 0);
		if (err != ESP_OK) {
			LOG_ERR("Failed to configure GPIO wake: %d", err);
			return -EIO;
		}
		LOG_INF("GPIO wake enabled on pin %d", gpio_num);
#else
		LOG_WRN("Button GPIO not available for wake");
		return -ENOTSUP;
#endif
	}

	if (timer_wake && timer_ms > 0) {
		esp_err_t err = esp_sleep_enable_timer_wakeup(timer_ms * 1000ULL);
		if (err != ESP_OK) {
			LOG_ERR("Failed to configure timer wake: %d", err);
			return -EIO;
		}
		LOG_INF("Timer wake enabled: %u ms", timer_ms);
	}
#else
	LOG_INF("Wake sources configured (non-ESP32): gpio=%d, timer=%d/%ums",
		gpio_wake, timer_wake, timer_ms);
#endif

	return 0;
}

/**
 * @brief Enter deep sleep
 */
int icle_pm_enter_deep_sleep(void)
{
	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	LOG_INF("Entering deep sleep...");

	/* Stop idle timer if running */
	k_timer_stop(&pm_ctx.idle_timer);

	/* Ensure RTC state is saved */
	k_mutex_lock(&pm_ctx.state_mutex, K_FOREVER);
	memcpy(&rtc_memory_state, &pm_ctx.rtc_state, sizeof(rtc_memory_state));
	k_mutex_unlock(&pm_ctx.state_mutex);

#ifdef CONFIG_SOC_SERIES_ESP32
	/* Configure default wake sources if none configured */
	if (!pm_ctx.gpio_wake_enabled && !pm_ctx.timer_wake_enabled) {
		LOG_WRN("No wake sources configured, enabling GPIO wake");
#if DT_NODE_HAS_STATUS(BUTTON_NODE, okay)
		icle_pm_configure_wake(true, false, 0);
#endif
	}

	/* Small delay to allow log output */
	k_msleep(10);

	/* Enter deep sleep - does not return */
	esp_deep_sleep_start();

	/* Should never reach here */
	LOG_ERR("Deep sleep failed!");
	return -EIO;
#else
	/* Non-ESP32: simulate deep sleep with halt */
	LOG_WRN("Deep sleep not supported on this platform, halting");

	/* Disable interrupts and halt */
	k_sleep(K_FOREVER);

	return -ENOTSUP;
#endif
}

/**
 * @brief Request light sleep for power saving
 */
int icle_pm_light_sleep(uint32_t timeout_ms)
{
	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

#ifdef CONFIG_SOC_SERIES_ESP32
	esp_err_t err;

	/* Configure timer wake for light sleep (0 means sleep indefinitely) */
	if (timeout_ms > 0) {
		err = esp_sleep_enable_timer_wakeup(timeout_ms * 1000ULL);
		if (err != ESP_OK) {
			LOG_ERR("Failed to configure light sleep timer: %d", err);
			return -EIO;
		}
	}

	/* Enter light sleep */
	err = esp_light_sleep_start();
	if (err != ESP_OK) {
		LOG_ERR("Light sleep failed: %d", err);
		return -EIO;
	}

	/* Check wake cause */
	esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
	if (cause == ESP_SLEEP_WAKEUP_TIMER) {
		return -ETIMEDOUT;
	}

	return 0;
#else
	/* Non-ESP32: use regular sleep (0 means sleep indefinitely) */
	if (timeout_ms == 0) {
		k_sleep(K_FOREVER);
	} else {
		k_msleep(timeout_ms);
	}
	return -ETIMEDOUT;
#endif
}

/**
 * @brief Idle timer handler - triggers return to deep sleep
 */
static void idle_timer_handler(struct k_timer *timer)
{
	ARG_UNUSED(timer);

	LOG_INF("Idle timeout expired, requesting deep sleep");

	/* This callback runs in ISR context, so we can't directly
	 * enter deep sleep. Post an event to the app layer instead.
	 * The app layer will handle the graceful shutdown sequence.
	 */

	/* For now, just log - actual integration with app state machine
	 * will happen when icle_app.c is implemented */
}

/**
 * @brief Start idle timeout timer
 */
int icle_pm_start_idle_timer(uint32_t timeout_ms)
{
	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	if (timeout_ms == 0) {
		return -EINVAL;
	}

	k_mutex_lock(&pm_ctx.state_mutex, K_FOREVER);
	pm_ctx.idle_timeout_ms = timeout_ms;
	k_mutex_unlock(&pm_ctx.state_mutex);

	k_timer_start(&pm_ctx.idle_timer, K_MSEC(timeout_ms), K_NO_WAIT);
	LOG_DBG("Idle timer started: %u ms", timeout_ms);

	return 0;
}

/**
 * @brief Reset idle timeout timer
 */
int icle_pm_reset_idle_timer(void)
{
	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	k_mutex_lock(&pm_ctx.state_mutex, K_FOREVER);
	uint32_t timeout = pm_ctx.idle_timeout_ms;
	k_mutex_unlock(&pm_ctx.state_mutex);

	if (timeout > 0) {
		k_timer_start(&pm_ctx.idle_timer, K_MSEC(timeout), K_NO_WAIT);
		LOG_DBG("Idle timer reset");
	}

	return 0;
}

/**
 * @brief Stop idle timeout timer
 */
int icle_pm_stop_idle_timer(void)
{
	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	k_timer_stop(&pm_ctx.idle_timer);
	LOG_DBG("Idle timer stopped");

	return 0;
}

/**
 * @brief Get boot count
 */
uint32_t icle_pm_get_boot_count(void)
{
	if (!pm_ctx.initialized) {
		return 0;
	}

	return pm_ctx.rtc_state.boot_count;
}

/**
 * @brief Get uptime in milliseconds
 */
uint32_t icle_pm_get_uptime_ms(void)
{
	return k_uptime_get_32();
}

/**
 * @brief Get wake source name string
 */
const char *icle_pm_wake_source_name(enum icle_wake_source source)
{
	switch (source) {
	case ICLE_WAKE_UNKNOWN:
		return "unknown";
	case ICLE_WAKE_BUTTON:
		return "button";
	case ICLE_WAKE_TIMER:
		return "timer";
	case ICLE_WAKE_RESET:
		return "reset";
	default:
		return "invalid";
	}
}

/**
 * @brief Update last mode in RTC state
 */
int icle_pm_set_last_mode(uint8_t mode)
{
	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	k_mutex_lock(&pm_ctx.state_mutex, K_FOREVER);
	pm_ctx.rtc_state.last_mode = mode;
	k_mutex_unlock(&pm_ctx.state_mutex);

	return 0;
}

/**
 * @brief Get last mode from RTC state
 */
uint8_t icle_pm_get_last_mode(void)
{
	if (!pm_ctx.initialized || !pm_ctx.rtc_state_valid) {
		return 0;
	}

	return pm_ctx.rtc_state.last_mode;
}

/**
 * @brief Update pending samples count
 */
int icle_pm_set_pending_samples(uint32_t count)
{
	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	k_mutex_lock(&pm_ctx.state_mutex, K_FOREVER);
	pm_ctx.rtc_state.pending_samples = count;
	k_mutex_unlock(&pm_ctx.state_mutex);

	return 0;
}

/**
 * @brief Get pending samples count
 */
uint32_t icle_pm_get_pending_samples(void)
{
	if (!pm_ctx.initialized) {
		return 0;
	}

	return pm_ctx.rtc_state.pending_samples;
}

/**
 * @brief Update last sync time
 */
int icle_pm_set_last_sync_time(uint32_t time)
{
	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	k_mutex_lock(&pm_ctx.state_mutex, K_FOREVER);
	pm_ctx.rtc_state.last_sync_time = time;
	k_mutex_unlock(&pm_ctx.state_mutex);

	return 0;
}

/**
 * @brief Get last sync time
 */
uint32_t icle_pm_get_last_sync_time(void)
{
	if (!pm_ctx.initialized) {
		return 0;
	}

	return pm_ctx.rtc_state.last_sync_time;
}

/**
 * @brief Prepare for deep sleep (graceful shutdown helper)
 *
 * This function should be called before entering deep sleep to ensure
 * all state is properly saved. It handles:
 * - Saving current mode to RTC memory
 * - Configuring wake sources
 * - Final state preservation
 *
 * @param mode Current operating mode to save
 * @param enable_gpio_wake Enable GPIO button wake
 * @param enable_timer_wake Enable timer wake
 * @param timer_ms Timer interval if timer wake enabled
 * @return 0 on success, negative errno on failure
 */
int icle_pm_prepare_deep_sleep(uint8_t mode, bool enable_gpio_wake,
			       bool enable_timer_wake, uint32_t timer_ms)
{
	int ret;

	if (!pm_ctx.initialized) {
		return -ENODEV;
	}

	LOG_INF("Preparing for deep sleep: mode=%u, gpio_wake=%d, timer_wake=%d",
		mode, enable_gpio_wake, enable_timer_wake);

	/* Update RTC state */
	k_mutex_lock(&pm_ctx.state_mutex, K_FOREVER);
	pm_ctx.rtc_state.last_mode = mode;
	pm_ctx.rtc_state.sleep_duration_ms = timer_ms;
	k_mutex_unlock(&pm_ctx.state_mutex);

	/* Save RTC state */
	ret = icle_pm_save_rtc_state(&pm_ctx.rtc_state);
	if (ret < 0) {
		LOG_ERR("Failed to save RTC state: %d", ret);
		return ret;
	}

	/* Configure wake sources */
	ret = icle_pm_configure_wake(enable_gpio_wake, enable_timer_wake, timer_ms);
	if (ret < 0) {
		LOG_ERR("Failed to configure wake sources: %d", ret);
		return ret;
	}

	return 0;
}
