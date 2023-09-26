#ifndef REGISTRY_H
#define REGISTRY_H

// Cipher includes
#include "config/daemon.h"
#include "config/default.h"
#include "daemon/daemon.h"

/**
 * @brief Check the internal daemon register for service entry existence
 *
 * @param d The daemon
 * @param entry The entry we want to check for
 * @retval true If found
 * @retval false If not found
 */
bool service_exists(cipher_daemon_t *d, cipher_service_entry_t *entry);

/**
 * @brief Add an entry to the daemon's service registry
 *
 * @param d The daemon
 * @param entry The new entry we want to add
 * @retval true If the entry was added succesfully, or it already exists
 * @retval false If there's not enough space in the registry
 */
bool service_register(cipher_daemon_t *d, cipher_service_entry_t *entry);

/**
 * @brief Remove an entry from the daemon's service registry
 *
 * @param d The daemon
 * @param entry The current entry we want to remove
 * @retval true If the entry was removed succesfully
 * @retval false If the entry wasn't found in the registry
 */
bool service_unregister(cipher_daemon_t *d, cipher_service_entry_t *entry);

#endif