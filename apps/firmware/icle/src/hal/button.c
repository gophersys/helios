// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Button Handler Implementation
 *
 * GPIO interrupt-driven button handling with debouncing and pattern detection.
 * Supports: short press, long press, double press, and held detection.
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>

#ifdef CONFIG_SOC_SERIES_ESP32
#include <esp_sleep.h>
#include <hal/gpio_types.h>
#endif

#include "hal/button.h"

LOG_MODULE_REGISTER(icle_button, CONFIG_LOG_DEFAULT_LEVEL);

/* Button GPIO configuration from devicetree */
#if DT_NODE_EXISTS(DT_ALIAS(sw0))
#define BUTTON_NODE DT_ALIAS(sw0)
#elif DT_NODE_EXISTS(DT_NODELABEL(user_button))
#define BUTTON_NODE DT_NODELABEL(user_button)
#elif DT_NODE_EXISTS(DT_NODELABEL(boot_button))
#define BUTTON_NODE DT_NODELABEL(boot_button)
#else
/* Fallback: Use GPIO0 pin 0 for ESP32 BOOT button */
#define BUTTON_GPIO_PORT DT_NODELABEL(gpio0)
#define BUTTON_GPIO_PIN  0
#define BUTTON_GPIO_FLAGS (GPIO_INPUT | GPIO_PULL_UP)
#define BUTTON_ACTIVE_LOW 1
#endif

#ifdef BUTTON_NODE
static const struct gpio_dt_spec button_spec = GPIO_DT_SPEC_GET(BUTTON_NODE, gpios);
#define BUTTON_ACTIVE_LOW (button_spec.dt_flags & GPIO_ACTIVE_LOW)
#else
static const struct device *button_port;
#endif

/* Default timing configuration */
#define DEFAULT_DEBOUNCE_MS       50
#define DEFAULT_LONG_PRESS_MS     2000
#define DEFAULT_DOUBLE_PRESS_MS   300
#define DEFAULT_HELD_THRESHOLD_MS 3000

/* Maximum number of registered callbacks */
#define MAX_CALLBACKS 4

/* Callback registration */
struct callback_entry {
	icle_button_callback_t callback;
	void *user_data;
};

/* Module state */
struct button_state {
	/* Configuration */
	struct icle_button_config config;

	/* GPIO callback */
	struct gpio_callback gpio_cb;

	/* Work items for deferred processing */
	struct k_work_delayable debounce_work;
	struct k_work_delayable long_press_work;
	struct k_work_delayable held_work;
	struct k_work_delayable double_press_work;

	/* Event signaling */
	struct k_event events;

	/* Button state tracking */
	bool is_pressed;
	bool is_enabled;
	bool is_initialized;
	int64_t press_start_time;
	int64_t last_release_time;
	uint8_t press_count;

	/* Registered callbacks */
	struct callback_entry callbacks[MAX_CALLBACKS];
	uint8_t callback_count;

	/* Mutex for thread safety */
	struct k_mutex state_mutex;
};

static struct button_state btn_state;

/* Forward declarations */
static void gpio_callback_handler(const struct device *dev,
				  struct gpio_callback *cb, uint32_t pins);
static void debounce_work_handler(struct k_work *work);
static void long_press_work_handler(struct k_work *work);
static void held_work_handler(struct k_work *work);
static void double_press_work_handler(struct k_work *work);
static void notify_callbacks(enum icle_button_event event, uint32_t hold_time_ms);
static int read_button_state(void);

/**
 * @brief Read the current physical button state
 * @return 1 if pressed, 0 if not pressed, negative on error
 */
static int read_button_state(void)
{
	int val;

#ifdef BUTTON_NODE
	val = gpio_pin_get_dt(&button_spec);
#else
	val = gpio_pin_get(button_port, BUTTON_GPIO_PIN);
	if (val >= 0 && BUTTON_ACTIVE_LOW)
		val = !val;
#endif

	return val;
}

/**
 * @brief Notify all registered callbacks of an event
 */
