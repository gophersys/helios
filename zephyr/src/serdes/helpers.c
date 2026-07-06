// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Private includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/cipher/serdes/decode.h>
#include <corekinect/cipher/serdes/encode.h>
#include <corekinect/cipher/serdes/print.h>
#include <corekinect/cipher/serdes/types.h>
#include <corekinect/iface/iface.h>

#include "utils/err.h"

LOG_MODULE_DECLARE(serdes);

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
        *(uint16_t *)&buffer[*position] = htons(value);
        *position += 2;
        status = true;
    }
    return status;
}

inline bool serdes_put_uint32(uint8_t *buffer, uint16_t size, uint16_t *position, uint32_t value) {
    bool status = false;
    if (*position + 4 <= size) {
        *(uint32_t *)&buffer[*position] = htonl(value);
        *position += 4;
        status = true;
    }
    return status;
}

inline bool serdes_put_uint64(uint8_t *buffer, uint16_t size, uint16_t *position, uint64_t value) {
    bool status = false;
    if (*position + 8 <= size) {
        *(uint64_t *)&buffer[*position] = htonll(value);
        *position += 8;
        status = true;
    }
    return status;
}

inline bool serdes_put_float(uint8_t *buffer, uint16_t size, uint16_t *position, float value) {
    bool status = false;
    if (*position + 4 <= size) {
        uint32_t int_representation = htonl(*(uint32_t *)&value);
        *(uint32_t *)&buffer[*position] = int_representation;
        *position += 4;
        status = true;
    }
    return status;
}

inline bool serdes_put_double(uint8_t *buffer, uint16_t size, uint16_t *position, double value) {
    bool status = false;
    if (*position + 8 <= size) {
        uint64_t int_representation = htonll(*(uint64_t *)&value);
        *(uint64_t *)&buffer[*position] = int_representation;
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
        result = ntohs(*(uint16_t *)(buffer + *position));
        *position += 2;
    }
    return result;
}

inline uint32_t serdes_get_uint32(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    uint32_t result = 0;
    if (*position + 4 <= size) {
        result = ntohl(*(uint32_t *)(buffer + *position));
        *position += 4;
    }
    return result;
}

inline uint64_t serdes_get_uint64(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    uint64_t result = 0;
    if (*position + 8 <= size) {
        // Similar to htonll in the put functions, you would use ntohll here, if you had such a function.
        result = ntohll(*(uint64_t *)(buffer + *position));
        *position += 8;
    }
    return result;
}

inline float serdes_get_float(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    float result = 0;
    if (*position + 4 <= size) {
        // We'll retrieve the bits as a uint32_t and then cast to float
        uint32_t intRepresentation = ntohl(*(uint32_t *)(buffer + *position));
        result = *(float *)&intRepresentation;
        *position += 4;
    }
    return result;
}

inline double serdes_get_double(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    double result = 0;
    if (*position + 8 <= size) {
        // Similar to float, we'll retrieve the bits as a uint64_t and then cast to double.
        // Again, you'd need a function similar to ntohll for this.
        uint64_t intRepresentation = ntohll(*(uint64_t *)(buffer + *position));
        result = *(double *)&intRepresentation;
        *position += 8;
    }
    return result;
}
