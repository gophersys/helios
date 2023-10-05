#include "motion-bed.h"

// Zephyr includes
#include <zephyr/random/rand32.h>

// Cipher includes
#include "daemon/api.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "utils/err.h"

LOG_MODULE_REGISTER(user, LOG_LEVEL_DBG);

#define SERVICE_ID 6969
#define RAND_OP_ID 1

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

cipher_rpc_err_t accel_command_motion_prv_handler(void* request, void* response) {

    motion_request_t* typed_request = (motion_request_t*)request;
    motion_response_t* typed_response = (motion_response_t*)response;

    *typed_response = accel_bench_rpc_command_motion_handler(*typed_request);

    if (!accel_command_motion_handler_implemented) {
        return CIPHER_RPC_ERR_NOT_IMPLEMENTED;
    }

    return CIPHER_RPC_ERR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                   Remote RPC Request Implementations
 *---------------------------------------------------------------------------------------------------*/
motion_response_t accel_bench_rpc_command_motion(cipher_daemon_t* d, cipher_rpc_user_info_t* info, motion_request_t request) {

    motion_response_t response = {0};

    cipher_rpc_entry_t rpc_entry = {
        .service_id = SERVICE_ID,
        .op_id = RAND_OP_ID,
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
 *                                                                                                  Ops
 *---------------------------------------------------------------------------------------------------*/

typedef enum {
    OP_ID_RPC_COMMAND_MOTION,
} accel_bench_service_op_id_t;

static cipher_ops_entry_t accel_bench_service_ops[] = {
    {
        .id = OP_ID_RPC_COMMAND_MOTION,
        .type = CIPHER_OPS_TYPE_RPC,
        .name = "CommandMotion",
        .op = {
            .rpc = {
                .request_size = sizeof(motion_request_t),
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
        .iface = NULL,
        .service = {
            .name = "AccelBench",
            .service_id = SERVICE_ID,
            .device_id = 0,   //TODO: This is assigned when the service is registered with the daemon
            .num_ops = 2,
            .allowed_hops = 1,
            .ops = accel_bench_service_ops,
        },
    },
};

cipher_service_entry_t* accel_fixture_get_services(size_t* num_services) {
    *num_services = ARRAY_SIZE(services);
    return services;
}