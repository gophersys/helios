// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "transport/transport.h"
#include "daemon/daemon.h"
#include "utils/err.h"

// Private include
#include "threads.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Protocol
 *---------------------------------------------------------------------------------------------------*/

typedef enum
{
    CIPHER_PACKET_TYPE_SD,
    CIPHER_PACKET_TYPE_RPC,
    CIPHER_PACKET_TYPE_EVENT,

    CIPHER_PACKET_TYPE_MAX
} cipher_packet_type_t;

// Cipher Header (12 bytes)
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
    uint8_t hop_count;          // TODO: Serdes for me
} cipher_header_t;

typedef struct
{
    cipher_header_t header;
    void *payload;
} cipher_packet_t;

void cipher_print_header(const cipher_header_t *header);
bool cipher_packet_parse_header(const uint8_t *recv_buffer, uint16_t recv_buffer_size, cipher_header_t *header_buffer);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Serdes
 *---------------------------------------------------------------------------------------------------*/

typedef enum
{
    CIPHER_ERROR_OK,
    CIPHER_ERROR_INVALID_HEADER,
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

typedef struct
{
    uint16_t service_id;
    uint8_t max_hops;
} cipher_payload_sd_t;
