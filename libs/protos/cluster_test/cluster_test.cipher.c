#include "cluster_test.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "cluster_test.pb.h"

LOG_MODULE_REGISTER(clustertest);

#define CLUSTERTEST_SERVICE_ID 1

typedef enum
{
    rpc_HealthCheck = 1,
    rpc_Execute = 2,
} ClusterTest_rpc;

// Server side
static bool ClusterTest_HealthCheckHandlerImplemented = true;
__attribute__((weak)) HealthCheckResponse ClusterTest_HealthCheckHandler(HealthCheckRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterTest_HealthCheckHandlerImplemented = false;
    HealthCheckResponse response  = {0};
    return response ;
}

cipher_rpc_err_t HealthCheckRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((HealthCheckResponse *)response ) = ClusterTest_HealthCheckHandler(*((HealthCheckRequest *)request));
    return ClusterTest_HealthCheckHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterTest_ExecuteHandlerImplemented = true;
__attribute__((weak)) ExecuteResponse ClusterTest_ExecuteHandler(ExecuteRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterTest_ExecuteHandlerImplemented = false;
    ExecuteResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ExecuteRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ExecuteResponse *)response ) = ClusterTest_ExecuteHandler(*((ExecuteRequest *)request));
    return ClusterTest_ExecuteHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
HealthCheckResponse ClusterTest_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request)
{
    HealthCheckResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERTEST_SERVICE_ID,
        .rpc_id = rpc_HealthCheck,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
ExecuteResponse ClusterTest_ExecuteRpc(cipher_unary_rpc_user_info_t *info, ExecuteRequest request)
{
    ExecuteResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERTEST_SERVICE_ID,
        .rpc_id = rpc_Execute,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t clustertest_rpcs[] =
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
    {
        .id = rpc_Execute,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Execute",
        .handler = ExecuteRpcPrvHandler,
        .request_info = {
            .fields = ExecuteRequest_fields,
            .encoded_size = ExecuteRequest_size,
            .decoded_size = sizeof(ExecuteRequest)
        },
        .response_info = {
            .fields = ExecuteResponse_fields,
            .encoded_size = ExecuteResponse_size,
            .decoded_size = sizeof(ExecuteResponse)
        },
        .supports_parallelism = true,
    },
};

static cipher_service_info_t clustertest_service =
{
    .id = CLUSTERTEST_SERVICE_ID,
    .name = "ClusterTest",
    .max_hops = 1,
    .rpcs = clustertest_rpcs,
    .num_rpcs = ARRAY_SIZE(clustertest_rpcs),
};

cipher_service_info_t *get_clustertestservice_info(void)
{
    return &clustertest_service;
}
