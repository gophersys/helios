// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Private includes
#include "transport/transport.h"
#include "protocol/protocol.h"
#include "protocol/serdes.h"
#include "utils/err.h"

// Private includes

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
cipher_error_t cipher_encode_packet(cipher_encode_args_t args)
{
    cipher_error_t status = CIPHER_ERROR_OK;
    return status;
}
cipher_error_t cipher_decode_packet(cipher_decode_args_t args)
{
    cipher_error_t status = CIPHER_ERROR_OK;
    if (!cipher_packet_parse_header(args.raw_payload, args.raw_payload_size, args.header))
    {
        status = CIPHER_ERROR_INVALID_HEADER;
    }
    else
    {
        const uint8_t *payload_buffer = args.raw_payload + sizeof(cipher_header_t);

        cipher_payload_sd_t *decoded_payload = (cipher_payload_sd_t *)args.decoded_payload;
        decoded_payload->service_id = *payload_buffer;
        payload_buffer += sizeof(uint8_t);
        // decoded_payload->num_hops = ntohs(*(uint16_t *)payload_buffer);
        payload_buffer += sizeof(uint16_t);
    }

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/

void cipher_print_header(const cipher_header_t *header)
{
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
}

bool cipher_packet_parse_header(const uint8_t *recv_buffer, uint16_t recv_buffer_size, cipher_header_t *header_buffer)
{
    __ASSERT(recv_buffer != NULL, "recv_buffer is NULL");
    __ASSERT(header_buffer != NULL, "header_buffer is NULL");

    bool status = false;

    // Size of the header, taking care to include all fields
    const size_t header_size = sizeof(cipher_header_t);
    if (recv_buffer_size < header_size)
    {
        WARN("Packet must be at least %d bytes, got %d", sizeof(cipher_header_t), recv_buffer_size);
    }
    else
    {
        header_buffer->source_id = ntohs(*(uint16_t *)recv_buffer);
        recv_buffer += sizeof(uint16_t);

        header_buffer->destination_id = ntohs(*(uint16_t *)recv_buffer);
        recv_buffer += sizeof(uint16_t);

        uint32_t temp = ntohl(*(uint32_t *)recv_buffer);
        header_buffer->service_id = temp & 0x3FFF;
        header_buffer->operation_id = (temp >> 14) & 0xFF;
        header_buffer->payload_len = (temp >> 22) & 0x3FF;
        recv_buffer += sizeof(uint32_t);

        uint16_t temp2 = ntohs(*(uint16_t *)recv_buffer);
        header_buffer->sequence_num = temp2 & 0x1FFF;
        header_buffer->type = (temp2 >> 13) & 0x7;
        recv_buffer += sizeof(uint16_t);

        header_buffer->flags = *recv_buffer;

        status = true;
    }

    return status;
}
