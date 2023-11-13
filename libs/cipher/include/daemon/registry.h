#ifndef REGISTRY_H
#define REGISTRY_H

// Cipher includes
#include "config/daemon.h"
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/service.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Services
 *---------------------------------------------------------------------------------------------------*/
/**
 * @brief Check the internal daemon register for service entry existence
 *
 * @param d The daemon
 * @param entry The entry we want to check for
 * @retval true If found
 * @retval false If not found
 */
bool registry_service_exists(cipher_daemon_t *d, cipher_service_entry_t *entry);

/**
 * @brief Add an entry to the daemon's service registry
 *
 * @param d The daemon
 * @param entry The new entry we want to add
 * @retval true If the entry was added succesfully, or it already exists
 * @retval false If there's not enough space in the registry
 */
bool registry_service_add(cipher_daemon_t *d, cipher_service_entry_t *entry);

/**
 * @brief Remove an entry from the daemon's service registry
 *
 * @param d The daemon
 * @param entry The current entry we want to remove
 */
void registry_service_remove(cipher_daemon_t *d, cipher_service_entry_t *entry);

/**
 * @brief Check that the end point doesn't already exist in the service
 *
 * @param d The daemon
 * @param entry The service you want to check
 * @param end_point The end point you want to check existence of in the service
 * @return true If it exists
 * @return false It it doesn't exist
 */
bool registry_end_point_exists(cipher_daemon_t *d, cipher_service_entry_t *service,
                               cipher_service_end_point_t *entry);

/**
 * @brief Add an end point for a service entry
 *
 * @param d The daemon
 * @param entry The entry you want to add a new end point to
 * @param end_point The metadata of the new end point
 * @return true If the end point was added succesfully, or it already exists
 * @return false If there's not enough space in the service's end point list
 */
bool registry_end_point_add_to_service(cipher_daemon_t *d, cipher_service_entry_t *service,
                                       cipher_service_end_point_t *entry);

/**
 * @brief Remove an end point from a service entry
 *
 * @param d The daemon
 * @param entry The entry you want to remove an end point from
 * @param end_point The metadata of the end point to remove
 */
void registry_end_point_rm_from_service(cipher_daemon_t *d, cipher_service_entry_t *service,
                                        cipher_service_end_point_t *entry);

bool registry_add_device_to_iface(cipher_daemon_t *d, cipher_iface_t *iface, uint16_t device_id);

/**
 * @brief Get the interface where a destination device is located
 *
 * @param d The daemon
 * @param device_id The device for which we want to find the interface
 * @return cipher_iface_t* NULL if not found, pointer to an interface otherwise
 */
cipher_iface_t *registry_get_iface(cipher_daemon_t *d, uint16_t device_id);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  RPC
 *---------------------------------------------------------------------------------------------------*/
bool cipher_rpc_exists(cipher_daemon_t *d, cipher_rpc_entry_t *entry);
bool cipher_rpc_entry_register(cipher_daemon_t *d, cipher_rpc_entry_t *entry);
cipher_rpc_entry_t *cipher_rpc_get_entry(cipher_daemon_t *d, uint16_t service_id, uint16_t op_id);
void cipher_rpc_entry_unregister(cipher_daemon_t *d, cipher_rpc_entry_t *entry);
cipher_ops_entry_t *find_op_in_registry(cipher_daemon_t *d, cipher_header_t *header);

#endif