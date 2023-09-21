#ifndef PACKET_INFO_H
#define PACKET_INFO_H

#include "daemon/daemon.h"

cipher_iface_packet_info_t *alloc_iface_packet_info(cipher_daemon_t *d, size_t payload_size);
void free_iface_packet_info(cipher_daemon_t *d, cipher_iface_packet_info_t *packet_info);

#endif