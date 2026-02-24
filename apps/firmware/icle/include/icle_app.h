/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE Application State Machine
 *
 * Main application controller managing operating modes and state transitions.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#ifndef ICLE_APP_H_
#define ICLE_APP_H_

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Application operating states
 */
enum icle_app_state {
	ICLE_STATE_BOOT,          /* Initial boot, hardware init */
	ICLE_STATE_BOOT_DECIDE,   /* Waiting for button to determine mode */
	ICLE_STATE_CONFIG,        /* Configuration mode (WiFi STA active) */
	ICLE_STATE_LOGGER,        /* Active logging mode */
	ICLE_STATE_SHUTDOWN,      /* Graceful shutdown in progress */
	ICLE_STATE_DEEP_SLEEP,    /* Entering deep sleep */
	ICLE_STATE_ERROR,         /* Critical error state */
};

/**
 * @brief Application events (used with k_event)
 */
enum icle_app_event {
	ICLE_EVENT_BUTTON_SHORT     = BIT(0),  /* Short button press */
	ICLE_EVENT_BUTTON_LONG      = BIT(1),  /* Long button press (>=2s) */
	ICLE_EVENT_BUTTON_DOUBLE    = BIT(2),  /* Double press */
	ICLE_EVENT_BUTTON_HELD_3S   = BIT(3),  /* Button held 3+ seconds */
	ICLE_EVENT_WIFI_CONNECTED   = BIT(4),  /* WiFi connection established */
	ICLE_EVENT_WIFI_DISCONNECTED = BIT(5), /* WiFi disconnected */
	ICLE_EVENT_CONFIG_TIMEOUT   = BIT(6),  /* Config mode timeout */
	ICLE_EVENT_CRITICAL_ERROR   = BIT(7),  /* Critical error occurred */
	ICLE_EVENT_SHUTDOWN_REQUEST = BIT(8),  /* Shutdown requested */
	ICLE_EVENT_SYNC_COMPLETE    = BIT(9),  /* HTTP sync completed */
};

/**
 * @brief Application configuration (loaded from NVS)
 */
struct icle_app_config {
	char wifi_ssid[33];
	char wifi_psk[65];
	char device_id[32];
	char sync_url[128];
	uint32_t sample_interval_ms;
	uint32_t sync_interval_ms;
	uint8_t log_format;
	uint8_t flags;
};

/**
 * @brief Application runtime context
 */
struct icle_app_ctx {
	enum icle_app_state state;
	enum icle_app_state prev_state;
	struct icle_app_config config;
	uint32_t boot_count;
	uint32_t state_enter_time;
	bool wifi_connected;
	bool storage_ready;
};

/**
 * @brief Initialize the application state machine
 *
 * Creates required threads, queues, and synchronization primitives.
 * Does NOT use K_THREAD_DEFINE or similar macros.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_app_init(void);

/**
 * @brief Start the application state machine
 *
 * Begins state machine execution. Call after all modules initialized.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_app_start(void);

/**
 * @brief Get current application state
 *
 * @return Current state
 */
enum icle_app_state icle_app_get_state(void);

/**
 * @brief Get application context (read-only)
 *
 * @return Pointer to application context
 */
const struct icle_app_ctx *icle_app_get_ctx(void);

/**
 * @brief Post an event to the application state machine
 *
 * Thread-safe event posting.
 *
 * @param event Event flags to post (can be ORed together)
 */
void icle_app_post_event(uint32_t event);

/**
 * @brief Request mode change
 *
 * Requests transition to a new operating mode. The state machine
 * will validate and execute the transition if allowed.
 *
 * @param target_state Requested target state
 * @return 0 if request accepted, -EINVAL if invalid transition
 */
int icle_app_request_mode(enum icle_app_state target_state);

/**
 * @brief Request shutdown
 *
 * Initiates graceful shutdown sequence:
 * 1. Flush pending logs
 * 2. Complete/cancel HTTP sync
 * 3. Disconnect WiFi
 * 4. Enter deep sleep
 *
 * @param enter_deep_sleep true to enter deep sleep, false to halt
 * @return 0 on success
 */
int icle_app_shutdown(bool enter_deep_sleep);

/**
 * @brief Load configuration from NVS
 *
 * @param config Pointer to store loaded configuration
 * @return 0 on success, -ENOENT if not found, negative errno on error
 */
int icle_app_load_config(struct icle_app_config *config);

/**
 * @brief Save configuration to NVS
 *
 * @param config Configuration to save
 * @return 0 on success, negative errno on failure
 */
int icle_app_save_config(const struct icle_app_config *config);

/**
 * @brief Get default configuration
 *
 * @param config Pointer to store default configuration
 */
void icle_app_default_config(struct icle_app_config *config);

/**
 * @brief Get state name string
 *
 * @param state State to get name for
 * @return State name string
 */
const char *icle_app_state_name(enum icle_app_state state);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_APP_H_ */
