// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/iface/iface.h>

#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "services.h"
#include "threads.h"

LOG_MODULE_REGISTER(registry, CONFIG_CK_CIPHER_REGISTRY_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     Service Registry
 *---------------------------------------------------------------------------------------------------*/

bool cipher_rpc_exists(cipher_daemon_t *d, cipher_registry_rpc_entry_t *entry) {

    // If the device if, service id and name match, service is present
    for (size_t i = 0; i < ARRAY_SIZE(d->rpc_registry.entries); i++) {

        cipher_registry_rpc_entry_t *current_entry = d->rpc_registry.entries[i];

        if (current_entry->id == entry->id) {
            continue;
        }

        return true;
    }

    return false;
}

bool cipher_rpc_entry_register(cipher_daemon_t *d, cipher_registry_rpc_entry_t *entry) {
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

cipher_registry_rpc_entry_t *cipher_rpc_get_entry(cipher_daemon_t *d, uint16_t service_id, uint16_t op_id) {
    for (size_t i = 0; i < ARRAY_SIZE(d->rpc_registry.entries); i++) {
        if (d->rpc_registry.entries[i] == NULL) {
            continue;
        }

        if (d->rpc_registry.entries[i]->service_id != service_id) {
            continue;
        }

        if (d->rpc_registry.entries[i]->op_id != op_id) {
            continue;
        }

        return d->rpc_registry.entries[i];
    }

    WARN("RPC entry not found");
    return NULL;
}

void cipher_rpc_entry_unregister(cipher_daemon_t *d, cipher_registry_rpc_entry_t *entry) {
    // Iterate through the registry entries
    for (size_t i = 0; i < ARRAY_SIZE(d->rpc_registry.entries); i++) {
        // Check if the current entry is not NULL and matches the entry to be unregistered
        if (d->rpc_registry.entries[i] != NULL && d->rpc_registry.entries[i]->id == entry->id) {
            // Set the entry to NULL and mark it as unused
            d->rpc_registry.entries[i]->_used = false;
            d->rpc_registry.entries[i] = NULL;
            return;  // Exit once the entry is found and unregistered
        }
    }

    // If we get here, it means the entry was not found in the registry
    WARN("RPC entry to unregister not found");
}

cipher_ops_entry_t *find_op_in_registry(cipher_daemon_t *d, cipher_header_t *header) {

    // First find the service
    cipher_service_entry_t *entry = NULL;
    for (size_t i = 0; i < ARRAY_SIZE(d->service_registry.entries); i++) {

        cipher_service_entry_t *current_entry = &d->service_registry.entries[i];

        // Find the matching service id
        if (current_entry->service.id == header->service_id) {
            entry = current_entry;
            break;
        }
    }

    // Then find the op in the service
    if (entry) {
        for (size_t i = 0; i < entry->service.num_ops; i++) {

            cipher_ops_entry_t *op = &entry->service.ops[i];

            if (op->id != header->operation_id) {
                continue;
            }

            return op;
        }
    }

    return NULL;
}
