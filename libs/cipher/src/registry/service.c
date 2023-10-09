// Standard includes
#include <ctype.h>
#include <stdio.h>
#include <string.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "protocol/protocol.h"
#include "protocol/serdes.h"
#include "transport/transport.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "services.h"
#include "threads.h"

LOG_MODULE_DECLARE(registry);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

static void print_service_info(cipher_service_entry_t *entry);
static void print_end_point_info(cipher_service_end_point_t *entry);

/**
 * @brief Verifies that the service entry metadata requested makes sense
 *
 * Checks that there's no clashing of ids, null interfaces, etc
 *
 * @param d The daemon
 * @param entry The entry to check
 * @retval true If the entry is valid
 * @retval false If there's an invalid setting, printed as WARN
 */
static bool verify_service_entry(cipher_daemon_t *d, cipher_service_entry_t *entry);

/**
 * @brief Verifies that the end point entry metadata makes sense
 *
 * Checks that there's no clashing of ids, null interfaces, etc
 *
 * @param d The daemon
 * @param entry The entry to check
 * @retval true If the entry is valid
 * @retval false If there's an invalid setting, printed as WARN
 */
static bool verify_end_point_entry(cipher_daemon_t *d, cipher_service_end_point_t *entry);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     Service Registry
 *---------------------------------------------------------------------------------------------------*/

bool registry_service_exists(cipher_daemon_t *d, cipher_service_entry_t *entry) {

    if (!verify_service_entry(d, entry)) {
        return false;
    }

    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *current_entry = &d->service_registry.entries[i];

        if (!current_entry->_used) {
            continue;
        }

        if (current_entry->service.id != entry->service.id) {
            continue;
        }

        // Check that there aren't services with same ids but different names
        if (strcmp(current_entry->service.name, entry->service.name) != 0) {
            ERROR("Found existing entry with name \"%s\" and id %d, but new entry has name \"%s\" and id %d",
                  current_entry->service.name, current_entry->service.id,
                  entry->service.name, entry->service.id);
        }

        DBG("Service %d found in daemon's %d registry", entry->service.id, d->id);
        return true;
    }

    DBG("Service %d not found in daemon's %d registry", entry->service.id, d->id);
    return false;
}

bool registry_service_add(cipher_daemon_t *d, cipher_service_entry_t *entry) {

    if (registry_service_exists(d, entry)) {
        return true;
    }

    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *current_entry = &d->service_registry.entries[i];

        if (current_entry->_used == true) {
            continue;
        }

        memcpy(current_entry, entry, sizeof(cipher_service_entry_t));
        current_entry->_used = true;

        DBG("Service %s registered, daemon %d", entry->service.name, d->id);
        print_service_info(entry);
        return true;
    }

    WARN("Daemon %d service registry is full, number of entries: %d!", d->id, ARRAY_SIZE(d->service_registry.entries));
    return false;
}

void registry_service_remove(cipher_daemon_t *d, cipher_service_entry_t *entry) {

    if (!registry_service_exists(d, entry)) {
        return;
    }

    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *current_entry = &d->service_registry.entries[i];

        if (current_entry->service.id != entry->service.id) {
            continue;
        }

        if (strcmp(current_entry->service.name, entry->service.name) != 0) {
            continue;
        }

        memset(current_entry, 0, sizeof(cipher_service_entry_t));

        DBG("Service %s removed from daemon's %d registry", entry->service.name, d->id);
    }
}

bool registry_end_point_exists(cipher_daemon_t *d, cipher_service_entry_t *service,
                               cipher_service_end_point_t *entry) {

    if (!verify_end_point_entry(d, entry)) {
        return false;
    }

    for (size_t i = 0; i < ARRAY_SIZE(service->end_points); i++) {

        if (!service->end_points[i]._used) {
            continue;
        }

        if (service->end_points[i].device_id != entry->device_id) {
            continue;
        }

        if (service->end_points[i].iface->id != entry->iface->id) {
            continue;
        }

        DBG("End point for device id %d for service %s found, iface %d", entry->device_id, service->service.name,
            entry->iface->id);
        return true;
    }

    DBG("End point for device id %d not found for service %s", entry->device_id, service->service.name);
    return false;
}

