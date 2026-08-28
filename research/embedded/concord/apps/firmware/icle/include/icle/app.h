// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Application State Machine
 *
 * Main application controller managing operating modes and state transitions.
 * Fully async event-driven architecture - no blocking timeouts anywhere.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#ifndef ICLE_APP_H_
#define ICLE_APP_H_

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>
#include "icle/config.h"
#include "icle/types.h"

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
 *
 * Core rules:
 * - Only K_FOREVER and K_NO_WAIT for any blocking call
 * - All timeouts via k_work_delayable that post events when fired
 * - WiFi is fully async - callbacks post events
 * - Single event loop in main thread processes all events
 */
enum icle_app_event {
	/* Button events */
	ICLE_EVENT_BUTTON_SHORT       = BIT(0),   /* Short button press */
	ICLE_EVENT_BUTTON_LONG        = BIT(1),   /* Long button press (>=2s) */
	ICLE_EVENT_BUTTON_DOUBLE      = BIT(2),   /* Double press */
	ICLE_EVENT_BUTTON_HELD_3S     = BIT(3),   /* Button held 3+ seconds */

	/* WiFi events (legacy - kept for compatibility) */
	ICLE_EVENT_WIFI_CONNECTED     = BIT(4),   /* WiFi connection established */
	ICLE_EVENT_WIFI_DISCONNECTED  = BIT(5),   /* WiFi disconnected */

	/* Config/control events */
	ICLE_EVENT_CONFIG_TIMEOUT     = BIT(6),   /* Config mode timeout */
	ICLE_EVENT_CRITICAL_ERROR     = BIT(7),   /* Critical error occurred */
	ICLE_EVENT_SHUTDOWN_REQUEST   = BIT(8),   /* Shutdown requested */
	ICLE_EVENT_SYNC_COMPLETE      = BIT(9),   /* HTTP sync completed */
	ICLE_EVENT_BUTTON_CONFIG      = BIT(10),  /* Config mode button trigger */
	ICLE_EVENT_SHUTDOWN           = BIT(11),  /* Force shutdown event */
	ICLE_EVENT_STORAGE_FULL       = BIT(12),  /* SD card storage full */

	/* Async WiFi events (new) */
	ICLE_EVENT_WIFI_SCAN_DONE     = BIT(13),  /* WiFi scan completed */
	ICLE_EVENT_WIFI_SCAN_FAILED   = BIT(14),  /* WiFi scan failed */
	ICLE_EVENT_WIFI_CONNECT_FAILED = BIT(15), /* WiFi connect attempt failed */
	ICLE_EVENT_WIFI_IP_ACQUIRED   = BIT(16),  /* IP address obtained */
	ICLE_EVENT_WIFI_CONNECT_TIMEOUT = BIT(17), /* WiFi connect timed out */

	/* Operational events (new) */
	ICLE_EVENT_HEARTBEAT_DUE      = BIT(18),  /* Time to send heartbeat */
	ICLE_EVENT_BOOT_DECIDE_TIMEOUT = BIT(19), /* Boot decide window expired */
	ICLE_EVENT_SHUTDOWN_TIMEOUT   = BIT(20),  /* Shutdown cleanup timed out */
	ICLE_EVENT_WRITER_DONE        = BIT(21),  /* Log writer finished flush */
	ICLE_EVENT_READY_FOR_SLEEP    = BIT(22),  /* All cleanup done, can sleep */
	ICLE_EVENT_TIMER_WAKE         = BIT(23),  /* Woke from timer */
};

/* All events mask for k_event_wait */
#define ICLE_EVENT_ALL 0x00FFFFFF

/**
 * @brief Application runtime context
 */
struct icle_app_ctx {
	enum icle_app_state state;
	enum icle_app_state prev_state;
	struct icle_config config;
	enum icle_wake_source wake_source;
	uint32_t boot_count;
	uint32_t state_enter_time;
	bool wifi_connected;
	bool storage_ready;
};

/**
 * @brief Initialize the application state machine
 * @return 0 on success, negative errno on failure
 */
int icle_app_init(void);

/**
 * @brief Run the application event loop (never returns)
 *
 * This IS the main event loop. Runs on the calling thread (main).
 * Uses k_event_wait(K_FOREVER) - no busy waits, no polling.
 */
void icle_app_run(void) __attribute__((noreturn));

/**
 * @brief Get current application state
 * @return Current state
 */
enum icle_app_state icle_app_get_state(void);

/**
 * @brief Get application context (read-only)
 * @return Pointer to application context
 */
const struct icle_app_ctx *icle_app_get_ctx(void);

/**
 * @brief Post an event to the application state machine
 *
 * Thread-safe. Can be called from ISR context, work handlers,
 * or any thread. The event loop will wake and process.
 *
 * @param event Event flags to post (can be ORed together)
 */
void icle_app_post_event(uint32_t event);

/**
 * @brief Request mode change via event posting
 * @param target_state Requested target state
 * @return 0 if request accepted, -EINVAL if invalid transition
 */
int icle_app_request_mode(enum icle_app_state target_state);

/**
 * @brief Request shutdown via event posting
 * @param enter_deep_sleep true to enter deep sleep, false to halt
 * @return 0 on success
 */
int icle_app_shutdown(bool enter_deep_sleep);

/**
 * @brief Get state name string
 * @param state State to get name for
 * @return State name string
 */
const char *icle_app_state_name(enum icle_app_state state);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_APP_H_ */
