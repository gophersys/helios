#ifndef SERDES_TYPES_H
#define SERDES_TYPES_H

// Private includes
#include <corekinect/cipher/protocol.h>

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Types
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Errors returned by the serdes module
 */
typedef enum {
    SERDES_ERROR_OK,
    SERDES_ERROR_INVALID_PARAMETER,
    SERDES_ERROR_INVALID_PAYLOAD_SIZE,
    SERDES_ERROR_NOT_FOUND,
    SERDES_ERROR_PUT_HELPER,
    SERDES_ERROR_BUFFER_TOO_SMALL,
    SERDES_ERROR_ENCODING,

    SERDES_ERROR_MAX
} serdes_error_t;

/**
 * @brief Network byte order to Host byte order arguements
 */
typedef struct {
    cipher_header_t *header;      // The buffer to put the decoded header in
    uint8_t *raw_packet;          // The raw network buffer received
    size_t raw_packet_size;       // The size of the network buffer
    void *decoded_payload;        // A buffer to store the decoded payload
    size_t decoded_payload_size;  // A buffer to store the decoded payload
} serdes_decode_args_t;

/**
 * @brief Host byte order to Network byte order arguements
 */
typedef struct {
    cipher_header_t *header;     // The header with the info needed to encode the raw payload
    void *raw_payload;           // The payload to encode
    size_t raw_payload_size;     // The size of the payload to encode
    uint8_t *encoded_packet;     // The raw network buffer to store the raw payload in
    size_t encoded_packet_size;  // The size of the payload to encode
} serdes_encode_args_t;

typedef struct {
    serdes_error_t (*encode)(serdes_encode_args_t *args);
    serdes_error_t (*decode)(serdes_decode_args_t *args);
} serdes_interface_t;

#endif  // SERDES_TYPES_H