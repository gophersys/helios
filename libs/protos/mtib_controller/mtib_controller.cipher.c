#include "mtib_controller.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "mtib_controller.pb.h"

LOG_MODULE_REGISTER(mtibcontroller);

#define MTIBCONTROLLER_SERVICE_ID 1

typedef enum
{
    rpc_HealthCheck = 1,
} MtibController_rpc;

// Server side
static bool MtibController_HealthCheckHandlerImplemented = true;
__attribute__((weak)) HealthCheckResponse MtibController_HealthCheckHandler(HealthCheckRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibController_HealthCheckHandlerImplemented = false;
    HealthCheckResponse response  = {0};
    return response ;
}

cipher_rpc_err_t HealthCheckRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((HealthCheckResponse *)response ) = MtibController_HealthCheckHandler(*((HealthCheckRequest *)request));
    return MtibController_HealthCheckHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
HealthCheckResponse MtibController_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request)
{
    HealthCheckResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCONTROLLER_SERVICE_ID,
        .rpc_id = rpc_HealthCheck,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t mtibcontroller_rpcs[] =
{
    {
        .id = rpc_HealthCheck,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "HealthCheck",
        .handler = HealthCheckRpcPrvHandler,
        .request_info = {
            .fields = HealthCheckRequest_fields,
            .encoded_size = HealthCheckRequest_size,
            .decoded_size = sizeof(HealthCheckRequest)
        },
        .response_info = {
            .fields = HealthCheckResponse_fields,
            .encoded_size = HealthCheckResponse_size,
            .decoded_size = sizeof(HealthCheckResponse)
        },
        .supports_parallelism = true,
    },
};

static cipher_service_info_t mtibcontroller_service =
{
    .id = MTIBCONTROLLER_SERVICE_ID,
    .name = "MtibController",
    .max_hops = 1,
    .rpcs = mtibcontroller_rpcs,
    .num_rpcs = ARRAY_SIZE(mtibcontroller_rpcs),
};

cipher_service_info_t *get_mtibcontrollerservice_info(void)
{
    return &mtibcontroller_service;
}