static void notify_callbacks(enum icle_button_event event, uint32_t hold_time_ms)
{
	k_mutex_lock(&btn_state.state_mutex, K_FOREVER);

	for (int i = 0; i < btn_state.callback_count; i++) {
		if (btn_state.callbacks[i].callback) {
			btn_state.callbacks[i].callback(event, hold_time_ms,
							btn_state.callbacks[i].user_data);
		}
	}

	k_mutex_unlock(&btn_state.state_mutex);
}

/**
 * @brief Post event to k_event and notify callbacks
 */
static void post_event(enum icle_button_event event, uint32_t hold_time_ms)
{
	if (!btn_state.is_enabled)
		return;

	LOG_DBG("Button event: %s (hold=%u ms)",
		icle_button_event_name(event), hold_time_ms);

	/* Post to k_event for waiters */
	k_event_post(&btn_state.events, BIT(event));

	/* Notify registered callbacks */
	notify_callbacks(event, hold_time_ms);
}

/**
 * @brief GPIO interrupt callback
 */
static void gpio_callback_handler(const struct device *dev,
				  struct gpio_callback *cb, uint32_t pins)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	/* Schedule debounce work - this handles both press and release */
	k_work_reschedule(&btn_state.debounce_work,
			  K_MSEC(btn_state.config.debounce_ms));
}

/**
 * @brief Debounce work handler - processes button state after debounce period
 */
static void debounce_work_handler(struct k_work *work)
{
	int current_state;
	bool pressed;
	int64_t now;

	ARG_UNUSED(work);

	current_state = read_button_state();
	if (current_state < 0) {
		LOG_ERR("Failed to read button state: %d", current_state);
		return;
	}

	pressed = (current_state == 1);
	now = k_uptime_get();

	if (pressed && !btn_state.is_pressed) {
		/* Button just pressed (debounced) */
		btn_state.is_pressed = true;
		btn_state.press_start_time = now;
		btn_state.press_count++;

		post_event(ICLE_BTN_EVENT_PRESSED, 0);

		/* Cancel any pending double-press detection */
		k_work_cancel_delayable(&btn_state.double_press_work);

		/* Schedule long press detection */
		k_work_schedule(&btn_state.long_press_work,
				K_MSEC(btn_state.config.long_press_ms));

		/* Schedule held detection */
		k_work_schedule(&btn_state.held_work,
				K_MSEC(btn_state.config.held_threshold_ms));

	} else if (!pressed && btn_state.is_pressed) {
		/* Button just released (debounced) */
		uint32_t hold_time = (uint32_t)(now - btn_state.press_start_time);

		btn_state.is_pressed = false;

		/* Cancel scheduled long press and held work */
		k_work_cancel_delayable(&btn_state.long_press_work);
		k_work_cancel_delayable(&btn_state.held_work);

		post_event(ICLE_BTN_EVENT_RELEASED, hold_time);

		/* Determine press type based on hold duration */
		if (hold_time >= btn_state.config.held_threshold_ms) {
			/* Already reported as HELD event, nothing more to do */
		} else if (hold_time >= btn_state.config.long_press_ms) {
			/* Long press (2-3 seconds) */
			post_event(ICLE_BTN_EVENT_LONG_PRESS, hold_time);
			btn_state.press_count = 0;
		} else {
			/* Short press - check for double press */
			int64_t time_since_last = now - btn_state.last_release_time;

			if (btn_state.press_count >= 2 &&
			    time_since_last < btn_state.config.double_press_ms) {
				/* Double press detected */
				post_event(ICLE_BTN_EVENT_DOUBLE_PRESS, hold_time);
				btn_state.press_count = 0;
			} else {
				/* Schedule delayed short press event
				 * (wait for possible second press)
				 */
				k_work_schedule(&btn_state.double_press_work,
						K_MSEC(btn_state.config.double_press_ms));
			}
		}

		btn_state.last_release_time = now;
	}
}

/**
 * @brief Long press work handler - fires when button held for long_press_ms
 */
static void long_press_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	if (btn_state.is_pressed) {
		int64_t now = k_uptime_get();
		uint32_t hold_time = (uint32_t)(now - btn_state.press_start_time);

		/* Long press threshold reached while still held */
		LOG_INF("Long press detected (%u ms)", hold_time);
		post_event(ICLE_BTN_EVENT_LONG_PRESS, hold_time);

		/* Reset press count since we've consumed this press */
		btn_state.press_count = 0;
	}
}

