#ifndef PACKET_INFO_H
#define PACKET_INFO_H

#include "daemon/daemon.h"

cipher_packet_fifo_item_t *alloc_packet_fifo_item(cipher_daemon_t *d, size_t payload_size);
void free_packet_fifo_item(cipher_daemon_t *d, cipher_packet_fifo_item_t *fifo_item);

#endif