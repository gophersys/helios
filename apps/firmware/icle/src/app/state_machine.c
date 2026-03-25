// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Application State Machine
 *
 * Fully async event-driven architecture.
 * icle_app_run() IS the main event loop - runs on the main thread,
 * uses k_event_wait(K_FOREVER), never returns.
 *
 * Core rules:
 * - Only K_FOREVER and K_NO_WAIT for any blocking call
 * - All timeouts via k_work_delayable that post events when fired
 * - WiFi is fully async - callbacks post events
 * - Single event loop processes all events
 */

#include "app/state_machine.h"
#include "app/events.h"
#include "icle/app.h"
#include "icle/config.h"
#include "hal/gpio.h"
#include "hal/button.h"
#include "net/wifi.h"
#include "net/heartbeat.h"
#include "services/logger.h"
#include "services/pm.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <string.h>

LOG_MODULE_REGISTER(icle_app, CONFIG_LOG_DEFAULT_LEVEL);

/* Timeout configurations (ms) */
#define BOOT_DECIDE_TIMEOUT_MS   3000   /* 3s boot decision window */
#define CONFIG_TIMEOUT_MS        300000 /* 5min config mode timeout */
#define SHUTDOWN_TIMEOUT_MS      5000   /* 5s shutdown grace period */

/* Application context */
static struct icle_app_ctx app_ctx;

/*
 * Timeout timers - use k_timer instead of k_work_delayable.
 *
 * k_work_delayable runs on the system workqueue, which can be blocked
 * by WiFi net_mgmt calls on ESP32. k_timer expiry functions run from
 * the timer ISR, and k_event_post() is ISR-safe, so these always fire
 * regardless of system workqueue state.
 */
static struct k_timer boot_decide_timer;
static struct k_timer config_timer;
static struct k_timer shutdown_timer;

/* State tracking */
static bool initialized;
static bool wifi_connect_started;

/* State name lookup — const pointers in a const array (CONST_ARRAY_QUALIFIER) */
static const char * const state_names[] = {
	[ICLE_STATE_BOOT] = "BOOT",
	[ICLE_STATE_BOOT_DECIDE] = "BOOT_DECIDE",
	[ICLE_STATE_CONFIG] = "CONFIG",
	[ICLE_STATE_LOGGER] = "LOGGER",
	[ICLE_STATE_SHUTDOWN] = "SHUTDOWN",
	[ICLE_STATE_DEEP_SLEEP] = "DEEP_SLEEP",
	[ICLE_STATE_ERROR] = "ERROR",
};

/* Forward declarations */
static void enter_state(enum icle_app_state state);
static void exit_state(enum icle_app_state state);
static void dispatch_events(uint32_t events);
static void transition_to(enum icle_app_state new_state);
static void button_event_handler(enum icle_button_event event,
				 uint32_t hold_time_ms, void *user_data);
static void handle_boot_decide_events(uint32_t events);
static void handle_config_events(uint32_t events);
static void handle_logger_events(uint32_t events);
static void handle_shutdown_events(uint32_t events);
static void handle_error_events(uint32_t events);

/*
 * Timer expiry handlers - run from timer ISR context.
 * k_event_post() is ISR-safe so we can post directly.
 */
static void boot_decide_timer_expiry(struct k_timer *timer)
{
	ARG_UNUSED(timer);
	icle_events_post(ICLE_EVENT_BOOT_DECIDE_TIMEOUT);
}

static void config_timer_expiry(struct k_timer *timer)
{
	ARG_UNUSED(timer);
	icle_events_post(ICLE_EVENT_CONFIG_TIMEOUT);
}

static void shutdown_timer_expiry(struct k_timer *timer)
{
	ARG_UNUSED(timer);
	icle_events_post(ICLE_EVENT_SHUTDOWN_TIMEOUT);
}

/**
 * @brief Button event handler - posts events to the app event loop
 */
