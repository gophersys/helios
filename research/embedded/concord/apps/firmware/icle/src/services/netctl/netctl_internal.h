// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Network Control Service - Internal API
 *
 * Functions shared between netctl.c and interface implementations.
 * NOT part of the public API.
 */

#ifndef ICLE_SERVICES_NETCTL_INTERNAL_H
#define ICLE_SERVICES_NETCTL_INTERNAL_H

#include "types.h"

/*
 * Notification functions (implemented in netctl.c)
 * Called by interface implementations to report state changes.
 */

void netctl_notify_connected(netctl_t *ctl, netctl_iface_t iface);
void netctl_notify_disconnected(netctl_t *ctl, netctl_iface_t iface);
void netctl_notify_connection_failed(netctl_t *ctl, netctl_iface_t iface, int error_code);
void netctl_notify_ip_acquired(netctl_t *ctl, netctl_iface_t iface,
			       const char *ip_addr, const char *gateway, const char *netmask);

/*
 * Interface-specific init/deinit (implemented in wifi_sta.c, etc.)
 */
#ifdef CONFIG_ICLE_NETCTL_WIFI

int netctl_wifi_init(netctl_t *ctl);
int netctl_wifi_deinit(netctl_t *ctl);
int netctl_wifi_connect(netctl_t *ctl, const netctl_wifi_creds_t *creds);
int netctl_wifi_disconnect(netctl_t *ctl);

#endif /* CONFIG_ICLE_NETCTL_WIFI */

#endif /* ICLE_SERVICES_NETCTL_INTERNAL_H */