/**
 * @brief Held work handler - fires when button held for held_threshold_ms
 */
static void held_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	if (btn_state.is_pressed) {
		int64_t now = k_uptime_get();
		uint32_t hold_time = (uint32_t)(now - btn_state.press_start_time);

		/* Held threshold reached */
		LOG_INF("Button held for %u ms (force shutdown threshold)", hold_time);
		post_event(ICLE_BTN_EVENT_HELD, hold_time);
	}
}

/**
 * @brief Double press work handler - fires if no second press detected
 */
static void double_press_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	/* If we get here, no second press occurred within the window */
	if (btn_state.press_count == 1 && !btn_state.is_pressed) {
		uint32_t hold_time = (uint32_t)(btn_state.last_release_time -
						btn_state.press_start_time);

		post_event(ICLE_BTN_EVENT_SHORT_PRESS, hold_time);
		btn_state.press_count = 0;
	}
}

int icle_button_init(void)
{
	int ret;
	int initial;

	if (btn_state.is_initialized) {
		LOG_WRN("Button handler already initialized");
		return -EALREADY;
	}

	/* Initialize mutex */
	k_mutex_init(&btn_state.state_mutex);

	/* Initialize k_event for button events */
	k_event_init(&btn_state.events);

	/* Set default configuration */
	btn_state.config.debounce_ms = DEFAULT_DEBOUNCE_MS;
	btn_state.config.long_press_ms = DEFAULT_LONG_PRESS_MS;
	btn_state.config.double_press_ms = DEFAULT_DOUBLE_PRESS_MS;
	btn_state.config.held_threshold_ms = DEFAULT_HELD_THRESHOLD_MS;

	/* Initialize work items programmatically */
	k_work_init_delayable(&btn_state.debounce_work, debounce_work_handler);
	k_work_init_delayable(&btn_state.long_press_work, long_press_work_handler);
	k_work_init_delayable(&btn_state.held_work, held_work_handler);
	k_work_init_delayable(&btn_state.double_press_work, double_press_work_handler);

	/* Configure GPIO */
#ifdef BUTTON_NODE
	if (!gpio_is_ready_dt(&button_spec)) {
		LOG_ERR("Button GPIO device not ready");
		return -ENODEV;
	}

	ret = gpio_pin_configure_dt(&button_spec, GPIO_INPUT);
	if (ret < 0) {
		LOG_ERR("Failed to configure button GPIO: %d", ret);
		return ret;
	}

	ret = gpio_pin_interrupt_configure_dt(&button_spec, GPIO_INT_EDGE_BOTH);
	if (ret < 0) {
		LOG_ERR("Failed to configure button interrupt: %d", ret);
		return ret;
	}

	gpio_init_callback(&btn_state.gpio_cb, gpio_callback_handler,
			   BIT(button_spec.pin));
	ret = gpio_add_callback(button_spec.port, &btn_state.gpio_cb);
	if (ret < 0) {
		LOG_ERR("Failed to add GPIO callback: %d", ret);
		return ret;
	}

	LOG_INF("Button initialized on %s pin %d", button_spec.port->name,
		button_spec.pin);
#else
	button_port = DEVICE_DT_GET(BUTTON_GPIO_PORT);
	if (!device_is_ready(button_port)) {
		LOG_ERR("Button GPIO port not ready");
		return -ENODEV;
	}

	ret = gpio_pin_configure(button_port, BUTTON_GPIO_PIN, BUTTON_GPIO_FLAGS);
	if (ret < 0) {
		LOG_ERR("Failed to configure button GPIO: %d", ret);
		return ret;
	}

	ret = gpio_pin_interrupt_configure(button_port, BUTTON_GPIO_PIN,
					   GPIO_INT_EDGE_BOTH);
	if (ret < 0) {
		LOG_ERR("Failed to configure button interrupt: %d", ret);
		return ret;
	}

	gpio_init_callback(&btn_state.gpio_cb, gpio_callback_handler,
			   BIT(BUTTON_GPIO_PIN));
	ret = gpio_add_callback(button_port, &btn_state.gpio_cb);
	if (ret < 0) {
		LOG_ERR("Failed to add GPIO callback: %d", ret);
		return ret;
	}

	LOG_INF("Button initialized on GPIO0 pin %d (fallback)", BUTTON_GPIO_PIN);
#endif

	/* Initialize state */
	btn_state.is_pressed = false;
	btn_state.is_enabled = true;
	btn_state.press_start_time = 0;
	btn_state.last_release_time = 0;
	btn_state.press_count = 0;
	btn_state.callback_count = 0;

	/* Read initial button state */
	initial = read_button_state();
	if (initial > 0) {
		LOG_INF("Button is pressed at init");
		btn_state.is_pressed = true;
		btn_state.press_start_time = k_uptime_get();
	}

	btn_state.is_initialized = true;
	LOG_INF("Button handler initialized (debounce=%u ms, long=%u ms, double=%u ms, held=%u ms)",
		btn_state.config.debounce_ms, btn_state.config.long_press_ms,
		btn_state.config.double_press_ms, btn_state.config.held_threshold_ms);

	return 0;
}

