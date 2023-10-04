#include "autogen.h"

// Cipher includes
#include "daemon/api.h"
#include "daemon/daemon.h"
#include "daemon/registry.h"
#include "utils/err.h"

LOG_MODULE_REGISTER(user, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Weak RPCs
 *---------------------------------------------------------------------------------------------------*/
__attribute__((weak)) MotionResponse_t accel_command_motion_handler(MotionRequest_t request) {
    WARN("no implementation for %s provided", __func__);

    MotionResponse_t resp = {
        .success = true,
    };

    return resp;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Remote RPCs
 *---------------------------------------------------------------------------------------------------*/
MotionResponse_t accel_command_motion_rpc(cipher_rpc_info_t* info, MotionRequest_t request) {
    // Add an rpc request to the rpc thread
    // Await on a reponse
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Private RPCs
 *---------------------------------------------------------------------------------------------------*/

void* accel_command_motion_prv_rpc(void* request) {
    MotionRequest_t* typed_request = (MotionRequest_t*)request;
    MotionResponse_t response = accel_command_motion_handler(*typed_request);
    MotionResponse_t* response_ptr = malloc(sizeof(MotionResponse_t));  // TODO: K_heap_malloc here
    *response_ptr = response;
    return response_ptr;
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
                .handler = accel_command_motion_prv_rpc,
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