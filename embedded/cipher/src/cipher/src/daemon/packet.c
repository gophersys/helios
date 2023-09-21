// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "protocol/protocol.h"
#include "utils/err.h"

// Private include
#include "threads.h"
#include "controller.h"
#include "packet.h"

inline cipher_iface_packet_info_t *alloc_iface_packet_info(cipher_daemon_t *d, size_t payload_size)
{
    cipher_iface_packet_info_t *packet_info = k_heap_alloc(&d->local_packets_heap, sizeof(cipher_iface_packet_info_t), K_FOREVER);
    if (!packet_info)
    {
        return NULL;
    }

    packet_info->packet = k_heap_alloc(&d->local_packets_heap, sizeof(cipher_packet_t), K_FOREVER);
    if (!packet_info->packet)
    {
        k_heap_free(&d->local_packets_heap, packet_info);
        return NULL;
    }

    packet_info->packet->payload = k_heap_alloc(&d->local_packets_heap, payload_size, K_FOREVER);
    if (!packet_info->packet->payload)
    {
        k_heap_free(&d->local_packets_heap, packet_info->packet);
        k_heap_free(&d->local_packets_heap, packet_info);
        return NULL;
    }

    return packet_info;
}

inline void free_iface_packet_info(cipher_daemon_t *d, cipher_iface_packet_info_t *packet_info)
{
    if (packet_info)
    {
        if (packet_info->packet)
        {
            if (packet_info->packet->payload)
            {
                k_heap_free(&d->local_packets_heap, packet_info->packet->payload);
            }
            k_heap_free(&d->local_packets_heap, packet_info->packet);
        }
        k_heap_free(&d->local_packets_heap, packet_info);
    }
}