int icle_button_deinit(void)
{
	if (!btn_state.is_initialized)
		return -EINVAL;

	/* Cancel all pending work */
	k_work_cancel_delayable(&btn_state.debounce_work);
	k_work_cancel_delayable(&btn_state.long_press_work);
	k_work_cancel_delayable(&btn_state.held_work);
	k_work_cancel_delayable(&btn_state.double_press_work);

	/* Remove GPIO callback and disable interrupt */
#ifdef BUTTON_NODE
	gpio_remove_callback(button_spec.port, &btn_state.gpio_cb);
	gpio_pin_interrupt_configure_dt(&button_spec, GPIO_INT_DISABLE);
#else
	gpio_remove_callback(button_port, &btn_state.gpio_cb);
	gpio_pin_interrupt_configure(button_port, BUTTON_GPIO_PIN, GPIO_INT_DISABLE);
#endif

	btn_state.is_initialized = false;
	LOG_INF("Button handler deinitialized");

	return 0;
}

int icle_button_set_config(const struct icle_button_config *config)
{
	if (!btn_state.is_initialized)
		return -EINVAL;

	k_mutex_lock(&btn_state.state_mutex, K_FOREVER);

	if (config == NULL) {
		/* Reset to defaults */
		btn_state.config.debounce_ms = DEFAULT_DEBOUNCE_MS;
		btn_state.config.long_press_ms = DEFAULT_LONG_PRESS_MS;
		btn_state.config.double_press_ms = DEFAULT_DOUBLE_PRESS_MS;
		btn_state.config.held_threshold_ms = DEFAULT_HELD_THRESHOLD_MS;
	} else {
		/* Validate configuration */
		if (config->debounce_ms == 0 || config->debounce_ms > 500) {
			k_mutex_unlock(&btn_state.state_mutex);
			return -EINVAL;
		}
		if (config->long_press_ms <= config->debounce_ms) {
			k_mutex_unlock(&btn_state.state_mutex);
			return -EINVAL;
		}
		if (config->held_threshold_ms <= config->long_press_ms) {
			k_mutex_unlock(&btn_state.state_mutex);
			return -EINVAL;
		}

		btn_state.config = *config;
	}

	k_mutex_unlock(&btn_state.state_mutex);

	LOG_INF("Button config updated: debounce=%u ms, long=%u ms, double=%u ms, held=%u ms",
		btn_state.config.debounce_ms, btn_state.config.long_press_ms,
		btn_state.config.double_press_ms, btn_state.config.held_threshold_ms);

	return 0;
}

int icle_button_get_config(struct icle_button_config *config)
{
	if (config == NULL)
		return -EINVAL;

	k_mutex_lock(&btn_state.state_mutex, K_FOREVER);
	*config = btn_state.config;
	k_mutex_unlock(&btn_state.state_mutex);

	return 0;
}

