// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Private includes
#include "daemon/registry.h"
#include "protocol/protocol.h"
#include "protocol/serdes.h"
#include "serdes_prv.h"
#include "transport/transport.h"
#include "utils/err.h"

LOG_MODULE_DECLARE(serdes);

encode_func rpc_lookup_encode_func(cipher_daemon_t *d, serdes_encode_args_t *args) {
    cipher_ops_entry_t *op = find_op_in_registry(d, args->header);
    if (!op) {
        return NULL;
    }

    cipher_ops_rpc_t *rpc = &op->op.rpc;

    switch (args->header->flags) {
        case CIPHER_FLAG_RPC_REQUEST:
            return rpc->request_serdes.encode;
        case CIPHER_FLAG_RPC_RESPONSE:
            return rpc->response_serdes.encode;
        default:
            ERROR("not good");
    }

    return NULL;
}

decode_func rpc_lookup_decode_func(cipher_daemon_t *d, serdes_decode_args_t *args) {
    cipher_ops_entry_t *op = find_op_in_registry(d, args->header);
    if (!op) {
        return NULL;
    }

    cipher_ops_rpc_t *rpc = &op->op.rpc;

    switch (args->header->flags) {
        case CIPHER_FLAG_RPC_REQUEST:
            return rpc->request_serdes.decode;
        case CIPHER_FLAG_RPC_RESPONSE:
            return rpc->response_serdes.decode;
        default:
            ERROR("not good");
    }

    return NULL;
}