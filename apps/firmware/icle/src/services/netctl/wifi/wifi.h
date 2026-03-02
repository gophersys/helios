// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Network Control Service - WiFi API
 *
 * Ported from Helios runtime netctl module.
 */

#ifndef ICLE_SERVICES_NETCTL_WIFI_H
#define ICLE_SERVICES_NETCTL_WIFI_H

#include "../types.h"

/**
 * @brief Trigger a WiFi network scan
 */
int netctl_wifi_scan(netctl_t *ctl);

/**
 * @brief Get WiFi scan results
 */
int netctl_wifi_get_scan_results(netctl_t *ctl, netctl_event_scan_result_t *results,
				 size_t max_results, size_t *count);

/*
 * Internal WiFi API (called by netctl core)
 */

int netctl_wifi_init(netctl_t *ctl);
int netctl_wifi_deinit(netctl_t *ctl);
int netctl_wifi_connect(netctl_t *ctl, const netctl_wifi_creds_t *creds);
int netctl_wifi_disconnect(netctl_t *ctl);

#endif /* ICLE_SERVICES_NETCTL_WIFI_H */
