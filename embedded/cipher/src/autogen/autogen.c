#include "autogen.h"

// Cipher includes
#include "daemon/api.h"
#include "daemon/daemon.h"
#include "daemon/registry.h"
#include "utils/err.h"

LOG_MODULE_REGISTER(user, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Remote RPCs
 *---------------------------------------------------------------------------------------------------*/
MotionResponse_t accel_command_motion_rpc(cipher_rpc_info_t* info, MotionRequest_t request) {
    // Add an rpc request to the rpc thread
    // Await on a reponse
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
        .id = 1,
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
            .service_id = 6969,
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