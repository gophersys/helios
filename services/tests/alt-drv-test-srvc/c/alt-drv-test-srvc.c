#include "alt-drv-test-srvc.h"

// Zephyr includes
#include <zephyr/random/rand32.h>

// Cipher includes
#include "daemon/api.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "protocol/serdes.h"
#include "utils/err.h"

LOG_MODULE_REGISTER(alt_drv_test, LOG_LEVEL_DBG);
#define SERVICE_ID 101

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Private Types
 *---------------------------------------------------------------------------------------------------*/
typedef enum {
    OP_ID_RPC_BEGIN_TEST,
} alt_drv_test_service_op_id_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                   Local RPC Handlers
 *---------------------------------------------------------------------------------------------------*/

static bool alt_drv_test_rpc_begin_test_handler_implemented = true;
__attribute__((weak)) test_response_t alt_drv_test_rpc_begin_test_handler(test_request_t request) {
    WARN("no implementation for %s provided", __func__);
    alt_drv_test_rpc_begin_test_handler_implemented = false;
    test_response_t resp = {0};
    return resp;
}

cipher_rpc_err_t alt_drv_test_rpc_begin_test_handler_prv_handler(void *request, void *response) {

    test_request_t *typed_request = (test_request_t *)request;
    test_response_t *typed_response = (test_response_t *)response;

    *typed_response = alt_drv_test_rpc_begin_test_handler(*typed_request);

    if (!alt_drv_test_rpc_begin_test_handler_implemented) {
        return CIPHER_RPC_ERR_NOT_IMPLEMENTED;
    }

    return CIPHER_RPC_ERR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                   Remote RPC Request Implementations
 *---------------------------------------------------------------------------------------------------*/
test_response_t alt_drv_test_rpc_begin_test(cipher_daemon_t *d, cipher_rpc_user_info_t *info, test_request_t request) {

    test_response_t response = {0};

    cipher_rpc_entry_t rpc_entry = {
        .service_id = SERVICE_ID,
        .op_id = OP_ID_RPC_BEGIN_TEST,
        .request = &request,
        .request_size = sizeof(request),
        .response = &response,
        .response_size = sizeof(response),
        .user_info = info,
    };
    sys_rand_get(&rpc_entry.id, sizeof(rpc_entry.id));

    cipher_remote_rpc_handler(d, &rpc_entry);

    return response;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Serdes
 *---------------------------------------------------------------------------------------------------*/
serdes_error_t test_request_t_encode(serdes_encode_args_t *args) {
    return SERDES_ERROR_OK;
}

serdes_error_t test_request_t_decode(serdes_decode_args_t *args) {
    return SERDES_ERROR_OK;
}

serdes_error_t test_response_t_encode(serdes_encode_args_t *args) {
    test_response_t *payload = (test_response_t *)args->raw_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    if (!serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, (uint8_t)payload->err)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    if (!serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, (uint8_t)payload->success)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    return SERDES_ERROR_OK;
}

serdes_error_t test_response_t_decode(serdes_decode_args_t *args) {
    test_response_t *payload = (test_response_t *)args->decoded_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    payload->err = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position);
    payload->success = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position);

    return SERDES_ERROR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  Ops
 *---------------------------------------------------------------------------------------------------*/

static cipher_ops_entry_t alt_drv_test_service_ops[] = {
    {
        .id = OP_ID_RPC_BEGIN_TEST,
        .type = CIPHER_OPS_TYPE_RPC,
        .name = "BeginTest",
        .op = {
            .rpc = {
                .request_serdes = {
                    .encode = test_request_t_encode,
                    .decode = test_request_t_decode,
                },
                .request_size = sizeof(test_request_t),
                .response_serdes = {
                    .encode = test_response_t_encode,
                    .decode = test_response_t_decode,
                },
                .response_size = sizeof(test_response_t),
                .handler = alt_drv_test_rpc_begin_test_handler_prv_handler,
            },
        },
    },
};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Services
 *---------------------------------------------------------------------------------------------------*/
static cipher_service_entry_t services[] = {
    {
        .local = true,
        .service = {
            .id = SERVICE_ID,
            .name = "AltimerterTest",
            .allowed_hops = 1,
            .num_ops = 1,
            .ops = alt_drv_test_service_ops,
        },
    },
};

cipher_service_entry_t *alt_drv_test_get_services(size_t *num_services) {
    *num_services = ARRAY_SIZE(services);
    return services;
}