/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE Zephyr Firmware - Main Application State Machine
 *
 * CoreKinect In-Circuit Loop-back Equipment (ICLE) v1.0
 * ESP32-WROOM-32 based test fixture for DUT validation
 *
 * State machine: BOOT -> BOOT_DECIDE -> CONFIG_MODE/LOGGER_MODE -> SHUTDOWN -> DEEP_SLEEP
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_main, CONFIG_LOG_DEFAULT_LEVEL);

#include <zephyr/drivers/gpio.h>
#include <string.h>
#include <errno.h>

#include "drivers/icle_gpio.h"
#include "drivers/icle_power.h"
#include "icle_app.h"
#include "icle_wifi.h"
#include "icle_storage.h"
#include "icle_log.h"
#include "icle_button.h"
#include "icle_http.h"
#include "icle_power_monitor.h"

/* Configuration constants */
#define CONFIG_MODE_TIMEOUT_MS    (5 * 60 * 1000)  /* 5 minutes */
#define BOOT_DECIDE_TIMEOUT_MS    2000              /* 2 seconds */
#define SHUTDOWN_TIMEOUT_MS       10000             /* 10 seconds */
#define DEFAULT_SAMPLE_INTERVAL   100               /* 100ms sampling */
#define DEFAULT_SYNC_INTERVAL     (60 * 1000)       /* 1 minute sync */
#define LOG_ROTATION_SIZE         (1024 * 1024)     /* 1MB max log file */
#define LED_BLINK_SLOW_MS         1000
#define LED_BLINK_FAST_MS         200
#define LED_BLINK_MEDIUM_MS       500

/* Thread stack sizes and priorities */
#define MAIN_STACK_SIZE           4096
#define LED_THREAD_STACK_SIZE     512
#define LOG_WRITER_STACK_SIZE     2048
#define HTTP_SYNC_STACK_SIZE      4096

#define MAIN_THREAD_PRIORITY      0
#define LED_THREAD_PRIORITY       7
#define LOG_WRITER_PRIORITY       4
#define HTTP_SYNC_PRIORITY        6

/* Application events */
#define APP_EVENT_ALL             0xFFFFFFFF

/* Thread stacks - allocated statically */
static K_THREAD_STACK_DEFINE(led_stack, LED_THREAD_STACK_SIZE);
static K_THREAD_STACK_DEFINE(log_writer_stack, LOG_WRITER_STACK_SIZE);
static K_THREAD_STACK_DEFINE(http_sync_stack, HTTP_SYNC_STACK_SIZE);

/* Thread control blocks */
static struct k_thread led_thread_data;
static struct k_thread log_writer_thread_data;
static struct k_thread http_sync_thread_data;

/* Thread IDs */
static k_tid_t led_thread_id;
static k_tid_t log_writer_thread_id;
static k_tid_t http_sync_thread_id;

/* Synchronization primitives - created programmatically */
static struct k_event app_events;
static struct k_mutex app_state_mutex;
static struct k_sem shutdown_complete_sem;

/* Application context */
static struct icle_app_ctx app_ctx;
static volatile bool app_running = true;
static volatile bool logger_threads_running = false;

/* Forward declarations */
static void led_thread_fn(void *p1, void *p2, void *p3);
static void log_writer_thread_fn(void *p1, void *p2, void *p3);
static void http_sync_thread_fn(void *p1, void *p2, void *p3);
static int state_boot(void);
static int state_boot_decide(void);
static int state_config_mode(void);
static int state_logger_mode(void);
static int state_shutdown(void);
static int state_deep_sleep(void);
static int state_error(void);
static void button_callback(enum icle_button_event event, uint32_t hold_time_ms, void *user_data);
static void wifi_callback(bool connected, void *user_data);
static void set_led_pattern(enum icle_app_state state);
static int transition_state(enum icle_app_state new_state);
static void start_logger_threads(void);
static void stop_logger_threads(void);

/**
 * @brief Get state name string
 */
const char *icle_app_state_name(enum icle_app_state state)
{
	switch (state) {
	case ICLE_STATE_BOOT:
		return "BOOT";
	case ICLE_STATE_BOOT_DECIDE:
		return "BOOT_DECIDE";
	case ICLE_STATE_CONFIG:
		return "CONFIG";
	case ICLE_STATE_LOGGER:
		return "LOGGER";
	case ICLE_STATE_SHUTDOWN:
		return "SHUTDOWN";
	case ICLE_STATE_DEEP_SLEEP:
		return "DEEP_SLEEP";
	case ICLE_STATE_ERROR:
		return "ERROR";
	default:
		return "UNKNOWN";
	}
}

