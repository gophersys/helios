// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Backend Heartbeat Service
 *
 * Replaced dedicated thread with k_work_delayable.
 * Posts ICLE_EVENT_HEARTBEAT_DUE to the app event loop.
 * No blocking timeouts - only K_FOREVER and K_NO_WAIT.
 */

#include "heartbeat.h"
#include "wifi.h"
#include "app/events.h"
#include "icle/app.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <string.h>
#include <stdio.h>

LOG_MODULE_REGISTER(icle_heartbeat, CONFIG_LOG_DEFAULT_LEVEL);

/* Configuration */
#define HEARTBEAT_BUFFER_SIZE 512

/* Module state */
static struct {
	bool initialized;
	bool running;
	uint32_t interval_ms;
	uint32_t last_heartbeat_time;

	/* k_timer runs in ISR context, posts event directly */
	struct k_timer heartbeat_timer;

	icle_heartbeat_cmd_cb_t callback;
	void *callback_user_data;

	char send_buffer[HEARTBEAT_BUFFER_SIZE];
	char recv_buffer[HEARTBEAT_BUFFER_SIZE];
} hb_ctx;

/* Forward declarations */
static void heartbeat_timer_expiry(struct k_timer *timer);

int icle_heartbeat_init(void)
{
	if (hb_ctx.initialized)
		return 0;

	memset(&hb_ctx, 0, sizeof(hb_ctx));

	k_timer_init(&hb_ctx.heartbeat_timer, heartbeat_timer_expiry, NULL);
	hb_ctx.interval_ms = 60000; /* Default 1 minute */

	hb_ctx.initialized = true;
	LOG_INF("Heartbeat service initialized");

	return 0;
}

int icle_heartbeat_deinit(void)
{
	if (!hb_ctx.initialized)
		return 0;

	if (hb_ctx.running)
		icle_heartbeat_stop();

	hb_ctx.initialized = false;
	LOG_INF("Heartbeat service deinitialized");

	return 0;
}

int icle_heartbeat_start(uint32_t interval_ms)
{
	if (!hb_ctx.initialized)
		return -ENODEV;

	if (hb_ctx.running) {
		/* Update interval - restart timer */
		hb_ctx.interval_ms = interval_ms;
		k_timer_start(&hb_ctx.heartbeat_timer,
			      K_MSEC(hb_ctx.interval_ms),
			      K_MSEC(hb_ctx.interval_ms));
		return 0;
	}

	hb_ctx.interval_ms = interval_ms;
	hb_ctx.running = true;

	/* Start repeating heartbeat timer */
	k_timer_start(&hb_ctx.heartbeat_timer,
		      K_MSEC(hb_ctx.interval_ms),
		      K_MSEC(hb_ctx.interval_ms));

	LOG_INF("Heartbeat service started (interval: %u ms)", interval_ms);
	return 0;
}

int icle_heartbeat_stop(void)
{
	if (!hb_ctx.initialized || !hb_ctx.running)
		return 0;

	hb_ctx.running = false;
	k_timer_stop(&hb_ctx.heartbeat_timer);

	LOG_INF("Heartbeat service stopped");
	return 0;
}

int icle_heartbeat_send(void)
{
	/* TODO: Implement HTTP POST to backend with device status */
	LOG_DBG("Heartbeat send (stub)");
	hb_ctx.last_heartbeat_time = k_uptime_get_32();
	return 0;
}

bool icle_heartbeat_is_running(void)
{
	return hb_ctx.running;
}

int icle_heartbeat_register_callback(icle_heartbeat_cmd_cb_t callback,
				     void *user_data)
{
	hb_ctx.callback = callback;
	hb_ctx.callback_user_data = user_data;
	return 0;
}

int icle_heartbeat_set_interval(uint32_t interval_ms)
{
	if (interval_ms < 1000)
		return -EINVAL;

	hb_ctx.interval_ms = interval_ms;

	/* Restart timer if running */
	if (hb_ctx.running) {
		k_timer_start(&hb_ctx.heartbeat_timer,
			      K_MSEC(hb_ctx.interval_ms),
			      K_MSEC(hb_ctx.interval_ms));
	}

	return 0;
}

uint32_t icle_heartbeat_get_last_time(void)
{
	return hb_ctx.last_heartbeat_time;
}

/**
 * @brief Heartbeat timer expiry - fires at interval from ISR context.
 *
 * Posts ICLE_EVENT_HEARTBEAT_DUE to the app event loop. The actual
 * heartbeat HTTP POST is done by the app thread when it processes the event.
 * k_event_post is ISR-safe. Timer auto-repeats via the period parameter.
 */
static void heartbeat_timer_expiry(struct k_timer *timer)
{
	ARG_UNUSED(timer);

	if (!hb_ctx.running)
		return;

	/* Post event to app event loop - ISR-safe */
	icle_events_post(ICLE_EVENT_HEARTBEAT_DUE);
}