bool registry_end_point_add_to_service(cipher_daemon_t *d, cipher_service_entry_t *service,
                                       cipher_service_end_point_t *entry) {

    if (registry_end_point_exists(d, service, entry)) {
        return true;
    }

    // Find the matching service in our registry
    cipher_service_entry_t *service_entry = NULL;
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {
        service_entry = &d->service_registry.entries[i];
        if (!service_entry->_used) {
            continue;
        }

        if (service_entry->service.id != service->service.id) {
            continue;
        }

        break;
    }

    if (!service_entry) {
        WARN("No entries in daemon for service %s", service->service.name);
        return false;
    }

    // Find a free end point entry in service
    for (size_t i = 0; i < ARRAY_SIZE(service->end_points); i++) {

        cipher_service_end_point_t *current_entry = &service_entry->end_points[i];

        if (current_entry->_used == true) {
            continue;
        }

        memcpy(&service_entry->end_points[i], entry, sizeof(cipher_service_end_point_t));
        current_entry->_used = true;

        DBG("End point for service %s registered, device id %d", service_entry->service.name, entry->device_id);
        print_end_point_info(entry);
        return true;
    }

    WARN("Daemon %d service %s end point registry is full, number of entries: %d!", d->id, service->service.name,
         ARRAY_SIZE(service->end_points));

    return false;
}

void registry_end_point_rm_from_service(cipher_daemon_t *d, cipher_service_entry_t *service,
                                        cipher_service_end_point_t *entry) {
    if (!registry_end_point_exists(d, service, entry)) {
        return;
    }

    for (size_t i = 0; i < ARRAY_SIZE(service->end_points); i++) {

        cipher_service_end_point_t *current_entry = &service->end_points[i];

        if (current_entry->device_id != entry->device_id) {
            continue;
        }

        if (current_entry->iface != entry->iface) {
            continue;
        }

        memset(current_entry, 0, sizeof(cipher_service_end_point_t));
        DBG("End point for device %d removed from service %s registry, daemon's %d", entry->device_id,
            service->service.name, d->id);
    }
}

bool registry_add_device_to_iface(cipher_daemon_t *d, cipher_iface_t *iface, uint16_t device_id) {
    for (size_t i = 0; i < d->cfg->num_downlink_ifaces; i++) {
        if (&d->downlink_t_g[i].iface != iface) {
            continue;
        }

        for (size_t j = 0; j < ARRAY_SIZE(d->downlink_t_g[i].device_entries); j++) {
            if (d->downlink_t_g[i].device_entries[j]._used) {

                // Device is already registered to interface
                if (d->downlink_t_g[i].device_entries[j].device_id == device_id) {
                    return true;
                }

                continue;
            }

            d->downlink_t_g[i].device_entries[j].device_id = device_id;
            d->downlink_t_g[i].device_entries[j]._used = true;
            return true;
        }
    }

    for (size_t i = 0; i < d->cfg->num_uplink_ifaces; i++) {
        if (&d->uplink_t_g[i].iface != iface) {
            continue;
        }

        for (size_t j = 0; j < ARRAY_SIZE(d->uplink_t_g[i].device_entries); j++) {
            if (d->uplink_t_g[i].device_entries[j]._used) {

                // Device is already registered to interface
                if (d->uplink_t_g[i].device_entries[j].device_id == device_id) {
                    return true;
                }

                continue;
            }

            d->uplink_t_g[i].device_entries[j].device_id = device_id;
            d->uplink_t_g[i].device_entries[j]._used = true;
            return true;
        }
    }

    return false;
}

