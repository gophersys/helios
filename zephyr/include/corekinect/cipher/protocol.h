#ifndef CIPHER_PROTOCOL_H
#define CIPHER_PROTOCOL_H

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/
// Auto-generated code cannot have same names are cipher structs

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Protocol
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Cipher packet types
 */
typedef enum
{
    CIPHER_PACKET_TYPE_ADMIN,
    CIPHER_PACKET_TYPE_SD,
    CIPHER_PACKET_TYPE_RPC,
    CIPHER_PACKET_TYPE_EVENT,
    CIPHER_PACKET_TYPE_STREAM,

    CIPHER_PACKET_TYPE_MAX
} cipher_packet_type_t;

/**
 * @brief Cipher packet header
 */
typedef struct __attribute__((packed))
{
    // Up to 65536 devices on a single network
    uint16_t source_id;

    // Up to 65536 devices on a single network
    uint16_t destination_id;

    // Up to 16384 services
    uint32_t service_id : 14;

    // Up to 256 operations per service
    uint32_t operation_id : 8;

    // Header + Payload will never exceed 1024 bytes
    uint32_t payload_len : 10;

    // Up to ~8MB streams (8192 sequences * 1005 bytes payload)
    uint16_t sequence_num : 13;

    // Up to 8 types (RPC, event, pub/sub, admin, etc)
    uint16_t type : 3;

    // Protocol/admin level communication (unimplemented methods, etc)
    uint8_t flags;

    // Number of hops the packet has had
    uint8_t hop_count;
}
cipher_header_t;

/**
 * @brief Cipher packet. Payload is a place holder
 */
typedef struct
{
    cipher_header_t header;
    void *payload;
} cipher_packet_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Flags
 *---------------------------------------------------------------------------------------------------*/
typedef enum
{

    CIPHER_FLAG_RPC_REQUEST = (1 << 0),
    CIPHER_FLAG_RPC_RESPONSE = (1 << 1),
    CIPHER_FLAG_RPC_ERR = (1 << 2),

    CIPHER_FLAG_SD_BROADCAST = (1 << 3),
} cipher_flags_e;

// Macro to set a flag
#define CIPHER_SET_FLAG(FLAGS, FLAG) ((FLAGS) |= (FLAG))

// Macro to clear a flag
#define CIPHER_CLEAR_FLAG(FLAGS, FLAG) ((FLAGS) &= ~(FLAG))

// Macro to check if a flag is set
#define CIPHER_IS_FLAG_SET(FLAGS, FLAG) ((FLAGS) & (FLAG))

/*-----------------------------------------------------------------------------------------------------
 *                                                                           Service Discovery Payloads
 *---------------------------------------------------------------------------------------------------*/

typedef struct __attribute__((packed))
{
    bool alive;
    char name[CONFIG_CK_CIPHER_SERVICE_MAX_NAME_LEN];
    uint16_t service_id;
    uint16_t device_id;
    uint8_t num_ops;
    uint8_t allowed_hops;
}
cipher_payload_sd_broadcast_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         RPC Payloads
 *---------------------------------------------------------------------------------------------------*/

typedef struct
{
    uint8_t err;  // TODO: make the right type cipher_rpc_err_t
} cipher_payload_rpc_err_t;

#endif  // CIPHER_PROTOCOL_H