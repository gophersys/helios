#include "autogen.h"

// Cipher includes
#include "daemon/api.h"
#include "daemon/registry.h"
#include "utils/err.h"

LOG_MODULE_REGISTER(user, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Weak RPCs
 *---------------------------------------------------------------------------------------------------*/
__attribute__((weak)) MotionResponse_t accel_command_motion_rpc(MotionRequest_t request) {
    WARN("no implementation for %s provided", __func__);

    MotionResponse_t resp = {
        .success = true,
    };

    return resp;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Private RPCs
 *---------------------------------------------------------------------------------------------------*/

void* accel_command_motion_prv_rpc(void* request) {
    MotionRequest_t* typed_request = (MotionRequest_t*)request;
    MotionResponse_t response = accel_command_motion_rpc(*typed_request);
    MotionResponse_t* response_ptr = malloc(sizeof(MotionResponse_t));  // TODO: K_heap_malloc here
    *response_ptr = response;
    return response_ptr;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  Ops
 *---------------------------------------------------------------------------------------------------*/

static cipher_op_union_t accel_command_motion_op = {
    .type = CIPHER_OP_TYPE_RPC,
    .op = {
        .rpc = {
            .base = {
                .type = CIPHER_OP_TYPE_RPC,
                .op_id = 1,
                .name = "CommandMotion",
            },
            .request_size = sizeof(MotionRequest_t),
            .response_size = sizeof(MotionResponse_t),
            .handler = accel_command_motion_prv_rpc,
        },
    },
};

static cipher_op_union_t accel_accelerometer_update_op = {
    .type = CIPHER_OP_TYPE_EVENT,
    .op = {
        .event = {
            .base = {
                .type = CIPHER_OP_TYPE_EVENT,
                .op_id = 2,
                .name = "AccelerometerUpdate",
            },
            // Event-specific fields...
        },
    },
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
            .ops = {
                &accel_command_motion_op,
                &accel_accelerometer_update_op,
            },
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