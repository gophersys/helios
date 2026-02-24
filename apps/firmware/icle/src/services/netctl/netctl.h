/*
 * ICLE Network Control Service - API
 *
 * Ported from Helios runtime netctl module.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef ICLE_SERVICES_NETCTL_H
#define ICLE_SERVICES_NETCTL_H

#include "types.h"

/**
 * @defgroup netctl Network Control Service
 * @brief Central control system for IP-capable network interfaces
 * @{
 */

/*
 * Lifecycle
 */

int netctl_init(netctl_t *ctl, netctl_event_cb_t cb, void *user_data);
int netctl_deinit(netctl_t *ctl);

/*
 * Profile Management
 */

int netctl_profile_register(netctl_t *ctl, const netctl_profile_t *profile);
int netctl_profile_unregister(netctl_t *ctl, const char *name);
const netctl_profile_t *netctl_profile_get(netctl_t *ctl, const char *name);

/*
 * Connection Control
 */

int netctl_connect(netctl_t *ctl, const char *profile_name);
int netctl_connect_with_creds(netctl_t *ctl, const netctl_profile_t *profile);
int netctl_disconnect(netctl_t *ctl, netctl_iface_t iface);
int netctl_disconnect_all(netctl_t *ctl);
int netctl_reset(netctl_t *ctl, netctl_iface_t iface);

/*
 * State Query
 */

netctl_state_t netctl_get_state(netctl_t *ctl, netctl_iface_t iface);
bool netctl_is_online(netctl_t *ctl);
netctl_iface_t netctl_get_active_iface(netctl_t *ctl);
const netctl_profile_t *netctl_get_active_profile(netctl_t *ctl);

/*
 * High-Level Convenience
 */

int netctl_request_internet(netctl_t *ctl);

/*
 * Event Subscription
 */

int netctl_subscribe(netctl_t *ctl, netctl_event_cb_t cb, void *user_data);
int netctl_unsubscribe(netctl_t *ctl, netctl_event_cb_t cb);

/** @} */

#endif /* ICLE_SERVICES_NETCTL_H */
