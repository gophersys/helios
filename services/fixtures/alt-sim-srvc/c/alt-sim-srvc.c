#include "alt-sim-srvc.h"

// Zephyr includes
#include <zephyr/random/rand32.h>

// Cipher includes
#include "daemon/api.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "protocol/serdes.h"
#include "utils/err.h"

LOG_MODULE_REGISTER(alt_sim, LOG_LEVEL_DBG);
#define SERVICE_ID 100

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Private Types
 *---------------------------------------------------------------------------------------------------*/
typedef enum {
    OP_ID_RPC_SET_ALTITUDE,
    OP_ID_RPC_GET_READINGS,
} alt_sim_service_op_id_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                   Local RPC Handlers
 *---------------------------------------------------------------------------------------------------*/

static bool alt_sim_rpc_set_altitude_handler_implemented = true;
__attribute__((weak)) alt_setting_response_t alt_sim_rpc_set_altitude_handler(alt_setting_request_t request) {
    WARN("no implementation for %s provided", __func__);
    alt_sim_rpc_set_altitude_handler_implemented = false;
    alt_setting_response_t resp = {0};
    return resp;
}

static bool alt_sim_rpc_get_readings_handler_implemented = true;
__attribute__((weak)) readings_response_t alt_sim_rpc_get_readings_handler(readings_request_t request) {
    WARN("no implementation for %s provided", __func__);
    alt_sim_rpc_get_readings_handler_implemented = false;
    readings_response_t resp = {0};
    return resp;
}

cipher_rpc_err_t alt_sim_rpc_set_altitude_prv_handler(void *request, void *response) {

    alt_setting_request_t *typed_request = (alt_setting_request_t *)request;
    alt_setting_response_t *typed_response = (alt_setting_response_t *)response;

    *typed_response = alt_sim_rpc_set_altitude_handler(*typed_request);

    if (!alt_sim_rpc_set_altitude_handler_implemented) {
        return CIPHER_RPC_ERR_NOT_IMPLEMENTED;
    }

    return CIPHER_RPC_ERR_OK;
}

