#ifndef SERDES_DECODE_H
#define SERDES_DECODE_H

// Standard includes
#include <stddef.h>

// CoreKinect includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/cipher/serdes/types.h>

#include "daemon/daemon.h"  //TODO: Remove me

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
 * @brief Unpacks network byte order protocol packet (header + payload) into buffer in host byte order
 *
 * @param args Decoding arguements
 * @return serdes_error_t SERDES_ERROR_OK if no errors
 */
serdes_error_t serdes_decode_packet(cipher_daemon_t *d, serdes_decode_args_t *args);

uint8_t serdes_get_uint8(const uint8_t *buffer, uint16_t size, uint16_t *position);
uint16_t serdes_get_uint16(const uint8_t *buffer, uint16_t size, uint16_t *position);
uint32_t serdes_get_uint32(const uint8_t *buffer, uint16_t size, uint16_t *position);
uint64_t serdes_get_uint64(const uint8_t *buffer, uint16_t size, uint16_t *position);
float serdes_get_float(const uint8_t *buffer, uint16_t size, uint16_t *position);
double serdes_get_double(const uint8_t *buffer, uint16_t size, uint16_t *position);

#endif  // SERDES_DECODE_H