#ifndef SERDES_H
#define SERDES_H

// Private includes
#include "protocol/protocol.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Types
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Errors returned by the serdes module
 */
typedef enum {
    SERDES_ERROR_OK,
    SERDES_ERROR_INVALID_PARAMETER,
    SERDES_ERROR_BUFFER_TOO_SMALL,
    SERDES_ERROR_ENCODING,

    SERDES_ERROR_MAX
} serdes_error_t;

/**
 * @brief Network byte order to Host byte order arguements
 */
typedef struct {
    cipher_header_t *header;
    uint8_t *raw_payload;
    size_t raw_payload_size;
    void *decoded_payload;
} serdes_decode_args_t;

/**
 * @brief Host byte order to Network byte order arguements
 */
typedef struct {
    cipher_header_t *header;
    void *raw_payload;
    size_t raw_payload_size;
    uint8_t *encoded_payload;
} serdes_encode_args_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/
/**
 * @brief Packs host byte order protocol header into buffer in network byte order
 *
 * @param buffer Where the encoded header will be stored
 * @param buffer_size The size of the encoded header buffer
 * @param header The header to encode
 * @return serdes_error_t SERDES_ERROR_OK if no errors
 */
serdes_error_t serdes_encode_header(uint8_t *buffer, uint16_t buffer_size, const cipher_header_t *header);

/**
 * @brief Unpacks network byte order protocol header into buffer in host byte order
 *
 * @param buffer Where the encoded header is
 * @param buffer_size The size of the encoded header buffer
 * @param header Buffer to store decoded header
 * @return serdes_error_t SERDES_ERROR_OK if no errors
 */
serdes_error_t serdes_decode_header(const uint8_t *buffer, uint16_t buffer_size, cipher_header_t *header);

/**
 * @brief Packs host byte order protocol packet (header + payload) into buffer in network byte order
 *
 * @param args Encoding arguements
 * @return serdes_error_t SERDES_ERROR_OK if no errors
 */
serdes_error_t serdes_encode_packet(serdes_encode_args_t args);

/**
 * @brief Unpacks network byte order protocol packet (header + payload) into buffer in host byte order
 *
 * @param args Decoding arguements
 * @return serdes_error_t SERDES_ERROR_OK if no errors
 */
serdes_error_t serdes_decode_packet(serdes_decode_args_t args);

/**
 * @brief Prints a readable header using LOG_RAW
 *
 * @param header The header to print
 * @return serdes_error_t SERDES_ERROR_OK if no errors
 */
serdes_error_t cipher_print_header(const cipher_header_t *header);

/**
 * @brief Prints a readable packet using LOG_RAW
 *
 * @param header The header to print
 * @return serdes_error_t SERDES_ERROR_OK if no errors
 */
serdes_error_t cipher_print_packet(const cipher_header_t *header, const void *payload, const size_t payload_len);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Encoding
 *---------------------------------------------------------------------------------------------------*/
bool serdes_put_uint8(uint8_t *buffer, uint16_t size, uint16_t *position, uint8_t value);
bool serdes_put_uint16(uint8_t *buffer, uint16_t size, uint16_t *position, uint16_t value);
bool serdes_put_uint32(uint8_t *buffer, uint16_t size, uint16_t *position, uint32_t value);
bool serdes_put_uint64(uint8_t *buffer, uint16_t size, uint16_t *position, uint64_t value);
bool serdes_put_float(uint8_t *buffer, uint16_t size, uint16_t *position, float value);
bool serdes_put_double(uint8_t *buffer, uint16_t size, uint16_t *position, double value);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Decoding
 *---------------------------------------------------------------------------------------------------*/
uint8_t serdes_get_uint8(const uint8_t *buffer, uint16_t size, uint16_t *position);
uint16_t serdes_get_uint16(const uint8_t *buffer, uint16_t size, uint16_t *position);
uint32_t serdes_get_uint32(const uint8_t *buffer, uint16_t size, uint16_t *position);
uint64_t serdes_get_uint64(const uint8_t *buffer, uint16_t size, uint16_t *position);
float serdes_get_float(const uint8_t *buffer, uint16_t size, uint16_t *position);
double serdes_get_double(const uint8_t *buffer, uint16_t size, uint16_t *position);

#endif  // SERDES_H