// Standard includes
#include <stdio.h>
#include <string.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>
#include <zephyr/sys/byteorder.h>

// Private includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/cipher/serdes/decode.h>
#include <corekinect/cipher/serdes/encode.h>
#include <corekinect/cipher/serdes/print.h>
#include <corekinect/cipher/serdes/types.h>
#include <corekinect/iface/iface.h>

#include "utils/err.h"

LOG_MODULE_DECLARE(serdes);

/*
 * Wire byte order is BIG-ENDIAN (network order), matching the previous
 * htons()/htonl()/htonll() encoding this file used. The sys_*_be* helpers from
 * <zephyr/sys/byteorder.h> read/write byte-by-byte, so they are safe on targets
 * that fault on unaligned word access (Xtensa/ESP32, Cortex-M0) where the old
 * `*(uint16_t *)(buffer + pos)` casts at arbitrary offsets misbehaved. The
 * on-the-wire bytes are unchanged, so this remains interoperable with the
 * previous encoding.
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Encoders
 *---------------------------------------------------------------------------------------------------*/
inline bool serdes_put_uint8(uint8_t *buffer, uint16_t size, uint16_t *position, uint8_t value) {
    bool status = false;
    if (*position + 1 <= size) {
        buffer[(*position)++] = value;
        status = true;
    }
    return status;
}

inline bool serdes_put_uint16(uint8_t *buffer, uint16_t size, uint16_t *position, uint16_t value) {
    bool status = false;
    if (*position + 2 <= size) {
        sys_put_be16(value, &buffer[*position]);
        *position += 2;
        status = true;
    }
    return status;
}

inline bool serdes_put_uint32(uint8_t *buffer, uint16_t size, uint16_t *position, uint32_t value) {
    bool status = false;
    if (*position + 4 <= size) {
        sys_put_be32(value, &buffer[*position]);
        *position += 4;
        status = true;
    }
    return status;
}

inline bool serdes_put_uint64(uint8_t *buffer, uint16_t size, uint16_t *position, uint64_t value) {
    bool status = false;
    if (*position + 8 <= size) {
        sys_put_be64(value, &buffer[*position]);
        *position += 8;
        status = true;
    }
    return status;
}

inline bool serdes_put_float(uint8_t *buffer, uint16_t size, uint16_t *position, float value) {
    bool status = false;
    if (*position + 4 <= size) {
        uint32_t int_representation;
        memcpy(&int_representation, &value, sizeof(int_representation));
        sys_put_be32(int_representation, &buffer[*position]);
        *position += 4;
        status = true;
    }
    return status;
}

inline bool serdes_put_double(uint8_t *buffer, uint16_t size, uint16_t *position, double value) {
    bool status = false;
    if (*position + 8 <= size) {
        uint64_t int_representation;
        memcpy(&int_representation, &value, sizeof(int_representation));
        sys_put_be64(int_representation, &buffer[*position]);
        *position += 8;
        status = true;
    }
    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Decoders
 *---------------------------------------------------------------------------------------------------*/

inline uint8_t serdes_get_uint8(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    uint8_t result = 0;
    if (*position + 1 <= size) {
        result = *(buffer + *position);
        (*position)++;
    }
    return result;
}

inline uint16_t serdes_get_uint16(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    uint16_t result = 0;
    if (*position + 2 <= size) {
        result = sys_get_be16(buffer + *position);
        *position += 2;
    }
    return result;
}

inline uint32_t serdes_get_uint32(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    uint32_t result = 0;
    if (*position + 4 <= size) {
        result = sys_get_be32(buffer + *position);
        *position += 4;
    }
    return result;
}

inline uint64_t serdes_get_uint64(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    uint64_t result = 0;
    if (*position + 8 <= size) {
        result = sys_get_be64(buffer + *position);
        *position += 8;
    }
    return result;
}

inline float serdes_get_float(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    float result = 0;
    if (*position + 4 <= size) {
        // Retrieve the bits as a uint32_t and then reinterpret as float
        uint32_t intRepresentation = sys_get_be32(buffer + *position);
        memcpy(&result, &intRepresentation, sizeof(result));
        *position += 4;
    }
    return result;
}

inline double serdes_get_double(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    double result = 0;
    if (*position + 8 <= size) {
        // Retrieve the bits as a uint64_t and then reinterpret as double
        uint64_t intRepresentation = sys_get_be64(buffer + *position);
        memcpy(&result, &intRepresentation, sizeof(result));
        *position += 8;
    }
    return result;
}
