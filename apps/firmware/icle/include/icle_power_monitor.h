/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE Power Management
 *
 * Manages device power states including deep sleep and wake sources.
 * Separate from icle_power.h which handles INA209 power monitoring.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#ifndef ICLE_POWER_MONITOR_H_
#define ICLE_POWER_MONITOR_H_

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Wake source identification
 */
enum icle_wake_source {
	ICLE_WAKE_UNKNOWN = 0,
	ICLE_WAKE_BUTTON,       /* GPIO button press */
	ICLE_WAKE_TIMER,        /* RTC timer */
	ICLE_WAKE_RESET,        /* Power-on or reset */
};

/**
 * @brief RTC-preserved state across deep sleep
 */
struct icle_rtc_state {
	uint32_t magic;             /* Validation magic number */
	uint8_t last_mode;          /* Last operating mode before sleep */
	uint32_t boot_count;        /* Number of boots/wakes */
	uint32_t last_sync_time;    /* Last successful sync timestamp */
	uint32_t pending_samples;   /* Samples not yet synced */
	uint32_t sleep_duration_ms; /* Requested sleep duration */
};

#define ICLE_RTC_STATE_MAGIC 0x49434C45  /* "ICLE" */

/**
 * @brief Initialize power management subsystem
 *
 * Configures wake sources and loads RTC state if valid.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_pm_init(void);

/**
 * @brief Get the wake source for current boot
 *
 * @return Wake source that caused current boot
 */
enum icle_wake_source icle_pm_get_wake_source(void);

/**
 * @brief Get RTC-preserved state
 *
 * @param state Pointer to store RTC state
 * @return 0 on success, -EINVAL if state invalid/corrupt
 */
int icle_pm_get_rtc_state(struct icle_rtc_state *state);

/**
 * @brief Save state to RTC memory before sleep
 *
 * @param state State to preserve
 * @return 0 on success, negative errno on failure
 */
int icle_pm_save_rtc_state(const struct icle_rtc_state *state);

/**
 * @brief Configure wake sources
 *
 * @param gpio_wake Enable GPIO button wake
 * @param timer_wake Enable RTC timer wake
 * @param timer_ms Timer interval in ms (if timer_wake enabled)
 * @return 0 on success, negative errno on failure
 */
int icle_pm_configure_wake(bool gpio_wake, bool timer_wake, uint32_t timer_ms);

/**
 * @brief Enter deep sleep
 *
 * This function does not return on success - device enters deep sleep.
 * Caller must ensure all pending operations are complete before calling.
 *
 * @return Negative errno on failure (only returns on error)
 */
int icle_pm_enter_deep_sleep(void);

/**
 * @brief Request light sleep for power saving
 *
 * Enters light sleep while waiting for events. WiFi stays connected
 * in light sleep mode (automatic modem sleep).
 *
 * @param timeout_ms Maximum sleep duration, K_FOREVER for indefinite
 * @return 0 on normal wake, -ETIMEDOUT on timeout
 */
int icle_pm_light_sleep(uint32_t timeout_ms);

/**
 * @brief Get boot count
 *
 * @return Number of boots since RTC state was last cleared
 */
uint32_t icle_pm_get_boot_count(void);

/**
 * @brief Get uptime in milliseconds
 *
 * @return Uptime since boot in ms
 */
uint32_t icle_pm_get_uptime_ms(void);

/**
 * @brief Get wake source name string
 *
 * @param source Wake source
 * @return Wake source name string
 */
const char *icle_pm_wake_source_name(enum icle_wake_source source);

/**
 * @brief Start idle timeout timer
 *
 * When the timer expires, the system will request a return to deep sleep.
 * Use icle_pm_reset_idle_timer() on activity to prevent sleep.
 *
 * @param timeout_ms Timeout in milliseconds
 * @return 0 on success, negative errno on failure
 */
int icle_pm_start_idle_timer(uint32_t timeout_ms);

/**
 * @brief Reset idle timeout timer
 *
 * Call this on user activity to prevent automatic sleep.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_pm_reset_idle_timer(void);

/**
 * @brief Stop idle timeout timer
 *
 * @return 0 on success, negative errno on failure
 */
int icle_pm_stop_idle_timer(void);

/**
 * @brief Set last operating mode in RTC state
 *
 * @param mode Operating mode to save
 * @return 0 on success, negative errno on failure
 */
int icle_pm_set_last_mode(uint8_t mode);

/**
 * @brief Get last operating mode from RTC state
 *
 * @return Last mode, or 0 if not available
 */
uint8_t icle_pm_get_last_mode(void);

/**
 * @brief Set pending samples count in RTC state
 *
 * @param count Number of pending samples
 * @return 0 on success, negative errno on failure
 */
int icle_pm_set_pending_samples(uint32_t count);

/**
 * @brief Get pending samples count from RTC state
 *
 * @return Pending sample count, or 0 if not available
 */
uint32_t icle_pm_get_pending_samples(void);

/**
 * @brief Set last sync time in RTC state
 *
 * @param time Sync timestamp (e.g., uptime or epoch)
 * @return 0 on success, negative errno on failure
 */
int icle_pm_set_last_sync_time(uint32_t time);

/**
 * @brief Get last sync time from RTC state
 *
 * @return Last sync time, or 0 if not available
 */
uint32_t icle_pm_get_last_sync_time(void);

/**
 * @brief Prepare for deep sleep (graceful shutdown helper)
 *
 * Saves state to RTC memory and configures wake sources.
 * Call this before icle_pm_enter_deep_sleep().
 *
 * @param mode Current operating mode to save
 * @param enable_gpio_wake Enable GPIO button wake
 * @param enable_timer_wake Enable timer wake
 * @param timer_ms Timer interval if timer wake enabled
 * @return 0 on success, negative errno on failure
 */
int icle_pm_prepare_deep_sleep(uint8_t mode, bool enable_gpio_wake,
			       bool enable_timer_wake, uint32_t timer_ms);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_POWER_MONITOR_H_ */
