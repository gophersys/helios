#ifndef IFACE_STACK_PROTOCOL_H
#define IFACE_STACK_PROTOCOL_H

// Standard includes
#include <stdint.h>

/**
 * @def IFACE_PACKET_START_DELIMITER
 * @brief Unique sequence of bytes used as protocol's start delimiter
 */
#define IFACE_PACKET_START_DELIMITER 0xABCDEF01

/**
 * @enum iface_packet_type_t
 * @brief Enumerates the types of packet available for protocol.
 */
typedef enum
{
    IFACE_PACKET_TYPE_CONN_REQ,
    IFACE_PACKET_TYPE_CONN_ACK,
    IFACE_PACKET_TYPE_DATA,
    IFACE_PACKET_TYPE_DATA_ACK,
    IFACE_PACKET_TYPE_DATA_REQ,
    IFACE_PACKET_TYPE_CLOSE_REQ,
    IFACE_PACKET_TYPE_CLOSE_ACK
} iface_packet_type_t;

/**
 * @struct iface_packet_header_t
 * @brief Structure holding an iface packet header members.
 */
typedef struct
{
    uint32_t crc32;       /**< The crc32 of the (type + sequence_num + length + data). */
    uint8_t type;         /**< @ref iface_packet_type_t. */
    uint8_t sequence_num; /**< Used to keep track of packets sequence and acknowledgements. */
    uint16_t length;      /**< The length of the paylaod in this packet. */
} iface_packet_header_t;

/**
 * @struct iface_packet_t
 * @brief Structure holding an iface packet members.
 */
typedef struct
{
    uint32_t start_delimiter;     /**< @ref IFACE_PACKET_START_DELIMITER */
    iface_packet_header_t header; /**< The packet header */
    uint8_t *p_data;              /**< Pointer to user data, meant to be allocated from a heap */
} iface_packet_t;

#endif  // IFACE_STACK_PROTOCOL_H