/**
 * @brief Print system info on boot
 */
static void print_banner(void)
{
	LOG_INF("=====================================");
	LOG_INF("  ICLE v1.0 - CoreKinect");
	LOG_INF("  In-Circuit Loop-back Equipment");
	LOG_INF("  Zephyr RTOS on ESP32-WROOM-32");
	LOG_INF("=====================================");
}

/**
 * @brief LED status thread - shows state via LED patterns
 */
static void led_thread_fn(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	uint32_t blink_interval = LED_BLINK_SLOW_MS;
	bool led_on = false;
	enum icle_led active_led = ICLE_LED_GREEN;

	LOG_DBG("LED thread started");

	while (app_running) {
		k_mutex_lock(&app_state_mutex, K_FOREVER);
		enum icle_app_state state = app_ctx.state;
		bool wifi = app_ctx.wifi_connected;
		k_mutex_unlock(&app_state_mutex);

		/* Determine LED pattern based on state */
		switch (state) {
		case ICLE_STATE_BOOT:
		case ICLE_STATE_BOOT_DECIDE:
			/* Slow green blink - waiting */
			active_led = ICLE_LED_GREEN;
			blink_interval = LED_BLINK_SLOW_MS;
			break;

		case ICLE_STATE_CONFIG:
			if (wifi) {
				/* Solid green when WiFi connected */
				icle_led_set(ICLE_LED_GREEN, true);
				icle_led_set(ICLE_LED_RED, false);
				k_msleep(LED_BLINK_SLOW_MS);
				continue;
			} else {
				/* Medium green blink when connecting */
				active_led = ICLE_LED_GREEN;
				blink_interval = LED_BLINK_MEDIUM_MS;
			}
			break;

		case ICLE_STATE_LOGGER:
			/* Red blink indicates logging active */
			active_led = ICLE_LED_RED;
			blink_interval = LED_BLINK_MEDIUM_MS;
			break;

		case ICLE_STATE_SHUTDOWN:
			/* Fast alternating - shutting down */
			icle_led_toggle(ICLE_LED_GREEN);
			icle_led_toggle(ICLE_LED_RED);
			k_msleep(LED_BLINK_FAST_MS);
			continue;

		case ICLE_STATE_ERROR:
			/* Solid red - error state */
			icle_led_set(ICLE_LED_GREEN, false);
			icle_led_set(ICLE_LED_RED, true);
			k_msleep(LED_BLINK_SLOW_MS);
			continue;

		case ICLE_STATE_DEEP_SLEEP:
			/* Both off before sleep */
			icle_led_set(ICLE_LED_GREEN, false);
			icle_led_set(ICLE_LED_RED, false);
			k_msleep(LED_BLINK_SLOW_MS);
			continue;

		default:
			blink_interval = LED_BLINK_SLOW_MS;
			break;
		}

		/* Toggle appropriate LED */
		led_on = !led_on;
		icle_led_set(active_led, led_on);
		icle_led_set(active_led == ICLE_LED_GREEN ? ICLE_LED_RED : ICLE_LED_GREEN, false);

		k_msleep(blink_interval);
	}

	/* Turn off LEDs on exit */
	icle_led_set(ICLE_LED_GREEN, false);
	icle_led_set(ICLE_LED_RED, false);

	LOG_DBG("LED thread exiting");
}

/**
 * @brief Log writer thread - writes samples from queue to SD card
 */
