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

// Optional packet-analyzer hooks (no-ops when the analyzer is absent/disabled)
#ifdef CONFIG_CK_PKT_ANALYZER
#include <corekinect/analyzer/analyzer.h>
static inline void ana_emit(ck_ana_dir_t dir, const cipher_header_t *h)
{
    const ck_ana_cipher_meta_t meta = {
        .source_id = h->source_id,
        .destination_id = h->destination_id,
        .service_id = h->service_id,
        .operation_id = h->operation_id,
        .type = h->type,
        .payload_len = h->payload_len,
        .sequence_num = h->sequence_num,
        .flags = h->flags,
        .hop_count = h->hop_count,
    };
    CK_ANA_CIPHER_PKT(dir, &meta, NULL);
}
#else
#define ana_emit(dir, h) ((void)0)
#define CK_ANA_DIR_TX 0
#define CK_ANA_DIR_RX 1
#endif

LOG_MODULE_DECLARE(serdes);

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

    ana_emit(CK_ANA_DIR_TX, header);
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

    ana_emit(CK_ANA_DIR_RX, header);
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
