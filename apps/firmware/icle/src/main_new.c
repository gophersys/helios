// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Zephyr Firmware - Main Entry Point
 *
 * CoreKinect In-Circuit Loop-back Equipment (ICLE) v1.0
 * ESP32-WROOM-32 based test fixture for DUT validation
 *
 * Boot sequence:
 * 1. Detect wake cause (cold boot, timer, button)
 * 2. Initialize PM (increments boot_count in RTC memory)
 * 3. Initialize all subsystems
 * 4. If timer wake: post TIMER_WAKE event for fast heartbeat path
 * 5. icle_app_run() — runs event loop on main thread, NEVER RETURNS
 *
 * Architecture: fully async event-driven, no blocking timeouts.
 * Only K_FOREVER and K_NO_WAIT are used for any blocking call.
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_main, CONFIG_LOG_DEFAULT_LEVEL);

#include "icle/version.h"
#include "icle/app.h"
#include "icle/config.h"

#include "app/events.h"
#include "hal/gpio.h"
#include "hal/power_monitor.h"
#include "hal/button.h"
#include "hal/storage.h"
#include "net/wifi.h"
#include "net/heartbeat.h"
#include "services/logger.h"
#include "services/ota.h"
#include "services/pm.h"

/**
 * @brief Print system banner on boot
 */
static void print_banner(enum icle_wake_source wake)
{
	const char *wake_str;

	switch (wake) {
	case ICLE_WAKE_TIMER:
		wake_str = "TIMER";
		break;
	case ICLE_WAKE_BUTTON:
		wake_str = "BUTTON";
		break;
	case ICLE_WAKE_RESET:
		wake_str = "RESET (cold boot)";
		break;
	default:
		wake_str = "UNKNOWN";
		break;
	}

	LOG_INF("=====================================");
	LOG_INF("  ICLE v%s - CoreKinect", ICLE_VERSION_STRING);
	LOG_INF("  In-Circuit Loop-back Equipment");
	LOG_INF("  Zephyr RTOS on ESP32-WROOM-32");
	LOG_INF("  Build: %s %s", ICLE_BUILD_DATE, ICLE_BUILD_TIME);
	LOG_INF("  Wake: %s  Boot#: %u", wake_str,
		icle_pm_get_boot_count());
	LOG_INF("=====================================");
}

/**
 * @brief Initialize all subsystems
 *
 * @return 0 on success, negative errno on critical failure
 */
static int init_subsystems(void)
{
	int ret;

	/* Initialize event system (must be first) */
	ret = icle_events_init();
	if (ret < 0) {
		LOG_ERR("Events init failed: %d", ret);
		return ret;
	}

	/* Initialize configuration manager */
	ret = icle_config_init();
	if (ret < 0)
		LOG_WRN("Config init failed: %d (using defaults)", ret);

	/* Initialize GPIO controls */
	ret = icle_gpio_init();
	if (ret < 0)
		LOG_WRN("GPIO init failed: %d (continuing)", ret);

	/* Initialize power monitor */
	ret = icle_power_init();
	if (ret < 0 && ret != -ENOTSUP)
		LOG_WRN("Power monitor init failed: %d (continuing)", ret);

	/* Initialize button handler */
	ret = icle_button_init();
	if (ret < 0) {
		LOG_ERR("Button init failed: %d", ret);
		return ret;
	}

	/* Initialize WiFi */
	ret = icle_wifi_init();
	if (ret < 0)
		LOG_WRN("WiFi init failed: %d (continuing)", ret);

	/* Initialize storage - non-critical, may fail if no SD card */
	ret = icle_storage_init();
	if (ret < 0)
		LOG_WRN("Storage init failed: %d (continuing)", ret);

	/* Initialize log manager */
	ret = icle_log_init();
	if (ret < 0)
		LOG_WRN("Log manager init failed: %d (continuing)", ret);

	/* Initialize heartbeat service */
	ret = icle_heartbeat_init();
	if (ret < 0)
		LOG_WRN("Heartbeat init failed: %d (continuing)", ret);

	/* Initialize OTA subsystem */
	ret = icle_ota_init();
	if (ret < 0)
		LOG_WRN("OTA init failed: %d (continuing)", ret);

	LOG_INF("All subsystems initialized");
	return 0;
}

/**
 * @brief Main application entry point
 *
 * After init, calls icle_app_run() which runs the event loop
 * on the main thread and NEVER RETURNS.
 */
int main(void)
{
	int ret;
	enum icle_wake_source wake;

	LOG_INF("*** ICLE main() starting ***");

	/*
	 * Step 1: Initialize PM and detect wake cause.
	 * This increments boot_count in RTC memory and
	 * reads esp_sleep_get_wakeup_cause() on ESP32.
	 */
	icle_pm_init();
	wake = icle_pm_detect_wake_cause();

	print_banner(wake);

	/*
	 * Step 2: Initialize all subsystems.
	 */
	ret = init_subsystems();
	if (ret < 0) {
		LOG_ERR("Critical subsystem init failed: %d", ret);
		/* Can't proceed - halt (LOG_MODE_IMMEDIATE flushes inline) */
		k_sleep(K_FOREVER);
		CODE_UNREACHABLE;
	}

	/*
	 * Step 3: Initialize application state machine.
	 */
	ret = icle_app_init();
	if (ret < 0) {
		LOG_ERR("App init failed: %d", ret);
		k_sleep(K_FOREVER);
		CODE_UNREACHABLE;
	}

	/*
	 * Step 4: If this is a timer wake from deep sleep,
	 * post the TIMER_WAKE event so the state machine
	 * can take the fast heartbeat path.
	 */
	if (wake == ICLE_WAKE_TIMER) {
		LOG_INF("Timer wake - posting TIMER_WAKE event");
		icle_events_post(ICLE_EVENT_TIMER_WAKE);
	}

	/*
	 * Step 5: Run the event loop on the main thread.
	 * This NEVER RETURNS. The main thread IS the app thread.
	 * All decisions happen in the event loop via k_event_wait(K_FOREVER).
	 */
	LOG_INF("Starting event loop (main thread, never returns)");
	icle_app_run();

	/* Never reaches here */
	CODE_UNREACHABLE;
	return 0;
}
