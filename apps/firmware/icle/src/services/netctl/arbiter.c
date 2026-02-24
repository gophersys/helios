/*
 * ICLE Network Control Service - Interface Arbiter
 *
 * Simplified for ICLE - no BLE on this platform.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <errno.h>

#include "arbiter.h"
#include "netctl.h"

int netctl_arbiter_can_activate_wifi(netctl_t *ctl)
{
	ARG_UNUSED(ctl);
	/* ICLE has no BLE - WiFi can always be activated */
	return 0;
}
