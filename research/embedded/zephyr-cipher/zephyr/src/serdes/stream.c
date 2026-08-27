// Standard includes
#include <stdio.h>
#include <string.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Private includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/cipher/serdes/types.h>

#include "serdes_prv.h"
#include "utils/err.h"

LOG_MODULE_DECLARE(serdes);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/
/**
 * Stream payloads are opaque bytes (a chunk of a larger transfer, or the
 * small START/END control payloads). Like RPC, the transport copies them raw
 * into/out of the wire buffer after the serdes-encoded header.
 */

static serdes_error_t stream_raw_encode(serdes_encode_args_t *args) {
    const uint16_t position = sizeof(cipher_header_t);
    if ((size_t)position + args->raw_payload_size > args->encoded_packet_size) {
        return SERDES_ERROR_BUFFER_TOO_SMALL;
    }
    memcpy(&args->encoded_packet[position], args->raw_payload, args->raw_payload_size);
    return SERDES_ERROR_OK;
}

static serdes_error_t stream_raw_decode(serdes_decode_args_t *args) {
    const uint16_t position = sizeof(cipher_header_t);
    if ((size_t)position + args->header->payload_len > args->raw_packet_size) {
        return SERDES_ERROR_BUFFER_TOO_SMALL;
    }
    if (args->header->payload_len > args->decoded_payload_size) {
        return SERDES_ERROR_BUFFER_TOO_SMALL;
    }
    memcpy(args->decoded_payload, &args->raw_packet[position], args->header->payload_len);
    return SERDES_ERROR_OK;
}

encode_func stream_lookup_encode_func(serdes_encode_args_t *args) {
    ARG_UNUSED(args);
    return stream_raw_encode;
}

decode_func stream_lookup_decode_func(serdes_decode_args_t *args) {
    ARG_UNUSED(args);
    return stream_raw_decode;
}