static void log_writer_thread_fn(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	struct icle_log_entry entry;
	char csv_buf[128];
	int ret;

	LOG_INF("Log writer thread started");

	while (logger_threads_running && app_running) {
		/* Wait for sample from queue */
		ret = icle_log_queue_get(&entry, 1000);
		if (ret == -ETIMEDOUT) {
			continue;
		}
		if (ret < 0) {
			LOG_ERR("Queue get error: %d", ret);
			continue;
		}

		/* Check if storage is ready */
		if (!icle_storage_is_ready()) {
			LOG_WRN("Storage not ready, dropping sample");
			continue;
		}

		/* Format and write based on log format */
		k_mutex_lock(&app_state_mutex, K_FOREVER);
		uint8_t format = app_ctx.config.log_format;
		k_mutex_unlock(&app_state_mutex);

		if (format == ICLE_LOG_FORMAT_CSV) {
			ret = icle_log_format_csv(&entry, csv_buf, sizeof(csv_buf));
			if (ret > 0) {
				icle_storage_write_log(csv_buf, ret);
			}
		} else {
			icle_storage_write_log(&entry, sizeof(entry));
		}

		/* Check for log rotation */
		if (icle_storage_needs_rotation(LOG_ROTATION_SIZE)) {
			LOG_INF("Rotating log file");
			icle_storage_rotate_log(format);
		}
	}

	/* Flush remaining data */
	icle_storage_flush_log();

	LOG_INF("Log writer thread exiting");
}

/**
 * @brief HTTP sync thread - syncs log files to backend
 */
static void http_sync_thread_fn(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	struct icle_file_entry files[8];
	struct icle_sync_result result;
	int count;
	int ret;

	LOG_INF("HTTP sync thread started");

	while (logger_threads_running && app_running) {
		/* Wait for sync interval */
		k_mutex_lock(&app_state_mutex, K_FOREVER);
		uint32_t interval = app_ctx.config.sync_interval_ms;
		bool wifi = app_ctx.wifi_connected;
		k_mutex_unlock(&app_state_mutex);

		k_msleep(interval > 0 ? interval : DEFAULT_SYNC_INTERVAL);

		/* Check if WiFi is connected */
		if (!wifi || !icle_wifi_is_connected()) {
			LOG_DBG("WiFi not connected, skipping sync");
			continue;
		}

		/* Check for pending files */
		count = icle_storage_get_pending_files(files, ARRAY_SIZE(files));
		if (count <= 0) {
			LOG_DBG("No files to sync");
			continue;
		}

		LOG_INF("Syncing %d files", count);

		/* Sync each pending file */
		for (int i = 0; i < count && logger_threads_running; i++) {
			ret = icle_http_sync_file(files[i].name, &result);
			if (ret == 0 && result.success) {
				icle_storage_mark_synced(files[i].name);
				LOG_INF("Synced: %s (%u bytes)", files[i].name, result.bytes_sent);

				/* Post sync complete event */
				k_event_post(&app_events, ICLE_EVENT_SYNC_COMPLETE);
			} else {
				LOG_WRN("Sync failed: %s - %s", files[i].name, result.error_msg);
			}
		}
	}

	LOG_INF("HTTP sync thread exiting");
}

/**
 * @brief Button event callback
 */
static void button_callback(enum icle_button_event event, uint32_t hold_time_ms, void *user_data)
{
	ARG_UNUSED(user_data);

	LOG_INF("Button event: %s (held %u ms)",
		icle_button_event_name(event), hold_time_ms);

	switch (event) {
	case ICLE_BTN_EVENT_SHORT_PRESS:
		k_event_post(&app_events, ICLE_EVENT_BUTTON_SHORT);
		break;
	case ICLE_BTN_EVENT_LONG_PRESS:
		k_event_post(&app_events, ICLE_EVENT_BUTTON_LONG);
		break;
	case ICLE_BTN_EVENT_DOUBLE_PRESS:
		k_event_post(&app_events, ICLE_EVENT_BUTTON_DOUBLE);
		break;
	case ICLE_BTN_EVENT_HELD:
		k_event_post(&app_events, ICLE_EVENT_BUTTON_HELD_3S);
		break;
	default:
		break;
	}

	/* Reset idle timer on any button activity */
	icle_pm_reset_idle_timer();
}

/**
 * @brief WiFi connection callback
 */
static void wifi_callback(bool connected, void *user_data)
{
	ARG_UNUSED(user_data);

	LOG_INF("WiFi %s", connected ? "connected" : "disconnected");

	k_mutex_lock(&app_state_mutex, K_FOREVER);
	app_ctx.wifi_connected = connected;
	k_mutex_unlock(&app_state_mutex);

	if (connected) {
		k_event_post(&app_events, ICLE_EVENT_WIFI_CONNECTED);
	} else {
		k_event_post(&app_events, ICLE_EVENT_WIFI_DISCONNECTED);
	}
}

/**
 * @brief Start logger mode threads
 */
