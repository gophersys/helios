#ifndef SERVICES_H
#define SERVICES_H

// Cipher includes
#include "daemon/daemon.h"

// Event handlers
void handle_sd_packet_event(cipher_daemon_t *d);

/**
 * @brief Event handler for a new interface connection detected
 *
 * This event will cycle through the daemon's registry, and send all the services available
 * to this interface out to the newly connected interface as service discovery payloads
 *
 * @param d The daemon
 */
void handle_iface_conn_event(cipher_daemon_t *d);

/**
 * @brief Event handler for an interface disconnection detected
 *
 * This event will broadcast to all affected interfaces about the loss of service, and then
 * update the service registry by removing all related services to this interface
 *
 * @param d The daemon
 */
void handle_iface_disconn_event(cipher_daemon_t *d);

/**
 * @brief Send a cipher packet with a service discovery payload to the ifaces send thread
 *
 * @param d The daemon
 * @param iface The interface that will send the packet
 * @param sd_payload The desired payload to put in the packet
 */
void send_service_payload(cipher_daemon_t *d, cipher_iface_t *iface, cipher_payload_sd_broadcast_t *sd_payload);

/**
 * @brief Send a service update to all connected interfaces.
 *
 * This function constructs a service discovery payload using provided entry details and broadcasts
 * it over all connected interfaces of the daemon. It's possible to specify an interface to omit
 * when broadcasting the update. The function handles both service availability and unavailability updates.
 *
 * @param d         Pointer to the daemon that holds the connected interfaces.
 * @param entry     Pointer to the service entry for which the update should be sent.
 * @param omit_iface Pointer to an interface that should be omitted when broadcasting. Can be NULL if no omission is needed.
 * @param alive     Boolean flag indicating service availability. Set to `true` if the service is available, and `false` otherwise.
 */
void send_service_update(cipher_daemon_t *d, cipher_service_entry_t *entry, cipher_iface_t *omit_iface, bool alive);

#endif