cipher_rpc_err_t alt_sim_rpc_get_readings_prv_handler(void *request, void *response) {

    readings_request_t *typed_request = (readings_request_t *)request;
    readings_response_t *typed_response = (readings_response_t *)response;

    *typed_response = alt_sim_rpc_get_readings_handler(*typed_request);

    if (!alt_sim_rpc_get_readings_handler_implemented) {
        return CIPHER_RPC_ERR_NOT_IMPLEMENTED;
    }

    return CIPHER_RPC_ERR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                   Remote RPC Request Implementations
 *---------------------------------------------------------------------------------------------------*/
alt_setting_response_t alt_sim_rpc_set_altitude(cipher_daemon_t *d, cipher_rpc_user_info_t *info, alt_setting_request_t request) {

    alt_setting_response_t response = {0};

    cipher_rpc_entry_t rpc_entry = {
        .service_id = SERVICE_ID,
        .op_id = OP_ID_RPC_SET_ALTITUDE,
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

readings_response_t alt_sim_rpc_get_readings(cipher_daemon_t *d, cipher_rpc_user_info_t *info, readings_request_t request) {

    readings_response_t response = {0};

    cipher_rpc_entry_t rpc_entry = {
        .service_id = SERVICE_ID,
        .op_id = OP_ID_RPC_GET_READINGS,
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
serdes_error_t alt_setting_request_t_encode(serdes_encode_args_t *args) {
    alt_setting_request_t *payload = (alt_setting_request_t *)args->raw_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    if (!serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, payload->setting)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    if (!serdes_put_double(args->encoded_packet, args->encoded_packet_size, &position, payload->desired_altitude_ft)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    return SERDES_ERROR_OK;
}

serdes_error_t alt_setting_request_t_decode(serdes_decode_args_t *args) {
    alt_setting_request_t *payload = (alt_setting_request_t *)args->decoded_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    payload->setting = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position);
    payload->desired_altitude_ft = serdes_get_double(args->raw_packet, args->raw_packet_size, &position);

    return SERDES_ERROR_OK;
}

serdes_error_t alt_setting_response_t_encode(serdes_encode_args_t *args) {
    alt_setting_response_t *payload = (alt_setting_response_t *)args->raw_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    if (!serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, payload->err)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    uint8_t success_flag = payload->success ? 1 : 0;
    if (!serdes_put_uint8(args->encoded_packet, args->encoded_packet_size, &position, success_flag)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    return SERDES_ERROR_OK;
}

serdes_error_t alt_setting_response_t_decode(serdes_decode_args_t *args) {
    alt_setting_response_t *payload = (alt_setting_response_t *)args->decoded_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    payload->err = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position);
    payload->success = serdes_get_uint8(args->raw_packet, args->raw_packet_size, &position) == 1 ? true : false;

    return SERDES_ERROR_OK;
}

serdes_error_t readings_request_t_encode(serdes_encode_args_t *args) {
    return SERDES_ERROR_OK;
}

serdes_error_t readings_request_t_decode(serdes_decode_args_t *args) {
    return SERDES_ERROR_OK;
}

serdes_error_t readings_response_t_encode(serdes_encode_args_t *args) {
    readings_response_t *payload = (readings_response_t *)args->raw_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    if (!serdes_put_double(args->encoded_packet, args->encoded_packet_size, &position, (uint8_t)payload->temperature_c)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    if (!serdes_put_double(args->encoded_packet, args->encoded_packet_size, &position, (uint8_t)payload->pressure_inhg)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    if (!serdes_put_double(args->encoded_packet, args->encoded_packet_size, &position, (uint8_t)payload->altitude_m)) {
        return SERDES_ERROR_PUT_HELPER;
    }

    return SERDES_ERROR_OK;
}

serdes_error_t readings_response_t_decode(serdes_decode_args_t *args) {
    readings_response_t *payload = (readings_response_t *)args->decoded_payload;
    uint16_t position = sizeof(cipher_header_t);  // Start right after the header

    payload->temperature_c = serdes_get_double(args->raw_packet, args->raw_packet_size, &position);
    payload->pressure_inhg = serdes_get_double(args->raw_packet, args->raw_packet_size, &position);
    payload->altitude_m = serdes_get_double(args->raw_packet, args->raw_packet_size, &position);

    return SERDES_ERROR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  Ops
 *---------------------------------------------------------------------------------------------------*/

static cipher_ops_entry_t alt_sim_service_ops[] = {
    {
        .id = OP_ID_RPC_SET_ALTITUDE,
        .type = CIPHER_OPS_TYPE_RPC,
        .name = "SetAltitude",
        .op = {
            .rpc = {
                .request_serdes = {
                    .encode = alt_setting_request_t_encode,
                    .decode = alt_setting_request_t_decode,
                },
                .request_size = sizeof(alt_setting_request_t),
                .response_serdes = {
                    .encode = alt_setting_response_t_encode,
                    .decode = alt_setting_response_t_decode,
                },
                .response_size = sizeof(alt_setting_response_t),
                .handler = alt_sim_rpc_set_altitude_prv_handler,
            },
        },
    },
    {
        .id = OP_ID_RPC_GET_READINGS,
        .type = CIPHER_OPS_TYPE_RPC,
        .name = "GetReadings",
        .op = {
            .rpc = {
                .request_serdes = {
                    .encode = readings_request_t_encode,
                    .decode = readings_request_t_decode,
                },
                .request_size = sizeof(readings_request_t),
                .response_serdes = {
                    .encode = readings_response_t_encode,
                    .decode = readings_response_t_decode,
                },
                .response_size = sizeof(readings_response_t),
                .handler = alt_sim_rpc_get_readings_prv_handler,
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
            .name = "AltSim",
            .allowed_hops = 1,
            .num_ops = 2,
            .ops = alt_sim_service_ops,
        },
    },
};

cipher_service_entry_t *alt_sim_fixture_get_services(size_t *num_services) {
    *num_services = ARRAY_SIZE(services);
    return services;
}