static void button_event_handler(enum icle_button_event event,
				 uint32_t hold_time_ms, void *user_data)
{
	ARG_UNUSED(user_data);

	switch (event) {
	case ICLE_BTN_EVENT_SHORT_PRESS:
		LOG_DBG("Short press detected");
		icle_events_post(ICLE_EVENT_BUTTON_SHORT);
		break;

	case ICLE_BTN_EVENT_LONG_PRESS:
		LOG_INF("Long press detected (%u ms)", hold_time_ms);
		icle_events_post(ICLE_EVENT_BUTTON_LONG);
		break;

	case ICLE_BTN_EVENT_DOUBLE_PRESS:
		LOG_DBG("Double press detected");
		icle_events_post(ICLE_EVENT_BUTTON_DOUBLE);
		break;

	case ICLE_BTN_EVENT_HELD:
		LOG_INF("Button held %u ms - force shutdown", hold_time_ms);
		icle_events_post(ICLE_EVENT_BUTTON_HELD_3S);
		break;

	default:
		break;
	}
}

/**
 * @brief Transition to a new state
 */
static void transition_to(enum icle_app_state new_state)
{
	if (new_state == app_ctx.state)
		return;

	LOG_INF("State transition: %s -> %s",
		icle_app_state_name(app_ctx.state),
		icle_app_state_name(new_state));

	exit_state(app_ctx.state);

	app_ctx.prev_state = app_ctx.state;
	app_ctx.state = new_state;

	enter_state(new_state);
}

/**
 * @brief Enter state - perform entry actions and schedule timeouts
 */
static void enter_state(enum icle_app_state state)
{
	app_ctx.state_enter_time = k_uptime_get_32();

	LOG_INF("Entering state: %s", icle_app_state_name(state));

	switch (state) {
	case ICLE_STATE_BOOT:
		/* Green LED blinking - boot in progress */
		icle_led_set(ICLE_LED_GREEN, true);
		icle_led_set(ICLE_LED_RED, false);
		/* Immediately transition to BOOT_DECIDE */
		transition_to(ICLE_STATE_BOOT_DECIDE);
		break;

	case ICLE_STATE_BOOT_DECIDE: {
		struct icle_config config;
		int ret;

		/* Schedule boot decide timeout via k_timer (ISR context) */
		k_timer_start(&boot_decide_timer,
			      K_MSEC(BOOT_DECIDE_TIMEOUT_MS), K_NO_WAIT);

		/* Start WiFi connection (async - returns immediately) */
		wifi_connect_started = false;
		icle_config_get(&config);

		LOG_INF("WiFi config: SSID='%s'", config.wifi_ssid);
		LOG_INF("Backend URL: %s", config.backend_url);

		ret = icle_wifi_connect_simple(
			config.wifi_ssid, config.wifi_psk, 0);

		if (ret == 0 || ret == -EINPROGRESS) {
			LOG_INF("WiFi connection started (async)");
			wifi_connect_started = true;
		} else {
			LOG_ERR("WiFi connection request failed: %d", ret);
		}

		/* Check if button pressed at boot */
		if (icle_button_is_pressed())
			LOG_INF("Button pressed at boot - config mode pending");
		break;
	}

	case ICLE_STATE_CONFIG:
		/* Red LED solid - config mode */
		icle_led_set(ICLE_LED_GREEN, false);
		icle_led_set(ICLE_LED_RED, true);

		/* Schedule config timeout via k_timer (ISR context) */
		k_timer_start(&config_timer,
			      K_MSEC(CONFIG_TIMEOUT_MS), K_NO_WAIT);

		LOG_INF("Config mode active (timeout: %u ms)", CONFIG_TIMEOUT_MS);
		break;

	case ICLE_STATE_LOGGER: {
		uint32_t hb_interval;
		uint32_t sample_interval;

		/* Green LED solid - logging active */
		icle_led_set(ICLE_LED_GREEN, true);
		icle_led_set(ICLE_LED_RED, false);

		app_ctx.wifi_connected = true;

		/* Start heartbeat service */
		hb_interval = icle_config_get_heartbeat_interval();
		icle_heartbeat_start(hb_interval);

		/* Start power sampling */
		sample_interval = icle_config_get_sample_interval();
		icle_log_start_sampling(sample_interval);

		LOG_INF("Logger active (sample=%u ms, heartbeat=%u ms)",
			sample_interval, hb_interval);
		break;
	}

	case ICLE_STATE_SHUTDOWN:
		/* Both LEDs on - shutting down */
		icle_led_set(ICLE_LED_GREEN, true);
		icle_led_set(ICLE_LED_RED, true);

		/* Stop active services */
		icle_log_stop_sampling();
		icle_heartbeat_stop();

		/* Flush logs (async - posts WRITER_DONE when complete) */
		icle_log_flush(0);

		/* Disconnect WiFi */
		icle_wifi_disconnect();

		/* Schedule shutdown timeout in case flush hangs */
		k_timer_start(&shutdown_timer,
			      K_MSEC(SHUTDOWN_TIMEOUT_MS), K_NO_WAIT);

		LOG_INF("Shutdown in progress (timeout: %u ms)",
			SHUTDOWN_TIMEOUT_MS);
		break;

	case ICLE_STATE_DEEP_SLEEP: {
		uint32_t hb_sec;
		struct icle_pm_persist_state pm_state = {
			.magic = ICLE_PM_STATE_MAGIC,
			.version = 1,
			.device_state = app_ctx.prev_state,
			.scheduled_action = 0,
			.wake_count = icle_pm_get_boot_count(),
		};

		/* Turn off LEDs */
		icle_led_set(ICLE_LED_GREEN, false);
		icle_led_set(ICLE_LED_RED, false);

		/* Save state to ZMS for wake recovery */
		icle_pm_save_state(&pm_state);

		/* Configure wake sources: timer (heartbeat) + button */
		hb_sec = icle_config_get_heartbeat_interval() / 1000;
		if (hb_sec < 60)
			hb_sec = 60;
		icle_button_configure_wake(true);
		icle_pm_configure_wakeup(hb_sec, 0);

		/* Enter deep sleep - never returns */
		icle_pm_enter_deep_sleep();
		break;
	}

	case ICLE_STATE_ERROR:
		/* Red LED blinking - error state */
		icle_led_set(ICLE_LED_GREEN, false);
		icle_led_set(ICLE_LED_RED, true);
		LOG_ERR("Entered ERROR state");
		break;

	default:
		break;
	}
}