cipher_iface_t *registry_get_iface(cipher_daemon_t *d, uint16_t device_id) {

    for (size_t i = 0; i < d->cfg->num_downlink_ifaces; i++) {
        if (d->downlink_t_g[i].device_entries[i].device_id != device_id) {
            continue;
        }

        return &d->downlink_t_g->iface;
    }

    for (size_t i = 0; i < d->cfg->num_uplink_ifaces; i++) {
        if (d->uplink_t_g[i].device_entries[i].device_id != device_id) {
            continue;
        }

        return &d->uplink_t_g->iface;
    }

    return NULL;

    // cipher_service_entry_t *current_entry = NULL;
    // for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

    //     // First we find the service
    //     current_entry = &d->service_registry.entries[i];
    //     // if (current_entry->service.id != service_id) {
    //     //     continue;
    //     // }

    //     // Then we find the interface for the device
    //     cipher_service_end_point_t *end_point_entry = NULL;
    //     for (size_t j = 0; j < ARRAY_SIZE(current_entry->end_points); j++) {
    //         end_point_entry = &current_entry->end_points[j];
    //         if (end_point_entry->device_id != device_id) {
    //             continue;
    //         }
    //         break;
    //     }

    //     if (!end_point_entry) {
    //         return NULL;
    //     }

    //     DBG("Device %d is at iface %d for service %s", device_id, end_point_entry->iface->id,
    //         current_entry->service.name);

    //     return end_point_entry->iface;
    // }

    // if (current_entry != NULL) {
    //     DBG("Device %d not found on service %d end points", device_id, service_id);
    // } else {
    //     DBG("Service %d not found on daemon's %d registry", service_id, d->id);
    // }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       Verify Helpers
 *---------------------------------------------------------------------------------------------------*/
static inline bool verify_service_entry(cipher_daemon_t *d, cipher_service_entry_t *entry) {

    if (entry->service.id == 0) {
        WARN("Service cannot have ID 0");
        return false;
    }

    bool is_name_blank = true;
    for (int i = 0; i < strlen(entry->service.name); i++) {
        if (!isspace((unsigned char)entry->service.name[i])) {
            is_name_blank = false;
            break;
        }
    }

    if (is_name_blank) {
        WARN("Service %d name is empty", entry->service.id);
        return false;
    }

    if (entry->service.num_ops < 1) {
        WARN("Service %d has %d operations registered. Must have at least 1", entry->service.id, entry->service.num_ops);
        return false;
    }

    return true;
}

static inline bool verify_end_point_entry(cipher_daemon_t *d, cipher_service_end_point_t *entry) {

    if (entry->device_id == CONFIG_CIPHER_LOCAL_ADDR) {
        if (entry->iface != NULL) {
            WARN("Cannot provide interface when it's a local end point");
            return false;
        }
    }

    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Print Helpers
 *---------------------------------------------------------------------------------------------------*/
static inline void print_service_info(cipher_service_entry_t *entry) {
#if REGISTRY_LOG_LEVEL == LOG_LEVEL_DBG
    LOG("Service %s (%d) info:", entry->service.name, entry->service.id);
    LOG_RAW("\t\tId: %d\n", entry->service.id);
    LOG_RAW("\t\tLocal: %s\n", entry->local ? "true" : "false");
    LOG_RAW("\t\tName: %s\n", entry->service.name);
    LOG_RAW("\t\tHops: %d\n", entry->service.allowed_hops);
    LOG_RAW("\t\tOps: %d\n", entry->service.num_ops);
#endif
}

static inline void print_end_point_info(cipher_service_end_point_t *entry) {
#if REGISTRY_LOG_LEVEL == LOG_LEVEL_DBG
    LOG("End point info:");
    LOG_RAW("\t\tDeviceId: %d\n", entry->device_id);
    LOG_RAW("\t\tIfaceId: %d\n", entry->iface->id);
#endif
}