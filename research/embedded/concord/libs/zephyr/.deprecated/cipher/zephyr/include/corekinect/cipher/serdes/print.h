#ifndef SERDES_PRINT_H
#define SERDES_PRINT_H

// Standard includes
#include <stddef.h>

// CoreKinect includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/cipher/serdes/types.h>

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

#endif  // SERDES_PRINT_H