// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Power Management
 *
 * Deep sleep support with ZMS state persistence.
 * ESP32 deep sleep is a full power-off - only RTC slow memory (8KB)
 * and flash (ZMS) survive. State must be saved before sleep.
 */

#ifndef ICLE_SERVICES_PM_H_
#define ICLE_SERVICES_PM_H_

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>
#include "icle/types.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Scheduled action after wake */
enum icle_pm_action {
	ICLE_PM_ACTION_IDLE = 0,
	ICLE_PM_ACTION_HEARTBEAT,
	ICLE_PM_ACTION_SYNC,
};

/** Persistent state structure (saved to ZMS before sleep) */
struct icle_pm_persist_state {
	uint32_t magic;              /* 0x49434C45 "ICLE" */
	uint32_t version;            /* 1 */
	uint32_t device_state;       /* icle_app_state before sleep */
	uint32_t scheduled_action;   /* icle_pm_action */
	uint32_t wake_count;
	uint32_t last_wake_cause;
	int64_t  last_sleep_time;
	uint32_t heartbeat_interval_s;
	uint32_t reserved[3];
};

#define ICLE_PM_STATE_MAGIC   0x49434C45 /* "ICLE" */
#define ICLE_PM_STATE_VERSION 1

/**
 * @brief Initialize power management
 * @return 0 on success, negative errno on failure
 */
int icle_pm_init(void);

/**
 * @brief Detect wake cause
 * @return Wake source enum
 */
enum icle_wake_source icle_pm_detect_wake_cause(void);

/**
 * @brief Get boot count (survives deep sleep via RTC_DATA_ATTR)
 * @return Boot count
 */
uint32_t icle_pm_get_boot_count(void);

/**
 * @brief Save state to ZMS before deep sleep
 * @param state State to persist
 * @return 0 on success, negative errno on failure
 */
int icle_pm_save_state(const struct icle_pm_persist_state *state);

/**
 * @brief Restore state from ZMS after deep sleep wake
 * @param state Buffer to load state into
 * @return 0 on success, -ENOENT if no saved state, negative errno on failure
 */
int icle_pm_restore_state(struct icle_pm_persist_state *state);

/**
 * @brief Configure wakeup sources for deep sleep
 * @param timer_sec Timer wakeup in seconds (0 to disable)
 * @param button_gpio_mask GPIO mask for button wakeup (0 to disable)
 * @return 0 on success, negative errno on failure
 */
int icle_pm_configure_wakeup(uint32_t timer_sec, uint32_t button_gpio_mask);

/**
 * @brief Enter deep sleep (never returns)
 */
void icle_pm_enter_deep_sleep(void) __attribute__((noreturn));

#ifdef __cplusplus
}
#endif

#endif /* ICLE_SERVICES_PM_H_ */
