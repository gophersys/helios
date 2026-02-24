/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE Button Handler
 *
 * Handles button input with debouncing and pattern detection.
 * Supports: short press, long press, double press, held detection.
 * Uses programmatic Zephyr APIs (no K_* macros).
 */

#ifndef ICLE_BUTTON_H_
#define ICLE_BUTTON_H_

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Button event types
 */
enum icle_button_event {
	ICLE_BTN_EVENT_NONE = 0,
	ICLE_BTN_EVENT_PRESSED,       /* Button pressed (debounced) */
	ICLE_BTN_EVENT_RELEASED,      /* Button released */
	ICLE_BTN_EVENT_SHORT_PRESS,   /* Press < long_threshold */
	ICLE_BTN_EVENT_LONG_PRESS,    /* Press >= long_threshold */
	ICLE_BTN_EVENT_DOUBLE_PRESS,  /* Two presses within double_window */
	ICLE_BTN_EVENT_HELD,          /* Button held for held_threshold */
};

/**
 * @brief Button callback type
 *
 * @param event The button event
 * @param hold_time_ms How long button was held (for press events)
 * @param user_data User-provided context
 */
typedef void (*icle_button_callback_t)(enum icle_button_event event,
				       uint32_t hold_time_ms,
				       void *user_data);

/**
 * @brief Button timing configuration
 */
struct icle_button_config {
	uint32_t debounce_ms;       /* Debounce time (default: 20ms) */
	uint32_t long_press_ms;     /* Long press threshold (default: 2000ms) */
	uint32_t double_press_ms;   /* Double press window (default: 300ms) */
	uint32_t held_threshold_ms; /* Held event threshold (default: 3000ms) */
};

/**
 * @brief Initialize button handler
 *
 * Configures GPIO interrupt and creates work queue items programmatically.
 * Does NOT use K_WORK_DEFINE or similar macros.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_button_init(void);

/**
 * @brief Deinitialize button handler
 *
 * Disables GPIO interrupt and releases resources.
 *
 * @return 0 on success, negative errno on failure
 */
int icle_button_deinit(void);

/**
 * @brief Set button timing configuration
 *
 * @param config Timing configuration (NULL for defaults)
 * @return 0 on success, -EINVAL if values invalid
 */
int icle_button_set_config(const struct icle_button_config *config);

/**
 * @brief Get current button configuration
 *
 * @param config Pointer to store configuration
 * @return 0 on success
 */
int icle_button_get_config(struct icle_button_config *config);

/**
 * @brief Register button event callback
 *
 * Multiple callbacks can be registered.
 *
 * @param callback Callback function
 * @param user_data User context passed to callback
 * @return 0 on success, -ENOMEM if too many callbacks
 */
int icle_button_register_callback(icle_button_callback_t callback,
				  void *user_data);

/**
 * @brief Unregister button event callback
 *
 * @param callback Callback to remove
 */
void icle_button_unregister_callback(icle_button_callback_t callback);

/**
 * @brief Check if button is currently pressed
 *
 * @return true if button is pressed
 */
bool icle_button_is_pressed(void);

/**
 * @brief Get button press duration
 *
 * @return Duration in ms if pressed, 0 if not pressed
 */
uint32_t icle_button_get_hold_time(void);

/**
 * @brief Wait for button event
 *
 * Blocks until specified event occurs or timeout.
 *
 * @param event_mask Events to wait for (ORed together)
 * @param timeout_ms Timeout in ms, K_FOREVER for indefinite
 * @return Event that occurred, or ICLE_BTN_EVENT_NONE on timeout
 */
enum icle_button_event icle_button_wait_event(uint32_t event_mask,
					      uint32_t timeout_ms);

/**
 * @brief Enable/disable button handling
 *
 * When disabled, GPIO interrupts are still processed but no events
 * are generated. Useful during critical operations.
 *
 * @param enable true to enable event generation
 */
void icle_button_set_enabled(bool enable);

/**
 * @brief Check if button handling is enabled
 *
 * @return true if events are being generated
 */
bool icle_button_is_enabled(void);

/**
 * @brief Configure button as wake source
 *
 * Sets up button GPIO to wake from deep sleep.
 *
 * @param enable true to enable wake capability
 * @return 0 on success, negative errno on failure
 */
int icle_button_configure_wake(bool enable);

/**
 * @brief Get event name string
 *
 * @param event Button event
 * @return Event name string
 */
const char *icle_button_event_name(enum icle_button_event event);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_BUTTON_H_ */
