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
void send_service_payload(cipher_daemon_t *d, cipher_iface_t *iface, cipher_payload_sd_t *sd_payload);

#endif