static void start_logger_threads(void)
{
	if (logger_threads_running) {
		return;
	}

	logger_threads_running = true;

	/* Create log writer thread */
	log_writer_thread_id = k_thread_create(
		&log_writer_thread_data,
		log_writer_stack,
		K_THREAD_STACK_SIZEOF(log_writer_stack),
		log_writer_thread_fn,
		NULL, NULL, NULL,
		LOG_WRITER_PRIORITY, 0, K_NO_WAIT);
	k_thread_name_set(log_writer_thread_id, "log_writer");

	/* Create HTTP sync thread */
	http_sync_thread_id = k_thread_create(
		&http_sync_thread_data,
		http_sync_stack,
		K_THREAD_STACK_SIZEOF(http_sync_stack),
		http_sync_thread_fn,
		NULL, NULL, NULL,
		HTTP_SYNC_PRIORITY, 0, K_NO_WAIT);
	k_thread_name_set(http_sync_thread_id, "http_sync");

	LOG_INF("Logger threads started");
}

/**
 * @brief Stop logger mode threads
 */
static void stop_logger_threads(void)
{
	if (!logger_threads_running) {
		return;
	}

	logger_threads_running = false;

	/* Wait for threads to exit */
	if (log_writer_thread_id) {
		k_thread_join(log_writer_thread_id, K_MSEC(5000));
		log_writer_thread_id = NULL;
	}
	if (http_sync_thread_id) {
		k_thread_join(http_sync_thread_id, K_MSEC(5000));
		http_sync_thread_id = NULL;
	}

	LOG_INF("Logger threads stopped");
}

/**
 * @brief Transition to new state
 */
static int transition_state(enum icle_app_state new_state)
{
	k_mutex_lock(&app_state_mutex, K_FOREVER);
	enum icle_app_state old_state = app_ctx.state;

	if (old_state == new_state) {
		k_mutex_unlock(&app_state_mutex);
		return 0;
	}

	LOG_INF("State transition: %s -> %s",
		icle_app_state_name(old_state),
		icle_app_state_name(new_state));

	app_ctx.prev_state = old_state;
	app_ctx.state = new_state;
	app_ctx.state_enter_time = k_uptime_get_32();

	k_mutex_unlock(&app_state_mutex);

	/* Save mode to RTC state */
	icle_pm_set_last_mode((uint8_t)new_state);

	return 0;
}

/**
 * @brief Get current application state
 */
enum icle_app_state icle_app_get_state(void)
{
	k_mutex_lock(&app_state_mutex, K_FOREVER);
	enum icle_app_state state = app_ctx.state;
	k_mutex_unlock(&app_state_mutex);
	return state;
}

/**
 * @brief Get application context (read-only)
 */
const struct icle_app_ctx *icle_app_get_ctx(void)
{
	return &app_ctx;
}

/**
 * @brief Post an event to the application state machine
 */
void icle_app_post_event(uint32_t event)
{
	k_event_post(&app_events, event);
}

/**
 * @brief BOOT state handler - initialize hardware
 */
