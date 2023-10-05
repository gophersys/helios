// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Private includes
#include "protocol/protocol.h"
#include "protocol/serdes.h"
#include "transport/transport.h"
#include "utils/err.h"

// User includes

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_REGISTER(serdes, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Work Queues
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Header
 *---------------------------------------------------------------------------------------------------*/
serdes_error_t serdes_encode_header(uint8_t *buffer, uint16_t buffer_size, const cipher_header_t *header) {
    // Check for null pointers
    if (!buffer || !header) {
        return SERDES_ERROR_INVALID_PARAMETER;
    }

    // Size of the header
    const size_t header_size = sizeof(cipher_header_t);
    if (buffer_size < header_size) {
        return SERDES_ERROR_BUFFER_TOO_SMALL;
    }

    uint16_t position = 0;

    if (!serdes_put_uint16(buffer, buffer_size, &position, header->source_id)) {
        return SERDES_ERROR_ENCODING;
    }

    if (!serdes_put_uint16(buffer, buffer_size, &position, header->destination_id)) {
        return SERDES_ERROR_ENCODING;
    }
    uint32_t temp = (header->service_id & 0x3FFF) |
                    ((header->operation_id & 0xFF) << 14) |
                    ((header->payload_len & 0x3FF) << 22);

    if (!serdes_put_uint32(buffer, buffer_size, &position, temp)) {
        return SERDES_ERROR_ENCODING;
    }
    uint16_t temp2 = (header->sequence_num & 0x1FFF) |
                     ((header->type & 0x7) << 13);

    if (!serdes_put_uint16(buffer, buffer_size, &position, temp2)) {
        return SERDES_ERROR_ENCODING;
    }
    if (!serdes_put_uint8(buffer, buffer_size, &position, header->flags)) {
        return SERDES_ERROR_ENCODING;
    }
    if (!serdes_put_uint8(buffer, buffer_size, &position, header->hop_count)) {
        return SERDES_ERROR_ENCODING;
    }
    return SERDES_ERROR_OK;
}

serdes_error_t serdes_decode_header(const uint8_t *buffer, uint16_t buffer_size, cipher_header_t *header) {
    // Check for null pointers
    if (!buffer || !header) {
        return SERDES_ERROR_INVALID_PARAMETER;
    }

    // Size of the header
    const size_t header_size = sizeof(cipher_header_t);
    if (buffer_size < header_size) {
        return SERDES_ERROR_BUFFER_TOO_SMALL;
    }

    uint16_t position = 0;

    header->source_id = serdes_get_uint16(buffer, buffer_size, &position);
    header->destination_id = serdes_get_uint16(buffer, buffer_size, &position);

    uint32_t temp = serdes_get_uint32(buffer, buffer_size, &position);
    header->service_id = temp & 0x3FFF;
    header->operation_id = (temp >> 14) & 0xFF;
    header->payload_len = (temp >> 22) & 0x3FF;

    uint16_t temp2 = serdes_get_uint16(buffer, buffer_size, &position);
    header->sequence_num = temp2 & 0x1FFF;
    header->type = (temp2 >> 13) & 0x7;

    header->flags = serdes_get_uint8(buffer, buffer_size, &position);
    header->hop_count = serdes_get_uint8(buffer, buffer_size, &position);

    return SERDES_ERROR_OK;
}

serdes_error_t cipher_print_header(const cipher_header_t *header) {
    // TODO: Change this to LOG_RAW
    if (header == NULL)
        ERROR("NULL header passed");

    // Print each field
    LOG("Cipher Packet Header:");
    LOG("Source ID: %u", header->source_id);
    LOG("Destination ID: %u", header->destination_id);
    LOG("Service ID: %u", header->service_id);
    LOG("Operation ID: %u", header->operation_id);
    LOG("Payload Length: %u", header->payload_len);
    LOG("Sequence Num: %u", header->sequence_num);
    LOG("Type: %u", header->type);
    LOG("Flags: 0x%02x", header->flags);
    return SERDES_ERROR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Header
 *---------------------------------------------------------------------------------------------------*/
serdes_error_t serdes_encode_packet(serdes_encode_args_t args) {
    serdes_error_t status = SERDES_ERROR_OK;
    return status;
}
serdes_error_t serdes_decode_packet(serdes_decode_args_t args) {
    serdes_error_t status = SERDES_ERROR_OK;
    return status;
}

serdes_error_t cipher_print_packet(const cipher_header_t *header, const void *payload, const size_t payload_len) {
    serdes_error_t status = SERDES_ERROR_OK;
    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Encoders
 *---------------------------------------------------------------------------------------------------*/
bool serdes_put_uint8(uint8_t *buffer, uint16_t size, uint16_t *position, uint8_t value) {
    bool status = false;
    if (*position + 1 <= size) {
        buffer[(*position)++] = value;
        status = true;
    }
    return status;
}

bool serdes_put_uint16(uint8_t *buffer, uint16_t size, uint16_t *position, uint16_t value) {
    bool status = false;
    if (*position + 2 <= size) {
        *(uint16_t *)&buffer[*position] = htons(value);
        *position += 2;
        status = true;
    }
    return status;
}

bool serdes_put_uint32(uint8_t *buffer, uint16_t size, uint16_t *position, uint32_t value) {
    bool status = false;
    if (*position + 4 <= size) {
        *(uint32_t *)&buffer[*position] = htonl(value);
        *position += 4;
        status = true;
    }
    return status;
}

bool serdes_put_uint64(uint8_t *buffer, uint16_t size, uint16_t *position, uint64_t value) {
    bool status = false;
    if (*position + 8 <= size) {
        *(uint64_t *)&buffer[*position] = htonll(value);
        *position += 8;
        status = true;
    }
    return status;
}

bool serdes_put_float(uint8_t *buffer, uint16_t size, uint16_t *position, float value) {
    bool status = false;
    if (*position + 4 <= size) {
        uint32_t int_representation = htonl(*(uint32_t *)&value);
        *(uint32_t *)&buffer[*position] = int_representation;
        *position += 4;
        status = true;
    }
    return status;
}

bool serdes_put_double(uint8_t *buffer, uint16_t size, uint16_t *position, double value) {
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

uint8_t serdes_get_uint8(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    uint8_t result = 0;
    if (*position + 1 <= size) {
        result = *(buffer + *position);
        (*position)++;
    }
    return result;
}

uint16_t serdes_get_uint16(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    uint16_t result = 0;
    if (*position + 2 <= size) {
        result = ntohs(*(uint16_t *)(buffer + *position));
        *position += 2;
    }
    return result;
}

uint32_t serdes_get_uint32(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    uint32_t result = 0;
    if (*position + 4 <= size) {
        result = ntohl(*(uint32_t *)(buffer + *position));
        *position += 4;
    }
    return result;
}

uint64_t serdes_get_uint64(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    uint64_t result = 0;
    if (*position + 8 <= size) {
        // Similar to htonll in the put functions, you would use ntohll here, if you had such a function.
        result = ntohll(*(uint64_t *)(buffer + *position));
        *position += 8;
    }
    return result;
}

float serdes_get_float(const uint8_t *buffer, uint16_t size, uint16_t *position) {
    float result = 0;
    if (*position + 4 <= size) {
        // We'll retrieve the bits as a uint32_t and then cast to float
        uint32_t intRepresentation = ntohl(*(uint32_t *)(buffer + *position));
        result = *(float *)&intRepresentation;
        *position += 4;
    }
    return result;
}

double serdes_get_double(const uint8_t *buffer, uint16_t size, uint16_t *position) {
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
