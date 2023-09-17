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

    // Threads
    k_tid_t controller_tid;
    k_tid_t service_discovery_tid;
    k_tid_t uplink_listener_tid;
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

typedef enum
{
    CIPHER_PACKET_TYPE_RPC,
    CIPHER_PACKET_TYPE_EVENT,

    CIPHER_PACKET_TYPE_SD,

    CIPHER_PACKET_TYPE_MAX
} cipher_packet_type_t;

typedef struct
{
    // TODO: me
    uint8_t dummy;
} cipher_service_discovery_payload_t;

typedef struct
{
    cipher_packet_type_t header;
    cipher_service_discovery_payload_t payload;
} cipher_service_discovery_packet_t;

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
} cipher_header_t;

void cipher_print_header(const cipher_header_t *header);
bool cipher_packet_parse_header(const uint8_t *recv_buffer, uint16_t recv_buffer_size, cipher_header_t *header_buffer);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Buffers
 *---------------------------------------------------------------------------------------------------*/
uint8_t *cipher_new_buffer(size_t size);
void cipher_free_buffer(uint8_t *buffer);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Serdes
 *---------------------------------------------------------------------------------------------------*/

typedef enum
{
    CIPHER_ERROR_OK,
    CIPHER_ERROR_MAX
} cipher_error_t;

typedef struct
{
    cipher_header_t *header;
    uint8_t *raw_payload;
    size_t raw_payload_size;
    void *decoded_payload;
} cipher_decode_args_t;

typedef struct
{
    cipher_header_t *header;
    void *raw_payload;
    size_t raw_payload_size;
    uint8_t *encoded_payload;
} cipher_encode_args_t;

cipher_error_t cipher_encode_packet(cipher_encode_args_t args);
cipher_error_t cipher_decode_packet(cipher_decode_args_t args);

#endif // RAL_H