static int state_boot(void)
{
	int ret;

	LOG_INF("=== BOOT STATE ===");

	/* Initialize GPIO controls (MUX, LEDs, power FET) */
	LOG_INF("Initializing GPIO...");
	ret = icle_gpio_init();
	if (ret < 0) {
		LOG_WRN("GPIO init issue: %d (continuing)", ret);
	}

	/* Start with power FET disabled for safety */
	icle_power_fet_enable(false);
	icle_mux_select(ICLE_MUX_CH0);

	/* Initialize power management */
	LOG_INF("Initializing power management...");
	ret = icle_pm_init();
	if (ret < 0) {
		LOG_ERR("Power management init failed: %d", ret);
	}

	/* Log wake source */
	enum icle_wake_source wake = icle_pm_get_wake_source();
	LOG_INF("Wake source: %s, boot count: %u",
		icle_pm_wake_source_name(wake),
		icle_pm_get_boot_count());

	/* Initialize power monitor (INA209) */
	LOG_INF("Initializing power monitor...");
	ret = icle_power_init();
	if (ret < 0 && ret != -ENOTSUP) {
		LOG_WRN("Power monitor init failed: %d (continuing)", ret);
	}

	/* Initialize button handler */
	LOG_INF("Initializing button handler...");
	ret = icle_button_init();
	if (ret < 0) {
		LOG_ERR("Button init failed: %d", ret);
		return ret;
	}
	icle_button_register_callback(button_callback, NULL);

	/* Initialize WiFi */
	LOG_INF("Initializing WiFi...");
	ret = icle_wifi_init();
	if (ret < 0) {
		LOG_WRN("WiFi init failed: %d (continuing)", ret);
	} else {
		icle_wifi_register_callback(wifi_callback, NULL);
	}

	/* Initialize storage */
	LOG_INF("Initializing storage...");
	ret = icle_storage_init();
	if (ret < 0) {
		LOG_WRN("Storage init failed: %d (continuing)", ret);
		app_ctx.storage_ready = false;
	} else {
		app_ctx.storage_ready = icle_storage_is_ready();
	}

	/* Initialize log manager */
	LOG_INF("Initializing log manager...");
	ret = icle_log_init();
	if (ret < 0) {
		LOG_WRN("Log manager init failed: %d (continuing)", ret);
	}

	/* Initialize HTTP client */
	LOG_INF("Initializing HTTP client...");
	ret = icle_http_init();
	if (ret < 0) {
		LOG_WRN("HTTP client init failed: %d (continuing)", ret);
	}

	/* Configure HTTP with config settings */
	if (strlen(app_ctx.config.sync_url) > 0) {
		icle_http_set_base_url(app_ctx.config.sync_url);
	}
	if (strlen(app_ctx.config.device_id) > 0) {
		icle_http_set_device_id(app_ctx.config.device_id);
	}

	LOG_INF("Boot complete");
	return 0;
}

/**
 * @brief BOOT_DECIDE state handler - determine operating mode
 */
static int state_boot_decide(void)
{
	uint32_t events;

	LOG_INF("=== BOOT_DECIDE STATE ===");
	LOG_INF("Waiting %d ms for button to determine mode...", BOOT_DECIDE_TIMEOUT_MS);

	/* Wait for button event or timeout */
	events = k_event_wait(&app_events,
			      ICLE_EVENT_BUTTON_SHORT | ICLE_EVENT_BUTTON_LONG |
			      ICLE_EVENT_BUTTON_DOUBLE,
			      false,
			      K_MSEC(BOOT_DECIDE_TIMEOUT_MS));

	/* Clear consumed events */
	k_event_clear(&app_events, events);

	if (events & ICLE_EVENT_BUTTON_LONG) {
		/* Long press -> Logger mode */
		LOG_INF("Long press detected -> LOGGER_MODE");
		transition_state(ICLE_STATE_LOGGER);
	} else if (events & (ICLE_EVENT_BUTTON_SHORT | ICLE_EVENT_BUTTON_DOUBLE)) {
		/* Short press or double press -> Config mode */
		LOG_INF("Short/double press detected -> CONFIG_MODE");
		transition_state(ICLE_STATE_CONFIG);
	} else {
		/* Timeout with no button -> default to config mode */
		LOG_INF("Timeout, defaulting to CONFIG_MODE");
		transition_state(ICLE_STATE_CONFIG);
	}

	return 0;
}

/**
 * @brief CONFIG_MODE state handler - WiFi STA for configuration
 */
