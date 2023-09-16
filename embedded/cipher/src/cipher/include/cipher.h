#ifndef CIPHER_H
#define CIPHER_H

#include <stdbool.h>

#include <zephyr/kernel.h>

// CoreKinect includes
#include "tal.h"

typedef struct
{
    // Interfaces
    tal_config_t uplink_cfg;
    tal_config_t downlink_cfg; // TODO: me

    // Threads
    k_tid_t uplink_listener_tid;
    k_tid_t downlink_listener_tid; // TODO: me
} cipher_daemon_t;

void init_cipher(cipher_daemon_t *daemon);

/**
 * @brief Ensure that node at end point matches protocol version, and exchange configs
 *
 * @param cfg The transport interface configuration
 * @return true If node was handshook correctly
 * @return false If node protocol version mismatch or connection issue occurs
 */
bool cipher_handshake(const tal_config_t *cfg);

bool cipher_threads_init(cipher_daemon_t *daemon);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Protocol
 *---------------------------------------------------------------------------------------------------*/

// Cipher Header (11 bytes)
typedef struct __attribute__((packed))
{
    uint16_t source_id;         // Up to 65536 devices on a single network
    uint16_t destination_id;    // Up to 65536 devices on a single network
    uint32_t service_id : 14;   // Up to 16384 services
    uint32_t operation_id : 8;  // Up to 256 operations per service
    uint32_t payload_len : 10;  // Header + Payload will never exceed 1024 bytes
    uint16_t sequence_num : 13; // Up to ~8MB streams (8192 sequences * 1005 bytes payload)
    uint16_t type : 3;          // Up to 8 types (RPC, event, pub/sub, admin, etc)
    uint8_t flags;              // Protocol/admin level communication (unimplemented methods, etc)
} cipher_packet_header_t;

void cipher_print_header(const cipher_packet_header_t *header);
bool cipher_packet_parse_header(const uint8_t *recv_buffer, uint16_t recv_buffer_size, cipher_packet_header_t *header_buffer);

#endif // RAL_H