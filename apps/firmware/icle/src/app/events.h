/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE Event System
 */

#ifndef ICLE_EVENTS_H_
#define ICLE_EVENTS_H_

#include <zephyr/kernel.h>
#include <stdint.h>
#include "icle/app.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize event system
 *
 * @return 0 on success, negative errno on failure
 */
int icle_events_init(void);

/**
 * @brief Post event(s)
 *
 * @param events Event flags to post
 */
void icle_events_post(uint32_t events);

/**
 * @brief Wait for event(s)
 *
 * @param events Event mask to wait for
 * @param reset Whether to clear events on return
 * @param timeout Timeout duration
 * @return Received events, or 0 on timeout
 */
uint32_t icle_events_wait(uint32_t events, bool reset, k_timeout_t timeout);

/**
 * @brief Clear event(s)
 *
 * @param events Event flags to clear
 */
void icle_events_clear(uint32_t events);

/**
 * @brief Get pending events (non-blocking)
 *
 * @return Currently pending events
 */
uint32_t icle_events_get(void);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_EVENTS_H_ */