int icle_button_register_callback(icle_button_callback_t callback,
				  void *user_data)
{
	if (callback == NULL)
		return -EINVAL;

	k_mutex_lock(&btn_state.state_mutex, K_FOREVER);

	if (btn_state.callback_count >= MAX_CALLBACKS) {
		k_mutex_unlock(&btn_state.state_mutex);
		LOG_ERR("Maximum callbacks reached (%d)", MAX_CALLBACKS);
		return -ENOMEM;
	}

	/* Check for duplicate */
	for (int i = 0; i < btn_state.callback_count; i++) {
		if (btn_state.callbacks[i].callback == callback) {
			k_mutex_unlock(&btn_state.state_mutex);
			LOG_WRN("Callback already registered");
			return 0;
		}
	}

	btn_state.callbacks[btn_state.callback_count].callback = callback;
	btn_state.callbacks[btn_state.callback_count].user_data = user_data;
	btn_state.callback_count++;

	k_mutex_unlock(&btn_state.state_mutex);

	LOG_DBG("Callback registered (%d total)", btn_state.callback_count);
	return 0;
}

void icle_button_unregister_callback(icle_button_callback_t callback)
{
	if (callback == NULL)
		return;

	k_mutex_lock(&btn_state.state_mutex, K_FOREVER);

	for (int i = 0; i < btn_state.callback_count; i++) {
		if (btn_state.callbacks[i].callback == callback) {
			/* Shift remaining callbacks down */
			for (int j = i; j < btn_state.callback_count - 1; j++)
				btn_state.callbacks[j] = btn_state.callbacks[j + 1];
			btn_state.callback_count--;
			break;
		}
	}

	k_mutex_unlock(&btn_state.state_mutex);
}

bool icle_button_is_pressed(void)
{
	return btn_state.is_pressed;
}

uint32_t icle_button_get_hold_time(void)
{
	int64_t now;

	if (!btn_state.is_pressed)
		return 0;

	now = k_uptime_get();
	return (uint32_t)(now - btn_state.press_start_time);
}

enum icle_button_event icle_button_wait_event(uint32_t event_mask,
					      uint32_t timeout_ms)
{
	uint32_t events;
	k_timeout_t timeout;

	if (timeout_ms == UINT32_MAX)
		timeout = K_FOREVER;
	else
		timeout = K_MSEC(timeout_ms);

	/* Wait for any of the requested events */
	events = k_event_wait(&btn_state.events, event_mask, false, timeout);

	if (events == 0)
		return ICLE_BTN_EVENT_NONE;

	/* Clear the events we received */
	k_event_clear(&btn_state.events, events);

	/* Return the first (lowest bit) event that matched */
	for (int i = 1; i < 8; i++) {
		if (events & BIT(i))
			return (enum icle_button_event)i;
	}

	return ICLE_BTN_EVENT_NONE;
}

void icle_button_set_enabled(bool enable)
{
	btn_state.is_enabled = enable;
	LOG_DBG("Button events %s", enable ? "enabled" : "disabled");
}

bool icle_button_is_enabled(void)
{
	return btn_state.is_enabled;
}

int icle_button_configure_wake(bool enable)
{
	LOG_INF("Button wake source %s", enable ? "enabled" : "disabled");

#ifdef CONFIG_SOC_SERIES_ESP32
	if (enable) {
		esp_err_t err;

		/*
		 * ESP32 BOOT button is on GPIO0, active low.
		 * Configure ext0 wakeup: wake when GPIO0 goes low.
		 */
		err = esp_sleep_enable_ext0_wakeup(GPIO_NUM_0, 0);
		if (err != ESP_OK) {
			LOG_ERR("Failed to enable ext0 wakeup: %d", err);
			return -EIO;
		}
		LOG_INF("ESP32 ext0 wakeup enabled on GPIO0 (low)");
	}
#endif

	return 0;
}

const char *icle_button_event_name(enum icle_button_event event)
{
	switch (event) {
	case ICLE_BTN_EVENT_NONE:
		return "NONE";
	case ICLE_BTN_EVENT_PRESSED:
		return "PRESSED";
	case ICLE_BTN_EVENT_RELEASED:
		return "RELEASED";
	case ICLE_BTN_EVENT_SHORT_PRESS:
		return "SHORT_PRESS";
	case ICLE_BTN_EVENT_LONG_PRESS:
		return "LONG_PRESS";
	case ICLE_BTN_EVENT_DOUBLE_PRESS:
		return "DOUBLE_PRESS";
	case ICLE_BTN_EVENT_HELD:
		return "HELD";
	default:
		return "UNKNOWN";
	}
}
