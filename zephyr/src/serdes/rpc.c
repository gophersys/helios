// Standard includes
#include <stdio.h>
#include <string.h>

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

#include "daemon/registry.h"
#include "serdes_prv.h"
#include "utils/err.h"

LOG_MODULE_DECLARE(serdes);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/
/**
 * RPC request/response payloads are OPAQUE application bytes. The rest of the
 * RPC path treats them as raw (local.c and worker.c memcpy the payload in and
 * out of the packet), so the transport serdes here is a straight copy of the
 * payload into/out of the wire buffer after the serdes-encoded header.
 *
 * Doing it this way (rather than per-op request_serdes/response_serdes lookups
 * via find_op_in_registry) is what lets a CLIENT encode a request for a REMOTE
 * service it does not have registered locally — the op only lives on the
 * server. Both the STM32 target and the x86/Go peers are little-endian, so a
 * packed application struct is wire-compatible without per-field swapping. If a
 * future op needs endian-neutral or variable-length payloads, it can define its
 * own request/response serdes and this default can dispatch to it.
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       Raw Payload IO
 *---------------------------------------------------------------------------------------------------*/
static serdes_error_t rpc_raw_encode(serdes_encode_args_t *args) {
    const uint16_t position = sizeof(cipher_header_t);

    if ((size_t)position + args->raw_payload_size > args->encoded_packet_size) {
        return SERDES_ERROR_BUFFER_TOO_SMALL;
    }

    memcpy(&args->encoded_packet[position], args->raw_payload, args->raw_payload_size);
    return SERDES_ERROR_OK;
}

static serdes_error_t rpc_raw_decode(serdes_decode_args_t *args) {
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

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Lookup
 *---------------------------------------------------------------------------------------------------*/
encode_func rpc_lookup_encode_func(cipher_daemon_t *d, serdes_encode_args_t *args) {
    ARG_UNUSED(d);

    if (!CIPHER_IS_FLAG_SET(args->header->flags, CIPHER_FLAG_RPC_REQUEST) &&
        !CIPHER_IS_FLAG_SET(args->header->flags, CIPHER_FLAG_RPC_RESPONSE) &&
        !CIPHER_IS_FLAG_SET(args->header->flags, CIPHER_FLAG_RPC_ERR)) {
        ERROR("RPC packet unknown flags: 0x%02x", args->header->flags);
        return NULL;
    }

    return rpc_raw_encode;
}

decode_func rpc_lookup_decode_func(cipher_daemon_t *d, serdes_decode_args_t *args) {
    ARG_UNUSED(d);

    if (!CIPHER_IS_FLAG_SET(args->header->flags, CIPHER_FLAG_RPC_REQUEST) &&
        !CIPHER_IS_FLAG_SET(args->header->flags, CIPHER_FLAG_RPC_RESPONSE) &&
        !CIPHER_IS_FLAG_SET(args->header->flags, CIPHER_FLAG_RPC_ERR)) {
        ERROR("RPC packet unknown flags: 0x%02x", args->header->flags);
        return NULL;
    }

    return rpc_raw_decode;
}
