#ifndef SERDES_H
#define SERDES_H

// Private includes
#include "protocol.h"

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

cipher_error_t cipher_print_header(const cipher_header_t *header);
cipher_error_t cipher_decode_header(const uint8_t *recv_buffer, uint16_t recv_buffer_size, cipher_header_t *header_buffer);
cipher_error_t cipher_encode_packet(cipher_encode_args_t args);
cipher_error_t cipher_decode_packet(cipher_decode_args_t args);

typedef struct
{
    uint16_t service_id;
    uint8_t max_hops;
} cipher_payload_sd_t;

#endif // SERDES_H