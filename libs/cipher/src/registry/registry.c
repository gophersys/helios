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
 *                                                                                     Service Registry
 *---------------------------------------------------------------------------------------------------*/

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

cipher_rpc_entry_t *cipher_rpc_get_entry(cipher_daemon_t *d, uint16_t service_id, uint16_t op_id) {
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

void cipher_rpc_entry_unregister(cipher_daemon_t *d, cipher_rpc_entry_t *entry) {
    WARN("%s: not implemented", __func__);
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
