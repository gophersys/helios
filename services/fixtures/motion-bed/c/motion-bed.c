#include "motion-bed.h"

// Zephyr includes
#include <zephyr/random/rand32.h>

// Cipher includes
#include "daemon/api.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "protocol/serdes.h"
#include "utils/err.h"

LOG_MODULE_REGISTER(user, LOG_LEVEL_DBG);

#define SERVICE_ID 6969

typedef enum {
    OP_ID_RPC_COMMAND_MOTION,
} accel_bench_service_op_id_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                   Local RPC Handlers
 *---------------------------------------------------------------------------------------------------*/

static bool accel_command_motion_handler_implemented = true;
__attribute__((weak)) motion_response_t accel_bench_rpc_command_motion_handler(motion_request_t request) {
    WARN("no implementation for %s provided", __func__);
    accel_command_motion_handler_implemented = false;
    motion_response_t resp = {0};
    return resp;
}

cipher_rpc_err_t accel_command_motion_prv_handler(void *request, void *response) {

    motion_request_t *typed_request = (motion_request_t *)request;
    motion_response_t *typed_response = (motion_response_t *)response;

    *typed_response = accel_bench_rpc_command_motion_handler(*typed_request);

    if (!accel_command_motion_handler_implemented) {
        return CIPHER_RPC_ERR_NOT_IMPLEMENTED;
    }

    return CIPHER_RPC_ERR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                   Remote RPC Request Implementations
 *---------------------------------------------------------------------------------------------------*/
motion_response_t accel_bench_rpc_command_motion(cipher_daemon_t *d, cipher_rpc_user_info_t *info, motion_request_t request) {

    motion_response_t response = {0};

    cipher_rpc_entry_t rpc_entry = {
        .service_id = SERVICE_ID,
        .op_id = OP_ID_RPC_COMMAND_MOTION,
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
serdes_error_t motion_request_t_encode(serdes_encode_args_t *args) {
    motion_request_t *payload = (motion_request_t *)args->raw_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    if (!serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, (uint8_t)payload->direction)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    if (!serdes_put_float(args->encoded_packet, args->encoded_packet_size, &position, payload->force)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    if (!serdes_put_float(args->encoded_packet, args->encoded_packet_size, &position, payload->interval)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    return SERDES_ERROR_OK;
}

serdes_error_t motion_request_t_decode(serdes_decode_args_t *args) {
    motion_request_t *payload = (motion_request_t *)args->decoded_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    payload->direction = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position);
    payload->force = serdes_get_float(args->raw_packet, args->raw_packet_size, &position);
    payload->interval = serdes_get_float(args->raw_packet, args->raw_packet_size, &position);

    return SERDES_ERROR_OK;
}

serdes_error_t motion_response_t_encode(serdes_encode_args_t *args) {

    motion_response_t *payload = (motion_response_t *)args->raw_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    if (!serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, (uint8_t)payload->error_code)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    uint8_t success_flag = payload->success ? 1 : 0;
    if (!serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, success_flag)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    return SERDES_ERROR_OK;
}

serdes_error_t motion_response_t_decode(serdes_decode_args_t *args) {
    motion_response_t *payload = (motion_response_t *)args->decoded_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    payload->error_code = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position);
    payload->success = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position) == 1 ? true : false;

    return SERDES_ERROR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  Ops
 *---------------------------------------------------------------------------------------------------*/



static cipher_ops_entry_t accel_bench_service_ops[] = {
    {
        .id = OP_ID_RPC_COMMAND_MOTION,
        .type = CIPHER_OPS_TYPE_RPC,
        .name = "CommandMotion",
        .op = {
            .rpc = {
                .request_serdes = {
                    .encode = motion_request_t_encode,
                    .decode = motion_request_t_decode,
                },
                .request_size = sizeof(motion_request_t),
                .response_serdes = {
                    .encode = motion_response_t_encode,
                    .decode = motion_response_t_decode,
                },
                .response_size = sizeof(motion_response_t),
                .handler = accel_command_motion_prv_handler,
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
            .name = "AccelBench",
            .allowed_hops = 1,
            .num_ops = 2,
            .ops = accel_bench_service_ops,
        },
    },
};

cipher_service_entry_t *accel_fixture_get_services(size_t *num_services) {
    *num_services = ARRAY_SIZE(services);
    return services;
}