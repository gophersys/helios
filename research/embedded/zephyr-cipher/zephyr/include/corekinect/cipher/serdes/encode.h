#ifndef SERDES_ENCODE_H
#define SERDES_ENCODE_H

// Standard includes
#include <stddef.h>

// CoreKinect includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/cipher/serdes/types.h>

#include "daemon/daemon.h"  //TODO: Remove me

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
 * @brief Packs host byte order protocol packet (header + payload) into buffer in network byte order
 *
 * @param args Encoding arguements
 * @return serdes_error_t SERDES_ERROR_OK if no errors
 */
serdes_error_t serdes_encode_packet(cipher_daemon_t *d, serdes_encode_args_t *args);

bool serdes_put_uint8(uint8_t *buffer, uint16_t size, uint16_t *position, uint8_t value);
bool serdes_put_uint16(uint8_t *buffer, uint16_t size, uint16_t *position, uint16_t value);
bool serdes_put_uint32(uint8_t *buffer, uint16_t size, uint16_t *position, uint32_t value);
bool serdes_put_uint64(uint8_t *buffer, uint16_t size, uint16_t *position, uint64_t value);
bool serdes_put_float(uint8_t *buffer, uint16_t size, uint16_t *position, float value);
bool serdes_put_double(uint8_t *buffer, uint16_t size, uint16_t *position, double value);

#endif  // SERDES_DECODE_H