/**
 * @brief Exit state - perform cleanup actions
 */
static void exit_state(enum icle_app_state state)
{
	/* Compute duration only when debug logging is active to avoid dead store */
	LOG_DBG("Exiting state: %s (duration: %u ms)",
		icle_app_state_name(state),
		(uint32_t)(k_uptime_get_32() - app_ctx.state_enter_time));

	switch (state) {
	case ICLE_STATE_BOOT_DECIDE:
		/* Cancel boot decide timeout */
		k_timer_stop(&boot_decide_timer);
		break;

	case ICLE_STATE_CONFIG:
		/* Cancel config timeout */
		k_timer_stop(&config_timer);
		break;

	case ICLE_STATE_LOGGER:
		/* Flush will happen in SHUTDOWN enter */
		break;

	case ICLE_STATE_SHUTDOWN:
		k_timer_stop(&shutdown_timer);
		break;

	default:
		break;
	}
}

/**
 * @brief Handle events while in ICLE_STATE_BOOT_DECIDE
 */
static void handle_boot_decide_events(uint32_t events)
{
	/* Config mode if long press detected */
	if (events & (ICLE_EVENT_BUTTON_LONG | ICLE_EVENT_BUTTON_CONFIG)) {
		transition_to(ICLE_STATE_CONFIG);
		return;
	}

	/* WiFi connected with IP -> start logging */
	if (events & (ICLE_EVENT_WIFI_IP_ACQUIRED |
		      ICLE_EVENT_WIFI_CONNECTED)) {
		LOG_INF("WiFi connected - starting logger");
		transition_to(ICLE_STATE_LOGGER);
		return;
	}

	/* WiFi connection failed - stay and wait for reconnect */
	if (events & (ICLE_EVENT_WIFI_CONNECT_FAILED |
		      ICLE_EVENT_WIFI_CONNECT_TIMEOUT)) {
		LOG_WRN("WiFi connect failed, auto-reconnect will retry");
		/* reconnect_work in wifi.c handles the retry */
	}

	/* Boot decide timeout - proceed without WiFi */
	if (events & ICLE_EVENT_BOOT_DECIDE_TIMEOUT) {
		if (icle_wifi_is_connected()) {
			transition_to(ICLE_STATE_LOGGER);
		} else {
			LOG_WRN("Boot decide timeout - no WiFi, starting logger anyway");
			transition_to(ICLE_STATE_LOGGER);
		}
		return;
	}

	/* Timer wake - send heartbeat and go back to sleep */
	if (events & ICLE_EVENT_TIMER_WAKE) {
		LOG_INF("Timer wake - heartbeat mode");
		/* WiFi connect is already started in enter_state,
		 * wait for IP acquired then send heartbeat.
		 */
	}
}

