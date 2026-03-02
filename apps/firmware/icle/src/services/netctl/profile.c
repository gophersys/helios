// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Network Control Service - Profile Management
 *
 * Ported from Helios runtime netctl module.
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <errno.h>
#include <string.h>

#include "netctl.h"

#ifndef CONFIG_ICLE_NETCTL_LOG_LEVEL
#define CONFIG_ICLE_NETCTL_LOG_LEVEL 3
#endif

LOG_MODULE_DECLARE(netctl, CONFIG_ICLE_NETCTL_LOG_LEVEL);

int netctl_profile_register(netctl_t *ctl, const netctl_profile_t *profile)
{
	if (ctl == NULL || !ctl->initialized || profile == NULL)
		return -EINVAL;

	if (profile->name[0] == '\0') {
		LOG_ERR("Profile name cannot be empty");
		return -EINVAL;
	}

	k_mutex_lock(&ctl->lock, K_FOREVER);

	/* Check for duplicate name */
	for (int i = 0; i < ctl->profile_count; i++) {
		if (strncmp(ctl->profiles[i].name, profile->name,
			    CONFIG_ICLE_NETCTL_PROFILE_NAME_MAX) == 0) {
			LOG_WRN("Profile already exists: %s", profile->name);
			k_mutex_unlock(&ctl->lock);
			return -EEXIST;
		}
	}

	/* Check capacity */
	if (ctl->profile_count >= CONFIG_ICLE_NETCTL_MAX_PROFILES) {
		LOG_ERR("Profile storage full");
		k_mutex_unlock(&ctl->lock);
		return -ENOMEM;
	}

	/* Copy profile */
	memcpy(&ctl->profiles[ctl->profile_count], profile, sizeof(netctl_profile_t));
	ctl->profile_count++;

	LOG_INF("Profile registered: %s (iface=%d, priority=%d)",
		profile->name, profile->iface, profile->priority);

	k_mutex_unlock(&ctl->lock);
	return 0;
}

int netctl_profile_unregister(netctl_t *ctl, const char *name)
{
	int found_idx = -1;

	if (ctl == NULL || !ctl->initialized || name == NULL)
		return -EINVAL;

	k_mutex_lock(&ctl->lock, K_FOREVER);

	for (int i = 0; i < ctl->profile_count; i++) {
		if (strncmp(ctl->profiles[i].name, name,
			    CONFIG_ICLE_NETCTL_PROFILE_NAME_MAX) == 0) {
			found_idx = i;
			break;
		}
	}

	if (found_idx < 0) {
		LOG_WRN("Profile not found: %s", name);
		k_mutex_unlock(&ctl->lock);
		return -ENOENT;
	}

	if (ctl->active_profile == &ctl->profiles[found_idx]) {
		LOG_WRN("Cannot unregister active profile: %s", name);
		k_mutex_unlock(&ctl->lock);
		return -EBUSY;
	}

	/* Remove by shifting remaining profiles down */
	for (int i = found_idx; i < ctl->profile_count - 1; i++)
		memcpy(&ctl->profiles[i], &ctl->profiles[i + 1], sizeof(netctl_profile_t));

	ctl->profile_count--;

	memset(&ctl->profiles[ctl->profile_count], 0, sizeof(netctl_profile_t));

	LOG_INF("Profile unregistered: %s", name);

	k_mutex_unlock(&ctl->lock);
	return 0;
}

const netctl_profile_t *netctl_profile_get(netctl_t *ctl, const char *name)
{
	if (ctl == NULL || !ctl->initialized || name == NULL)
		return NULL;

	k_mutex_lock(&ctl->lock, K_FOREVER);

	for (int i = 0; i < ctl->profile_count; i++) {
		if (strncmp(ctl->profiles[i].name, name,
			    CONFIG_ICLE_NETCTL_PROFILE_NAME_MAX) == 0) {
			k_mutex_unlock(&ctl->lock);
			return &ctl->profiles[i];
		}
	}

	k_mutex_unlock(&ctl->lock);
	return NULL;
}
