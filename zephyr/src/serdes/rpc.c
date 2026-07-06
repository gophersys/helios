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

#include "daemon/registry.h"
#include "serdes_prv.h"
#include "utils/err.h"

LOG_MODULE_DECLARE(serdes);

encode_func rpc_lookup_encode_func(cipher_daemon_t *d, serdes_encode_args_t *args) {
    cipher_ops_entry_t *op = find_op_in_registry(d, args->header);
    if (!op) {
        return NULL;
    }

    cipher_ops_rpc_t *rpc = &op->op.rpc;

    if (CIPHER_IS_FLAG_SET(args->header->flags, CIPHER_FLAG_RPC_REQUEST)) {
        return rpc->request_serdes.encode;
    } else if (CIPHER_IS_FLAG_SET(args->header->flags, CIPHER_FLAG_RPC_RESPONSE)) {
        return rpc->response_serdes.encode;
    } else {
        ERROR("RPC Packet uknown flags: 0x%02x", args->header->flags);
    }

    return NULL;
}

decode_func rpc_lookup_decode_func(cipher_daemon_t *d, serdes_decode_args_t *args) {
    cipher_ops_entry_t *op = find_op_in_registry(d, args->header);
    if (!op) {
        return NULL;
    }

    cipher_ops_rpc_t *rpc = &op->op.rpc;

    if (CIPHER_IS_FLAG_SET(args->header->flags, CIPHER_FLAG_RPC_REQUEST)) {
        return rpc->request_serdes.decode;
    } else if (CIPHER_IS_FLAG_SET(args->header->flags, CIPHER_FLAG_RPC_RESPONSE)) {
        return rpc->response_serdes.decode;
    } else {
        ERROR("RPC Packet uknown flags: 0x%02x", args->header->flags);
    }

    return NULL;
}