/**
 * @brief Handle events while in ICLE_STATE_CONFIG
 */
static void handle_config_events(uint32_t events)
{
	/* Exit config on short press */
	if (events & ICLE_EVENT_BUTTON_SHORT) {
		transition_to(ICLE_STATE_BOOT_DECIDE);
		return;
	}

	/* Config timeout */
	if (events & ICLE_EVENT_CONFIG_TIMEOUT) {
		LOG_INF("Config mode timeout");
		transition_to(ICLE_STATE_BOOT_DECIDE);
		return;
	}

	/* WiFi connected while in config */
	if (events & ICLE_EVENT_WIFI_IP_ACQUIRED) {
		LOG_INF("WiFi connected in config mode");
		/* Stay in config - user chose this mode */
	}
}

/**
 * @brief Handle events while in ICLE_STATE_LOGGER
 */
static void handle_logger_events(uint32_t events)
{
	/* WiFi disconnected */
	if (events & ICLE_EVENT_WIFI_DISCONNECTED) {
		LOG_WRN("WiFi disconnected in logger mode");
		app_ctx.wifi_connected = false;
		/* Auto-reconnect handles retry, keep logging locally */
	}

	/* WiFi reconnected */
	if (events & (ICLE_EVENT_WIFI_IP_ACQUIRED |
		      ICLE_EVENT_WIFI_CONNECTED)) {
		LOG_INF("WiFi reconnected");
		app_ctx.wifi_connected = true;
	}

	/* Heartbeat due */
	if (events & ICLE_EVENT_HEARTBEAT_DUE)
		icle_heartbeat_send();

	/* Storage full */
	if (events & ICLE_EVENT_STORAGE_FULL)
		LOG_WRN("Storage full - consider sync or cleanup");

	/* Long press -> config mode */
	if (events & (ICLE_EVENT_BUTTON_LONG | ICLE_EVENT_BUTTON_CONFIG)) {
		transition_to(ICLE_STATE_CONFIG);
		return;
	}

	/* Sync complete */
	if (events & ICLE_EVENT_SYNC_COMPLETE)
		LOG_INF("HTTP sync completed");
}

/**
 * @brief Handle events while in ICLE_STATE_SHUTDOWN
 */
static void handle_shutdown_events(uint32_t events)
{
	/* Writer done flushing */
	if (events & ICLE_EVENT_WRITER_DONE) {
		LOG_INF("Log flush complete - ready for sleep");
		transition_to(ICLE_STATE_DEEP_SLEEP);
		return;
	}

	/* Shutdown timeout - force sleep even if flush didn't complete */
	if (events & ICLE_EVENT_SHUTDOWN_TIMEOUT) {
		LOG_WRN("Shutdown timeout - forcing deep sleep");
		transition_to(ICLE_STATE_DEEP_SLEEP);
	}
}

/**
 * @brief Handle events while in ICLE_STATE_ERROR
 */
static void handle_error_events(uint32_t events)
{
	/* Short press to retry */
	if (events & ICLE_EVENT_BUTTON_SHORT) {
		LOG_INF("Retry from error state");
		transition_to(ICLE_STATE_BOOT);
	}
}

/**
 * @brief Dispatch events based on current state
 *
 * This is the core of the event-driven state machine.
 * Called from the main event loop whenever events are pending.
 */
