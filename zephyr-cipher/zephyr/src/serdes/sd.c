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

#include "serdes_prv.h"
#include "utils/err.h"

LOG_MODULE_DECLARE(serdes);

serdes_error_t encode_payload_sd_broadcast(serdes_encode_args_t *args);
serdes_error_t decode_payload_sd_broadcast(serdes_decode_args_t *args);

encode_func sd_lookup_encode_func(serdes_encode_args_t *args) {
    switch (args->header->flags) {
        case CIPHER_FLAG_SD_BROADCAST:
            return encode_payload_sd_broadcast;
            break;

        default:
            ERROR("Unknown flag type for SD packet");
            break;
    }
}

decode_func sd_lookup_decode_func(serdes_decode_args_t *args) {
    switch (args->header->flags) {
        case CIPHER_FLAG_SD_BROADCAST:
            return decode_payload_sd_broadcast;
            break;

        default:
            ERROR("Unknown flag type for SD packet");
            break;
    }
}

serdes_error_t encode_payload_sd_broadcast(serdes_encode_args_t *args) {
    cipher_payload_sd_broadcast_t *payload = (cipher_payload_sd_broadcast_t *)args->raw_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    // Encode alive flag
    uint8_t alive_flag = payload->alive ? 1 : 0;
    if (!serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, alive_flag)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    // Encode name
    for (int i = 0; i < CONFIG_CK_CIPHER_SERVICE_MAX_NAME_LEN; i++) {
        if (!serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, payload->name[i])) {
            return SERDES_ERROR_PUT_HELPER;
        }
    }

    // Encode service_id, device_id, num_ops, and allowed_hops
    if (!serdes_put_uint16(args->encoded_packet, args->encoded_packet_size, &position, payload->service_id) ||
        !serdes_put_uint16(args->encoded_packet, args->encoded_packet_size, &position, payload->device_id) ||
        !serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, payload->num_ops) ||
        !serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, payload->allowed_hops)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    return SERDES_ERROR_OK;
}

serdes_error_t decode_payload_sd_broadcast(serdes_decode_args_t *args) {
    cipher_payload_sd_broadcast_t *payload = (cipher_payload_sd_broadcast_t *)args->decoded_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    // Decode alive flag
    payload->alive = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position) == 1 ? true : false;

    // Decode name
    for (int i = 0; i < CONFIG_CK_CIPHER_SERVICE_MAX_NAME_LEN; i++) {
        payload->name[i] = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position);
    }

    // Decode service_id, device_id, num_ops, and allowed_hops
    payload->service_id = serdes_get_uint16(args->raw_packet, args->raw_packet_size, &position);
    payload->device_id = serdes_get_uint16(args->raw_packet, args->raw_packet_size, &position);
    payload->num_ops = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position);
    payload->allowed_hops = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position);

    return SERDES_ERROR_OK;
}
