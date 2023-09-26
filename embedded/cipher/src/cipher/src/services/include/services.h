#ifndef SERVICES_H
#define SERVICES_H

// Cipher includes
#include "daemon/daemon.h"

// Event handlers
void handle_packet_event(cipher_daemon_t *d);
void handle_iface_conn_event(cipher_daemon_t *d);
void handle_iface_disconn_event(cipher_daemon_t *d);

// Helpers
void send_service_broadcast(cipher_daemon_t *d, cipher_iface_t *iface, cipher_payload_sd_t *sd_payload);

#endif