static void dispatch_events(uint32_t events)
{
	/* Global events - handled in any state */

	/* Force shutdown on button held 3s */
	if (events & ICLE_EVENT_BUTTON_HELD_3S) {
		if (app_ctx.state != ICLE_STATE_SHUTDOWN &&
		    app_ctx.state != ICLE_STATE_DEEP_SLEEP) {
			LOG_INF("Force shutdown requested");
			transition_to(ICLE_STATE_SHUTDOWN);
			return;
		}
	}

	/* Shutdown request event */
	if (events & (ICLE_EVENT_SHUTDOWN_REQUEST | ICLE_EVENT_SHUTDOWN)) {
		if (app_ctx.state != ICLE_STATE_SHUTDOWN &&
		    app_ctx.state != ICLE_STATE_DEEP_SLEEP) {
			transition_to(ICLE_STATE_SHUTDOWN);
			return;
		}
	}

	/* Critical error */
	if (events & ICLE_EVENT_CRITICAL_ERROR) {
		if (app_ctx.state != ICLE_STATE_ERROR) {
			transition_to(ICLE_STATE_ERROR);
			return;
		}
	}

	/* State-specific event handling */
	switch (app_ctx.state) {
	case ICLE_STATE_BOOT:
		/* Should not stay here - enter_state transitions immediately */
		break;

	case ICLE_STATE_BOOT_DECIDE:
		handle_boot_decide_events(events);
		break;

	case ICLE_STATE_CONFIG:
		handle_config_events(events);
		break;

	case ICLE_STATE_LOGGER:
		handle_logger_events(events);
		break;

	case ICLE_STATE_SHUTDOWN:
		handle_shutdown_events(events);
		break;

	case ICLE_STATE_DEEP_SLEEP:
		/* Should not receive events here - enter_state calls
		 * icle_pm_enter_deep_sleep() which never returns
		 */
		break;

	case ICLE_STATE_ERROR:
		handle_error_events(events);
		break;

	default:
		LOG_ERR("Unknown state: %d", app_ctx.state);
		transition_to(ICLE_STATE_ERROR);
		break;
	}
}

/*
 * Public API
 */

int icle_app_init(void)
{
	if (initialized)
		return 0;

	memset(&app_ctx, 0, sizeof(app_ctx));

	/* Initialize timeout timers (run in ISR context, bypass system workqueue) */
	k_timer_init(&boot_decide_timer, boot_decide_timer_expiry, NULL);
	k_timer_init(&config_timer, config_timer_expiry, NULL);
	k_timer_init(&shutdown_timer, shutdown_timer_expiry, NULL);

	app_ctx.state = ICLE_STATE_BOOT;
	app_ctx.prev_state = ICLE_STATE_BOOT;

	/* Register button callback for state machine events */
	icle_button_register_callback(button_event_handler, NULL);

	initialized = true;

	LOG_INF("Application state machine initialized");
	return 0;
}

void icle_app_run(void)
{
	LOG_INF("=== Event loop starting on main thread ===");

	/* Enter initial state */
	enter_state(app_ctx.state);

	/*
	 * Main event loop - this IS the application.
	 * k_event_wait with K_FOREVER is safe on ESP32.
	 * Wakes only when events are posted.
	 * No busy waits, no polling, no blocking timeouts.
	 */
	for (;;) {
		uint32_t events;

		/*
		 * Poll for events with cooperative yield.
		 *
		 * ESP32 Zephyr port has issues with blocking primitives
		 * being woken from ISR context (k_event_wait, k_sem_take
		 * don't return when signaled from timer ISR). Polling
		 * with k_yield() is the reliable workaround.
		 *
		 * k_yield() gives the CPU to any ready thread of equal
		 * or higher priority, then returns. This keeps the system
		 * responsive while allowing other threads to run.
		 */
		events = icle_events_wait(
			ICLE_EVENT_ALL, true, K_NO_WAIT);

		if (events != 0) {
			LOG_INF("Events: 0x%08x (state=%s)",
				events, icle_app_state_name(app_ctx.state));
			dispatch_events(events);
		}

		k_yield();
	}

	/* Never reaches here */
	CODE_UNREACHABLE;
}

enum icle_app_state icle_app_get_state(void)
{
	return app_ctx.state;
}

const struct icle_app_ctx *icle_app_get_ctx(void)
{
	return &app_ctx;
}

void icle_app_post_event(uint32_t event)
{
	icle_events_post(event);
}

int icle_app_request_mode(enum icle_app_state target_state)
{
	switch (target_state) {
	case ICLE_STATE_SHUTDOWN:
		icle_events_post(ICLE_EVENT_SHUTDOWN_REQUEST);
		return 0;
	case ICLE_STATE_CONFIG:
		icle_events_post(ICLE_EVENT_BUTTON_CONFIG);
		return 0;
	case ICLE_STATE_LOGGER:
		icle_events_post(ICLE_EVENT_WIFI_CONNECTED);
		return 0;
	default:
		return -EINVAL;
	}
}

int icle_app_shutdown(bool enter_deep_sleep)
{
	ARG_UNUSED(enter_deep_sleep);
	icle_events_post(ICLE_EVENT_SHUTDOWN_REQUEST);
	return 0;
}

const char *icle_app_state_name(enum icle_app_state state)
{
	if (state >= ARRAY_SIZE(state_names))
		return "UNKNOWN";
	return state_names[state];
}
