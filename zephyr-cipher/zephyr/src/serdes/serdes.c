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

LOG_MODULE_REGISTER(serdes, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
static void assert_serdes_args(serdes_encode_args_t *encode_args, serdes_decode_args_t *decode_args);
static void assert_serdes_arrays(void);

// Lookup helpers
static encode_func lookup_encode_func(cipher_daemon_t *d, serdes_encode_args_t *args);
static decode_func lookup_decode_func(cipher_daemon_t *d, serdes_decode_args_t *args);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/
serdes_error_t serdes_encode_packet(cipher_daemon_t *d, serdes_encode_args_t *args) {
    assert_serdes_args(args, NULL);
    assert_serdes_arrays();

    // Cipher packets can have just a header on them
    if (args->raw_payload_size > 0) {
        encode_func encode_payload_func = lookup_encode_func(d, args);

        if (!encode_payload_func) {
            return SERDES_ERROR_NOT_FOUND;
        }

        serdes_error_t err = encode_payload_func(args);
        if (err != SERDES_ERROR_OK) {
            return err;
        }
    }

    return serdes_encode_header(args->encoded_packet, args->encoded_packet_size, args->header);
}

serdes_error_t serdes_decode_packet(cipher_daemon_t *d, serdes_decode_args_t *args) {
    assert_serdes_args(NULL, args);
    assert_serdes_arrays();

    serdes_error_t err = serdes_decode_header(args->raw_packet, args->raw_packet_size, args->header);
    if (err != SERDES_ERROR_OK) {
        return err;
    }

    /* SECURITY: payload_len is a 10-bit field supplied by the remote peer over
     * TCP. It must not exceed the framed payload actually received (the decoded
     * buffer size). Without this a peer sets payload_len larger than the frame
     * and every downstream memcpy(dst, payload, payload_len) over-reads the heap
     * buffer / desyncs framing. Reject the packet here, at the trust boundary. */
    if (args->header->payload_len > args->decoded_payload_size) {
        return SERDES_ERROR_INVALID_PAYLOAD_SIZE;
    }

    if (args->header->payload_len == 0) {
        return SERDES_ERROR_OK;
    }

    decode_func decode_payload_func = lookup_decode_func(d, args);

    if (!decode_payload_func) {
        return SERDES_ERROR_NOT_FOUND;
    }

    return decode_payload_func(args);
}

serdes_error_t cipher_print_packet(const cipher_header_t *header, const void *payload, const size_t payload_len) {
    serdes_error_t status = SERDES_ERROR_OK;
    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Look Ups
 *---------------------------------------------------------------------------------------------------*/
static encode_func lookup_encode_func(cipher_daemon_t *d, serdes_encode_args_t *args) {

    switch (args->header->type) {
        case CIPHER_PACKET_TYPE_ADMIN:

            break;
        case CIPHER_PACKET_TYPE_SD:
            return sd_lookup_encode_func(args);
        case CIPHER_PACKET_TYPE_RPC:
            return rpc_lookup_encode_func(d, args);
            break;
        case CIPHER_PACKET_TYPE_EVENT:

            break;
        case CIPHER_PACKET_TYPE_STREAM:
            return stream_lookup_encode_func(args);

        default:
            break;
    }

    return NULL;
}

static decode_func lookup_decode_func(cipher_daemon_t *d, serdes_decode_args_t *args) {
    switch (args->header->type) {
        case CIPHER_PACKET_TYPE_ADMIN:

            break;
        case CIPHER_PACKET_TYPE_SD:
            return sd_lookup_decode_func(args);
        case CIPHER_PACKET_TYPE_RPC:
            return rpc_lookup_decode_func(d, args);
            break;
        case CIPHER_PACKET_TYPE_EVENT:

            break;
        case CIPHER_PACKET_TYPE_STREAM:
            return stream_lookup_decode_func(args);

        default:
            break;
    }

    return NULL;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Asserts
 *---------------------------------------------------------------------------------------------------*/

static void assert_serdes_args(serdes_encode_args_t *encode_args, serdes_decode_args_t *decode_args) {

    assert_serdes_arrays();

    // Common phrase to attach to each check
    char *args_msg = NULL;

    if (encode_args != NULL) {
        args_msg = "Are you populating serdes_encode_args_t correctly?";
    }

    if (decode_args != NULL) {
        args_msg = "Are you populating serdes_decode_args_t correctly?";
    }

    // __ASSERT(encode_args->header, "Null header, %s", args_msg);
    // __ASSERT(encode_args->encoded_packet, "Null raw_packet, %s", args_msg);
    // __ASSERT(encode_args->encoded_packet, "Null encoded_packet, %s", args_msg);

    // TODO: Assert header
}

static void assert_serdes_arrays(void) {
}