// Standard includes
#include <stdio.h>

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

LOG_MODULE_REGISTER(registry, REGISTRY_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Verifies that the service entry being requested makes sense
 *
 * Checks that there's no clashing of ids, null interfaces, etc
 *
 * @param d The daemon
 * @param entry The entry to check
 * @retval true If the entry is valid
 * @retval false If there's an invalid setting, printed as WARN
 */
static bool verify_service_entry(cipher_daemon_t *d, cipher_service_entry_t *entry);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                   API Implementation
 *---------------------------------------------------------------------------------------------------*/

bool cipher_service_exists(cipher_daemon_t *d, cipher_service_entry_t *entry) {

    // If the device if, service id and name match, service is present
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *current_entry = &d->service_registry.entries[i];

        if (current_entry->service.device_id != entry->service.device_id) {
            continue;
        }

        if (current_entry->service.service_id == entry->service.service_id) {

            // Check that there aren't services with same ids but different names
            if (strcmp(current_entry->service.name, entry->service.name) != 0) {
                ERROR("Found existing entry with name \"%s\" and id %d, but new entry has name \"%s\" and id %d",
                      current_entry->service.name, current_entry->service.service_id,
                      entry->service.name, entry->service.service_id);
            }

            continue;
        }

        DBG("Service %d, at device %d, on iface %d found in daemon's %d registry",
            entry->service.service_id, entry->service.device_id, entry->iface->id, d->id);

        return true;
    }

    DBG("Service %d, at device %d, on iface %d not in daemon's %d registry",
        entry->service.service_id, entry->service.device_id, entry->iface->id, d->id);

    return false;
}

bool cipher_service_register(cipher_daemon_t *d, cipher_service_entry_t *entry) {

    if (!verify_service_entry(d, entry)) {
        return false;
    }

    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *current_entry = &d->service_registry.entries[i];

        if (current_entry->_used == true) {
            continue;
        }

        memcpy(current_entry, entry, sizeof(cipher_service_entry_t));
        current_entry->_used = true;

        DBG("Service %d, at device %d registered, daemon %d, allowed hops %d",
            entry->service.service_id, entry->service.device_id, d->id, entry->service.allowed_hops);

        return true;
    }

    WARN("Daemon %d service registry is full, number of entries: %d!", d->id, ARRAY_SIZE(d->service_registry.entries));
    return false;
}

bool cipher_service_unregister(cipher_daemon_t *d, cipher_service_entry_t *entry) {

    if (!cipher_service_exists(d, entry)) {
        return false;
    }

    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *current_entry = &d->service_registry.entries[i];

        if (current_entry->service.device_id != entry->service.device_id) {
            continue;
        }

        if (current_entry->service.service_id != entry->service.service_id) {
            continue;
        }

        if (strcmp(current_entry->service.name, entry->service.name) != 0) {
            continue;
        }

        memset(current_entry, 0, sizeof(cipher_service_entry_t));

        DBG("Service %d, for device %d, on iface %d removed from daemon's %d registry",
            entry->service.service_id, entry->service.device_id, entry->iface->id, d->id);

        return true;
    }

    return false;
}

cipher_iface_t *cipher_get_iface_by_device_id(cipher_daemon_t *d, uint16_t device_id) {

    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *current_entry = &d->service_registry.entries[i];

        if (current_entry->service.device_id != device_id) {
            continue;
        }

        DBG("Device %d is at iface %d, daemon %d", device_id, current_entry->iface->id, d->id);

        return current_entry->iface;
    }

    DBG("Device %d not found on daemons' %d interfaces", device_id, d->id);

    return NULL;
}

bool cipher_rpc_exists(cipher_daemon_t *d, cipher_rpc_entry_t *entry) {

    // If the device if, service id and name match, service is present
    for (size_t i = 0; i < ARRAY_SIZE(d->rpc_registry.entries); i++) {

        cipher_rpc_entry_t *current_entry = d->rpc_registry.entries[i];

        if (current_entry->id == entry->id) {
            continue;
        }

        return true;
    }

    return false;
}

bool cipher_rpc_entry_register(cipher_daemon_t *d, cipher_rpc_entry_t *entry) {
    for (size_t i = 0; i < ARRAY_SIZE(d->rpc_registry.entries); i++) {
        if (d->rpc_registry.entries[i] != NULL) {
            if (d->rpc_registry.entries[i]->_used) {
                continue;
            }
        }

        d->rpc_registry.entries[i] = entry;
        d->rpc_registry.entries[i]->_used = true;
        return true;
    }

    WARN("RPC registry full");
    return false;
}

bool cipher_rpc_entry_unregister(cipher_daemon_t *d, cipher_rpc_entry_t *entry) {
    ERROR("%s: not implemented", __func__);
}

cipher_ops_entry_t *find_op_in_registry(cipher_daemon_t *d, cipher_packet_t *packet) {

    // First find the service
    cipher_service_entry_t *entry = NULL;
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *e = &d->service_registry.entries[i];

        // Ensure its a local service
        if (!e->local) {
            continue;
        }

        // Find the matching service id
        if (e->service.service_id == packet->header.service_id) {
            entry = e;
            break;
        }
    }

    // Then find the op in the service
    if (entry) {

        for (size_t i = 0; i < entry->service.num_ops; i++) {

            cipher_ops_entry_t *op = &entry->service.ops[i];

            if (op->id != packet->header.operation_id) {
                continue;
            }

            return op;
        }
    }

    return NULL;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Verify Entry
 *---------------------------------------------------------------------------------------------------*/
static bool verify_service_entry(cipher_daemon_t *d, cipher_service_entry_t *entry) {

    if (cipher_service_exists(d, entry)) {
        return true;
    }

    if (entry->local) {
        if (entry->iface != NULL) {
            WARN("Cannot register a local service %d with a non-null iface, daemon %d",
                 entry->service.service_id, d->id);

            return false;
        }

        if (entry->service.device_id != d->device_id) {
            WARN("Expected local service device id to be %d, got %d, daemon %d",
                 d->device_id, entry->service.service_id, d->id);

            return false;
        }
    } else {
        if (entry->iface == NULL) {
            WARN("Cannot register remote service %d with a null iface, daemon %d",
                 entry->service.service_id, d->id);

            return false;
        }

        if (entry->service.device_id == d->device_id) {
            WARN("Cannot register remote device id %d, same as local id %d, daemon %d",
                 entry->service.service_id, d->device_id, d->id);

            return false;
        }
    }

    return true;
}