static int state_config_mode(void)
{
	uint32_t events;
	int ret;

	LOG_INF("=== CONFIG_MODE STATE ===");

	/* Start idle timeout timer */
	icle_pm_start_idle_timer(CONFIG_MODE_TIMEOUT_MS);

	/* Connect to WiFi if credentials available */
	if (strlen(app_ctx.config.wifi_ssid) > 0) {
		LOG_INF("Connecting to WiFi SSID: %s", app_ctx.config.wifi_ssid);
		ret = icle_wifi_connect_simple(app_ctx.config.wifi_ssid,
					       app_ctx.config.wifi_psk,
					       30000);
		if (ret == 0) {
			ret = icle_wifi_wait_connected(30000);
			if (ret == 0) {
				LOG_INF("WiFi connected");
			}
		}
		if (ret < 0) {
			LOG_WRN("WiFi connection failed: %d", ret);
		}
	} else {
		LOG_INF("No WiFi credentials configured");
	}

	/* Config mode loop - wait for events */
	while (app_ctx.state == ICLE_STATE_CONFIG && app_running) {
		events = k_event_wait(&app_events,
				      ICLE_EVENT_BUTTON_DOUBLE |
				      ICLE_EVENT_BUTTON_HELD_3S |
				      ICLE_EVENT_CONFIG_TIMEOUT |
				      ICLE_EVENT_SHUTDOWN_REQUEST |
				      ICLE_EVENT_CRITICAL_ERROR,
				      false,
				      K_SECONDS(10));

		k_event_clear(&app_events, events);

		if (events & ICLE_EVENT_BUTTON_DOUBLE) {
			/* Double press exits config mode -> shutdown */
			LOG_INF("Double press -> exiting config mode");
			transition_state(ICLE_STATE_SHUTDOWN);
			break;
		}

		if (events & ICLE_EVENT_BUTTON_HELD_3S) {
			/* 3s hold -> shutdown */
			LOG_INF("Button held 3s -> shutdown");
			transition_state(ICLE_STATE_SHUTDOWN);
			break;
		}

		if (events & (ICLE_EVENT_CONFIG_TIMEOUT | ICLE_EVENT_SHUTDOWN_REQUEST)) {
			/* Timeout or shutdown request */
			LOG_INF("Config timeout/shutdown request");
			transition_state(ICLE_STATE_SHUTDOWN);
			break;
		}

		if (events & ICLE_EVENT_CRITICAL_ERROR) {
			LOG_ERR("Critical error in config mode");
			transition_state(ICLE_STATE_ERROR);
			break;
		}

		/* Periodic status */
		LOG_DBG("Config mode: WiFi=%s",
			icle_wifi_is_connected() ? "connected" : "disconnected");
	}

	/* Stop idle timer */
	icle_pm_stop_idle_timer();

	return 0;
}

/**
 * @brief LOGGER_MODE state handler - active power logging
 */
static int state_logger_mode(void)
{
	uint32_t events;
	int ret;

	LOG_INF("=== LOGGER_MODE STATE ===");

	/* Verify storage is ready - critical for logger mode */
	if (!icle_storage_is_ready()) {
		LOG_ERR("Storage not ready - cannot enter logger mode");
		k_event_post(&app_events, ICLE_EVENT_CRITICAL_ERROR);
		return -EIO;
	}

	/* Connect to WiFi if credentials available */
	if (strlen(app_ctx.config.wifi_ssid) > 0) {
		LOG_INF("Connecting to WiFi for sync...");
		ret = icle_wifi_connect_simple(app_ctx.config.wifi_ssid,
					       app_ctx.config.wifi_psk,
					       30000);
		if (ret < 0) {
			LOG_WRN("WiFi connection failed: %d (continuing without sync)", ret);
		} else {
			icle_wifi_wait_connected(30000);
		}
		icle_wifi_set_auto_reconnect(true);
	}

	/* Create log file */
	ret = icle_storage_create_log(app_ctx.config.log_format);
	if (ret < 0) {
		LOG_ERR("Failed to create log file: %d", ret);
		k_event_post(&app_events, ICLE_EVENT_CRITICAL_ERROR);
		return ret;
	}

	/* Start logger threads */
	start_logger_threads();

	/* Start power sampling */
	ret = icle_log_start_sampling(app_ctx.config.sample_interval_ms > 0 ?
				      app_ctx.config.sample_interval_ms :
				      DEFAULT_SAMPLE_INTERVAL);
	if (ret < 0) {
		LOG_ERR("Failed to start sampling: %d", ret);
		stop_logger_threads();
		k_event_post(&app_events, ICLE_EVENT_CRITICAL_ERROR);
		return ret;
	}

	LOG_INF("Logger mode active - sampling every %u ms",
		app_ctx.config.sample_interval_ms > 0 ?
		app_ctx.config.sample_interval_ms : DEFAULT_SAMPLE_INTERVAL);

	/* Logger mode loop - wait for exit events */
	while (app_ctx.state == ICLE_STATE_LOGGER && app_running) {
		events = k_event_wait(&app_events,
				      ICLE_EVENT_BUTTON_HELD_3S |
				      ICLE_EVENT_SHUTDOWN_REQUEST |
				      ICLE_EVENT_CRITICAL_ERROR,
				      false,
				      K_SECONDS(30));

		k_event_clear(&app_events, events);

		if (events & ICLE_EVENT_BUTTON_HELD_3S) {
			/* 3s hold -> shutdown */
			LOG_INF("Button held 3s -> stopping logger");
			transition_state(ICLE_STATE_SHUTDOWN);
			break;
		}

		if (events & ICLE_EVENT_SHUTDOWN_REQUEST) {
			LOG_INF("Shutdown requested");
			transition_state(ICLE_STATE_SHUTDOWN);
			break;
		}

		if (events & ICLE_EVENT_CRITICAL_ERROR) {
			LOG_ERR("Critical error in logger mode");
			transition_state(ICLE_STATE_ERROR);
			break;
		}

		/* Periodic status */
		struct icle_log_stats stats;
		if (icle_log_get_stats(&stats) == 0) {
			LOG_INF("Logger: samples=%u, written=%u, dropped=%u, queue=%u",
				stats.samples_taken, stats.samples_written,
				stats.samples_dropped, stats.queue_depth);
		}
	}

	/* Stop sampling */
	icle_log_stop_sampling();

	/* Stop logger threads */
	stop_logger_threads();

	/* Flush and close log */
	icle_log_flush(5000);
	icle_storage_close_log();

	return 0;
}

