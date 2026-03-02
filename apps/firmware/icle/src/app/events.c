// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Event System Implementation
 *
 * Uses atomic flags + k_sem instead of k_event.
 * k_event_wait/k_event_post may not work reliably on ESP32
 * (events posted from ISR context are not seen by k_event_wait).
 *
 * This implementation uses:
 * - atomic_t for ISR-safe flag set/clear
 * - k_sem for wakeup signaling (k_sem_give is ISR-safe)
 */

#include "events.h"

#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_events, CONFIG_LOG_DEFAULT_LEVEL);

static atomic_t event_flags;
static struct k_sem event_sem;
static bool initialized;

int icle_events_init(void)
{
	if (initialized)
		return 0;

	atomic_clear(&event_flags);
	k_sem_init(&event_sem, 0, 1);
	initialized = true;

	LOG_DBG("Event system initialized (atomic+sem)");
	return 0;
}

void icle_events_post(uint32_t events)
{
	if (!initialized)
		return;

	/* Atomically OR in the event bits - ISR-safe */
	atomic_or(&event_flags, events);

	/* Signal the waiter - k_sem_give is ISR-safe */
	k_sem_give(&event_sem);
}

uint32_t icle_events_wait(uint32_t events, bool reset, k_timeout_t timeout)
{
	uint32_t current;
	uint32_t matched;

	if (!initialized)
		return 0;

	if (K_TIMEOUT_EQ(timeout, K_NO_WAIT)) {
		/* Non-blocking: just read current flags */
		current = (uint32_t)atomic_get(&event_flags);
		matched = current & events;

		if (matched && reset)
			atomic_and(&event_flags, ~matched);

		return matched;
	}

	/*
	 * Blocking wait: use k_sem_take to sleep until events are posted.
	 * Only K_FOREVER is used here (K_NO_WAIT handled above).
	 */
	for (;;) {
		/* Check if events are already pending */
		current = (uint32_t)atomic_get(&event_flags);
		matched = current & events;

		if (matched) {
			if (reset)
				atomic_and(&event_flags, ~matched);
			return matched;
		}

		/* Wait for signal from icle_events_post */
		k_sem_take(&event_sem, timeout);

		/*
		 * If timeout was not K_FOREVER, could have timed out.
		 * Check once more and return.
		 */
		if (!K_TIMEOUT_EQ(timeout, K_FOREVER)) {
			current = (uint32_t)atomic_get(&event_flags);
			matched = current & events;
			if (matched && reset)
				atomic_and(&event_flags, ~matched);
			return matched;
		}
	}
}

void icle_events_clear(uint32_t events)
{
	if (!initialized)
		return;

	atomic_and(&event_flags, ~events);
}

uint32_t icle_events_get(void)
{
	if (!initialized)
		return 0;

	return (uint32_t)atomic_get(&event_flags);
}
