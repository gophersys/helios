#include "autogen.h"

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
 *                                                                                          Remote RPCs
 *---------------------------------------------------------------------------------------------------*/
MotionResponse_t accel_command_motion_rpc(cipher_daemon_t* d, cipher_rpc_user_info_t* info, MotionRequest_t request) {

    // Response buffer
    MotionResponse_t response = {0};

    // RPC entry info
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

    // Call general purpose RPC handler
    cipher_remote_rpc_handler(d, &rpc_entry);

    return response;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Weak Local RPCs
 *---------------------------------------------------------------------------------------------------*/

static bool accel_command_motion_handler_implemented = true;
__attribute__((weak)) MotionResponse_t accel_command_motion_handler(MotionRequest_t request) {
    WARN("no implementation for %s provided", __func__);
    accel_command_motion_handler_implemented = false;
    MotionResponse_t resp = {0};
    return resp;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                               Private Local Handlers
 *---------------------------------------------------------------------------------------------------*/

cipher_rpc_err_t accel_command_motion_prv_handler(void* request, void* response) {

    MotionRequest_t* typed_request = (MotionRequest_t*)request;
    MotionResponse_t* typed_response = (MotionResponse_t*)response;

    *typed_response = accel_command_motion_handler(*typed_request);

    if (!accel_command_motion_handler_implemented) {
        return CIPHER_RPC_ERR_NOT_IMPLEMENTED;
    }

    return CIPHER_RPC_ERR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Service Ops
 *---------------------------------------------------------------------------------------------------*/

static cipher_ops_entry_t local_ops[] = {
    {
        .id = RAND_OP_ID,
        .type = CIPHER_OPS_TYPE_RPC,
        .name = "CommandMotion",
        .op = {
            .rpc = {
                .request_size = sizeof(MotionRequest_t),
                .response_size = sizeof(MotionResponse_t),
                .handler = accel_command_motion_prv_handler,
            },
        },
    },
    // Add more operations as needed...
};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Service
 *---------------------------------------------------------------------------------------------------*/
static cipher_service_entry_t local_services[] = {
    {
        .local = true,
        .iface = NULL,
        .service = {
            .name = "AccelerometerBench",
            .service_id = SERVICE_ID,
            .device_id = THIS_DEVICE_ID,
            .num_ops = 2,
            .allowed_hops = 1,
            .ops = local_ops,
        },
    },
};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/
cipher_service_entry_t* cipher_get_local_services(size_t* num_services) {
    *num_services = ARRAY_SIZE(local_services);
    return local_services;
}