/**
 * @brief SHUTDOWN state handler - graceful shutdown
 */
static int state_shutdown(void)
{
	LOG_INF("=== SHUTDOWN STATE ===");

	/* Stop any active operations */
	if (icle_log_is_sampling()) {
		LOG_INF("Stopping sampling...");
		icle_log_stop_sampling();
	}

	/* Stop logger threads if running */
	stop_logger_threads();

	/* Flush pending log data */
	LOG_INF("Flushing logs...");
	icle_log_flush(5000);
	icle_storage_flush_log();
	icle_storage_close_log();

	/* Cancel any pending HTTP sync */
	if (icle_http_is_syncing()) {
		LOG_INF("Canceling HTTP sync...");
		icle_http_cancel_sync();
	}

	/* Disconnect WiFi */
	if (icle_wifi_is_connected()) {
		LOG_INF("Disconnecting WiFi...");
		icle_wifi_set_auto_reconnect(false);
		icle_wifi_disconnect();
	}

	/* Unmount storage */
	LOG_INF("Unmounting storage...");
	icle_storage_unmount();

	/* Deinitialize modules */
	icle_http_deinit();
	icle_log_deinit();
	icle_storage_deinit();
	icle_wifi_deinit();

	LOG_INF("Shutdown complete");

	/* Transition to deep sleep */
	transition_state(ICLE_STATE_DEEP_SLEEP);

	return 0;
}

/**
 * @brief DEEP_SLEEP state handler - enter deep sleep
 */
static int state_deep_sleep(void)
{
	LOG_INF("=== DEEP_SLEEP STATE ===");

	/* Stop LED thread */
	app_running = false;
	if (led_thread_id) {
		k_thread_join(led_thread_id, K_MSEC(1000));
	}

	/* Turn off all LEDs */
	icle_led_set(ICLE_LED_GREEN, false);
	icle_led_set(ICLE_LED_RED, false);

	/* Prepare for deep sleep */
	icle_pm_prepare_deep_sleep((uint8_t)app_ctx.prev_state, true, false, 0);

	/* Configure button as wake source */
	icle_button_configure_wake(true);

	/* Small delay for log output */
	k_msleep(100);

	LOG_INF("Entering deep sleep...");

	/* Enter deep sleep - does not return */
	icle_pm_enter_deep_sleep();

	/* Should never reach here */
	LOG_ERR("Deep sleep failed!");
	return -EIO;
}

/**
 * @brief ERROR state handler - critical error handling
 */
static int state_error(void)
{
	uint32_t events;

	LOG_ERR("=== ERROR STATE ===");

	/* Wait for button to acknowledge and reset */
	while (app_ctx.state == ICLE_STATE_ERROR && app_running) {
		events = k_event_wait(&app_events,
				      ICLE_EVENT_BUTTON_HELD_3S |
				      ICLE_EVENT_SHUTDOWN_REQUEST,
				      false,
				      K_SECONDS(30));

		k_event_clear(&app_events, events);

		if (events & (ICLE_EVENT_BUTTON_HELD_3S | ICLE_EVENT_SHUTDOWN_REQUEST)) {
			transition_state(ICLE_STATE_SHUTDOWN);
			break;
		}

		LOG_ERR("In error state - hold button 3s to shutdown");
	}

	return 0;
}

/**
 * @brief Load configuration from NVS
 */
int icle_app_load_config(struct icle_app_config *config)
{
	/* TODO: Implement NVS loading */
	/* For now, use defaults */
	icle_app_default_config(config);
	return 0;
}

