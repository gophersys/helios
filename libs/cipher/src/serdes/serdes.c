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
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
serdes_error_t serdes_encode_header(uint8_t *buffer, uint16_t buffer_size, const cipher_header_t *header) {
    serdes_error_t status = SERDES_ERROR_OK;
    return status;
}

serdes_error_t serdes_decode_header(const uint8_t *buffer, uint16_t buffer_size, cipher_header_t *header) {
    __ASSERT(buffer, "header_buffer is NULL");

    // Size of the header, taking care to include all fields
    const size_t header_size = sizeof(cipher_header_t);
    if (buffer_size < header_size) {
        WARN("Packet must be at least %d bytes, got %d", sizeof(cipher_header_t), buffer_size);
    } else {
        header->source_id = ntohs(*(uint16_t *)buffer);
        buffer += sizeof(uint16_t);

        header->destination_id = ntohs(*(uint16_t *)buffer);
        buffer += sizeof(uint16_t);

        uint32_t temp = ntohl(*(uint32_t *)buffer);
        header->service_id = temp & 0x3FFF;
        header->operation_id = (temp >> 14) & 0xFF;
        header->payload_len = (temp >> 22) & 0x3FF;
        buffer += sizeof(uint32_t);

        uint16_t temp2 = ntohs(*(uint16_t *)buffer);
        header->sequence_num = temp2 & 0x1FFF;
        header->type = (temp2 >> 13) & 0x7;
        buffer += sizeof(uint16_t);

        header->flags = *buffer;
    }

    return SERDES_ERROR_OK;
}

serdes_error_t serdes_encode_packet(serdes_encode_args_t args) {
    serdes_error_t status = SERDES_ERROR_OK;
    return status;
}
serdes_error_t serdes_decode_packet(serdes_decode_args_t args) {
    serdes_error_t status = SERDES_ERROR_OK;
    return status;
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

serdes_error_t cipher_print_packet(const cipher_header_t *header, const void *payload, const size_t payload_len) {
    serdes_error_t status = SERDES_ERROR_OK;
    return status;
}
