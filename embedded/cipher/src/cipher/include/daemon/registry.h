#ifndef REGISTRY_H
#define REGISTRY_H

// Cipher includes
#include "config/daemon.h"
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/service.h"

/**
 * @brief Check the internal daemon register for service entry existence
 *
 * @param d The daemon
 * @param entry The entry we want to check for
 * @retval true If found
 * @retval false If not found
 */
bool cipher_service_exists(cipher_daemon_t *d, cipher_service_entry_t *entry);

/**
 * @brief Add an entry to the daemon's service registry
 *
 * If trying to register a local service, the device id must match the daemon's
 * device id, and if trying to register a remote service, the device id must not
 * match the daemon's device id
 *
 * @param d The daemon
 * @param entry The new entry we want to add
 * @retval true If the entry was added succesfully, or it already exists
 * @retval false If there's not enough space in the registry
 */
bool cipher_service_register(cipher_daemon_t *d, cipher_service_entry_t *entry);

/**
 * @brief Remove an entry from the daemon's service registry
 *
 * @param d The daemon
 * @param entry The current entry we want to remove
 * @retval true If the entry was removed succesfully
 * @retval false If the entry wasn't found in the registry
 */
bool cipher_service_unregister(cipher_daemon_t *d, cipher_service_entry_t *entry);

/**
 * @brief Get the interface where a destination device is located
 *
 * @param d The daemon
 * @param device_id The device for which we want to find the interface
 * @return cipher_iface_t* NULL if not found, pointer to an interface otherwise
 */
cipher_iface_t *cipher_get_iface_by_device_id(cipher_daemon_t *d, uint16_t device_id);

#endif