/**
 * @brief Save configuration to NVS
 */
int icle_app_save_config(const struct icle_app_config *config)
{
	ARG_UNUSED(config);
	/* TODO: Implement NVS saving */
	return 0;
}

/**
 * @brief Get default configuration
 */
void icle_app_default_config(struct icle_app_config *config)
{
	memset(config, 0, sizeof(*config));
	config->sample_interval_ms = DEFAULT_SAMPLE_INTERVAL;
	config->sync_interval_ms = DEFAULT_SYNC_INTERVAL;
	config->log_format = ICLE_LOG_FORMAT_CSV;
}

/**
 * @brief Request shutdown
 */
int icle_app_shutdown(bool enter_deep_sleep)
{
	ARG_UNUSED(enter_deep_sleep);
	k_event_post(&app_events, ICLE_EVENT_SHUTDOWN_REQUEST);
	return 0;
}

/**
 * @brief Request mode change
 */
int icle_app_request_mode(enum icle_app_state target_state)
{
	/* Validate transition */
	enum icle_app_state current = icle_app_get_state();

	switch (target_state) {
	case ICLE_STATE_CONFIG:
	case ICLE_STATE_LOGGER:
		if (current != ICLE_STATE_BOOT_DECIDE) {
			return -EINVAL;
		}
		break;
	case ICLE_STATE_SHUTDOWN:
		/* Can always request shutdown */
		break;
	default:
		return -EINVAL;
	}

	transition_state(target_state);
	return 0;
}

/**
 * @brief Initialize the application state machine
 */
int icle_app_init(void)
{
	int ret;

	/* Initialize synchronization primitives */
	k_event_init(&app_events);
	ret = k_mutex_init(&app_state_mutex);
	if (ret != 0) {
		LOG_ERR("Failed to init app mutex: %d", ret);
		return ret;
	}
	k_sem_init(&shutdown_complete_sem, 0, 1);

	/* Initialize context */
	memset(&app_ctx, 0, sizeof(app_ctx));
	app_ctx.state = ICLE_STATE_BOOT;
	app_ctx.state_enter_time = k_uptime_get_32();

	/* Load configuration */
	icle_app_load_config(&app_ctx.config);
	app_ctx.boot_count = icle_pm_get_boot_count();

	return 0;
}

/**
 * @brief Start the application state machine
 */
int icle_app_start(void)
{
	/* Create LED thread */
	led_thread_id = k_thread_create(
		&led_thread_data,
		led_stack,
		K_THREAD_STACK_SIZEOF(led_stack),
		led_thread_fn,
		NULL, NULL, NULL,
		LED_THREAD_PRIORITY, 0, K_NO_WAIT);
	k_thread_name_set(led_thread_id, "led_status");

	return 0;
}

/**
 * @brief Main application entry point
 */
int main(void)
{
	int ret;

	print_banner();

	/* Initialize application state machine */
	ret = icle_app_init();
	if (ret < 0) {
		LOG_ERR("App init failed: %d", ret);
		return ret;
	}

	/* Start LED thread */
	icle_app_start();

	/* State machine loop */
	while (app_running) {
		k_mutex_lock(&app_state_mutex, K_FOREVER);
		enum icle_app_state state = app_ctx.state;
		k_mutex_unlock(&app_state_mutex);

		switch (state) {
		case ICLE_STATE_BOOT:
			ret = state_boot();
			if (ret == 0) {
				transition_state(ICLE_STATE_BOOT_DECIDE);
			} else {
				transition_state(ICLE_STATE_ERROR);
			}
			break;

		case ICLE_STATE_BOOT_DECIDE:
			state_boot_decide();
			break;

		case ICLE_STATE_CONFIG:
			state_config_mode();
			break;

		case ICLE_STATE_LOGGER:
			state_logger_mode();
			break;

		case ICLE_STATE_SHUTDOWN:
			state_shutdown();
			break;

		case ICLE_STATE_DEEP_SLEEP:
			state_deep_sleep();
			/* Should not return */
			break;

		case ICLE_STATE_ERROR:
			state_error();
			break;

		default:
			LOG_ERR("Unknown state: %d", state);
			transition_state(ICLE_STATE_ERROR);
			break;
		}
	}

	LOG_INF("Main loop exited");
	return 0;
}
